use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::{Manager, RunEvent, WindowEvent};
use tauri_plugin_shell::process::CommandChild;

const APP_VERSION: &str = env!("CARGO_PKG_VERSION");
const UPDATE_CHANNEL_LOCAL: &str = "local-installer";
const ROLLBACK_REASON_HEALTH_FAIL: &str = "health check falhou apos update";
const FORCED_FAIL_ENV: &str = "PIPELINE_SOLAR_FORCE_HEALTHCHECK_FAIL";

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct RuntimeUpdateState {
    last_started_version: Option<String>,
    pending_update: Option<PendingUpdateMarker>,
    rollback_notice: Option<RollbackNotice>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct PendingUpdateMarker {
    from_version: String,
    to_version: String,
    channel: String,
    marked_at_epoch_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RollbackNotice {
    from_version: String,
    to_version: String,
    channel: String,
    reason: String,
    rollback_at_epoch_ms: u64,
    restored_from_backup: bool,
}

#[derive(Debug, Clone)]
struct RuntimeUpdatePaths {
    state_file: PathBuf,
    notice_file: PathBuf,
    backup_sidecar: PathBuf,
    active_sidecar: PathBuf,
}

fn now_epoch_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

fn request_backend_shutdown() {
    let Ok(addr) = "127.0.0.1:8765".parse::<SocketAddr>() else {
        return;
    };
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(300)) else {
        return;
    };
    let _ = stream.set_write_timeout(Some(Duration::from_millis(300)));
    let payload = b"{}";
    let request = format!(
        "POST /api/shutdown HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        payload.len()
    );
    let _ = stream.write_all(request.as_bytes());
    let _ = stream.write_all(payload);
    let _ = stream.flush();
}

fn probe_backend_health_once(force_fail: bool) -> bool {
    if force_fail {
        return false;
    }

    let Ok(addr) = "127.0.0.1:8765".parse::<SocketAddr>() else {
        return false;
    };
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(450)) else {
        return false;
    };

    let _ = stream.set_write_timeout(Some(Duration::from_millis(450)));
    let _ = stream.set_read_timeout(Some(Duration::from_millis(450)));

    let request =
        "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nConnection: close\r\n\r\n";
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }

    response.contains("\"ok\": true") || response.contains("\"ok\":true")
}

fn wait_for_backend_health(attempts: u32, delay: Duration, force_fail: bool) -> bool {
    for _ in 0..attempts {
        if probe_backend_health_once(force_fail) {
            return true;
        }
        std::thread::sleep(delay);
    }
    false
}

fn kill_process_tree_by_pid(pid: u32) {
    let _ = Command::new("taskkill")
        .args(["/F", "/T", "/PID", &pid.to_string()])
        .output();
}

fn kill_residual_processes() {
    let targets = [
        "pipeline-solar-backend.exe",
        "pipeline-solar-backend-x86_64-pc-windows-msvc.exe",
    ];
    for target in targets {
        let _ = Command::new("taskkill")
            .args(["/F", "/T", "/IM", target])
            .output();
    }
}

fn stop_backend_now(
    backend_child: &Arc<Mutex<Option<CommandChild>>>,
    backend_pid: &Arc<Mutex<Option<u32>>>,
) {
    request_backend_shutdown();

    let pid = backend_pid.lock().ok().and_then(|mut slot| slot.take());
    if let Some(pid) = pid {
        kill_process_tree_by_pid(pid);
    }

    if let Ok(mut slot) = backend_child.lock() {
        if let Some(child) = slot.take() {
            let _ = child.kill();
        }
    }

    std::thread::sleep(Duration::from_millis(220));
    kill_residual_processes();
}

fn cleanup_backend(
    backend_child: &Arc<Mutex<Option<CommandChild>>>,
    backend_pid: &Arc<Mutex<Option<u32>>>,
    already_cleaned: &Arc<AtomicBool>,
) {
    if already_cleaned.swap(true, Ordering::SeqCst) {
        return;
    }
    stop_backend_now(backend_child, backend_pid);
}

fn resolve_sidecar_path() -> Option<PathBuf> {
    let current = std::env::current_exe().ok()?;
    let exe_dir = current.parent()?;
    let candidates = [
        "pipeline-solar-backend-x86_64-pc-windows-msvc.exe",
        "pipeline-solar-backend.exe",
    ];

    for name in candidates {
        let candidate = exe_dir.join(name);
        if candidate.exists() {
            return Some(candidate);
        }
    }
    None
}

fn resolve_update_paths(base_dir: PathBuf) -> Option<RuntimeUpdatePaths> {
    let active_sidecar = resolve_sidecar_path()?;
    let runtime_dir = base_dir.join("runtime-update");
    Some(RuntimeUpdatePaths {
        state_file: runtime_dir.join("update-runtime-state.json"),
        notice_file: runtime_dir.join("rollback-notice.json"),
        backup_sidecar: runtime_dir.join("known-good-sidecar.exe"),
        active_sidecar,
    })
}

fn ensure_parent(path: &Path) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    Ok(())
}

fn load_update_state(path: &Path) -> RuntimeUpdateState {
    match fs::read_to_string(path) {
        Ok(raw) => serde_json::from_str::<RuntimeUpdateState>(&raw).unwrap_or_default(),
        Err(_) => RuntimeUpdateState::default(),
    }
}

fn persist_update_state(paths: &RuntimeUpdatePaths, state: &RuntimeUpdateState) -> Result<(), String> {
    ensure_parent(&paths.state_file).map_err(|err| err.to_string())?;
    let payload = serde_json::to_string_pretty(state).map_err(|err| err.to_string())?;
    fs::write(&paths.state_file, payload).map_err(|err| err.to_string())?;

    if let Some(notice) = &state.rollback_notice {
        let notice_payload = serde_json::to_string_pretty(notice).map_err(|err| err.to_string())?;
        fs::write(&paths.notice_file, notice_payload).map_err(|err| err.to_string())?;
    } else if paths.notice_file.exists() {
        let _ = fs::remove_file(&paths.notice_file);
    }
    Ok(())
}

fn mark_pending_update_if_needed(state: &mut RuntimeUpdateState, current_version: &str) {
    if let Some(last) = &state.last_started_version {
        if last != current_version {
            state.pending_update = Some(PendingUpdateMarker {
                from_version: last.clone(),
                to_version: current_version.to_string(),
                channel: UPDATE_CHANNEL_LOCAL.to_string(),
                marked_at_epoch_ms: now_epoch_ms(),
            });
        }
    }
    state.last_started_version = Some(current_version.to_string());
}

fn copy_file_replace(source: &Path, target: &Path) -> Result<(), String> {
    ensure_parent(target).map_err(|err| err.to_string())?;
    if target.exists() {
        fs::remove_file(target).map_err(|err| err.to_string())?;
    }
    fs::copy(source, target).map_err(|err| err.to_string())?;
    Ok(())
}

fn update_known_good_backup(paths: &RuntimeUpdatePaths) -> Result<(), String> {
    if !paths.active_sidecar.exists() {
        return Err(format!(
            "sidecar ativo nao encontrado em {}",
            paths.active_sidecar.display()
        ));
    }
    copy_file_replace(&paths.active_sidecar, &paths.backup_sidecar)
}

fn restore_backup_sidecar(paths: &RuntimeUpdatePaths) -> Result<(), String> {
    if !paths.backup_sidecar.exists() {
        return Err(format!(
            "backup do sidecar nao encontrado em {}",
            paths.backup_sidecar.display()
        ));
    }
    copy_file_replace(&paths.backup_sidecar, &paths.active_sidecar)
}

fn build_rollback_notice(pending: &PendingUpdateMarker, reason: String, restored: bool) -> RollbackNotice {
    RollbackNotice {
        from_version: pending.from_version.clone(),
        to_version: pending.to_version.clone(),
        channel: pending.channel.clone(),
        reason,
        rollback_at_epoch_ms: now_epoch_ms(),
        restored_from_backup: restored,
    }
}

fn spawn_backend(
    handle: &tauri::AppHandle,
    backend_child: &Arc<Mutex<Option<CommandChild>>>,
    backend_pid: &Arc<Mutex<Option<u32>>>,
) -> Result<(), String> {
    use tauri_plugin_shell::ShellExt;

    let sidecar = handle
        .shell()
        .sidecar("pipeline-solar-backend")
        .map_err(|err| format!("backend sidecar nao encontrado: {err}"))?;

    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|err| format!("falha ao iniciar backend sidecar: {err}"))?;

    if let Ok(mut slot) = backend_pid.lock() {
        *slot = Some(child.pid());
    }
    if let Ok(mut slot) = backend_child.lock() {
        *slot = Some(child);
    }

    tauri::async_runtime::spawn(async move { while rx.recv().await.is_some() {} });

    Ok(())
}

fn env_force_health_fail() -> bool {
    match std::env::var(FORCED_FAIL_ENV) {
        Ok(value) => {
            let normalized = value.trim().to_ascii_lowercase();
            normalized == "1" || normalized == "true" || normalized == "yes"
        }
        Err(_) => false,
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_child: Arc<Mutex<Option<CommandChild>>> = Arc::new(Mutex::new(None));
    let backend_pid: Arc<Mutex<Option<u32>>> = Arc::new(Mutex::new(None));
    let already_cleaned = Arc::new(AtomicBool::new(false));

    let backend_child_setup = Arc::clone(&backend_child);
    let backend_pid_setup = Arc::clone(&backend_pid);
    let backend_child_close = Arc::clone(&backend_child);
    let backend_pid_close = Arc::clone(&backend_pid);
    let backend_child_run = Arc::clone(&backend_child);
    let backend_pid_run = Arc::clone(&backend_pid);
    let already_cleaned_close = Arc::clone(&already_cleaned);
    let already_cleaned_run = Arc::clone(&already_cleaned);

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let handle = app.handle().clone();
            let base_state_dir = app
                .path()
                .app_local_data_dir()
                .unwrap_or_else(|_| std::env::temp_dir().join("pipeline-solar-runtime"));
            let update_paths = resolve_update_paths(base_state_dir);

            let mut update_state = update_paths
                .as_ref()
                .map(|paths| load_update_state(&paths.state_file))
                .unwrap_or_default();

            mark_pending_update_if_needed(&mut update_state, APP_VERSION);
            if let Some(paths) = update_paths.as_ref() {
                let _ = persist_update_state(paths, &update_state);
            }

            if let Err(error) = spawn_backend(&handle, &backend_child_setup, &backend_pid_setup) {
                eprintln!("{error}");
                return Ok(());
            }

            let force_fail = env_force_health_fail();
            let mut health_ok = wait_for_backend_health(16, Duration::from_millis(350), force_fail);
            let mut rollback_triggered = false;

            if let Some(paths) = update_paths.as_ref() {
                if let Some(pending) = update_state.pending_update.clone() {
                    if !health_ok {
                        rollback_triggered = true;
                        stop_backend_now(&backend_child_setup, &backend_pid_setup);

                        let restored = restore_backup_sidecar(paths).is_ok();
                        let reason = if restored {
                            ROLLBACK_REASON_HEALTH_FAIL.to_string()
                        } else {
                            format!(
                                "{ROLLBACK_REASON_HEALTH_FAIL}; backup indisponivel em {}",
                                paths.backup_sidecar.display()
                            )
                        };

                        update_state.rollback_notice =
                            Some(build_rollback_notice(&pending, reason, restored));
                        let _ = persist_update_state(paths, &update_state);

                        if restored {
                            if let Err(error) =
                                spawn_backend(&handle, &backend_child_setup, &backend_pid_setup)
                            {
                                eprintln!("{error}");
                            } else {
                                health_ok =
                                    wait_for_backend_health(16, Duration::from_millis(350), false);
                            }
                        }
                    }

                    if health_ok {
                        update_state.pending_update = None;
                        if !rollback_triggered {
                            update_state.rollback_notice = None;
                        }
                    }
                }

                if health_ok {
                    let _ = update_known_good_backup(paths);
                }

                let _ = persist_update_state(paths, &update_state);
            }

            Ok(())
        })
        .on_window_event(move |_window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. } | WindowEvent::Destroyed) {
                cleanup_backend(
                    &backend_child_close,
                    &backend_pid_close,
                    &already_cleaned_close,
                );
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building Pipeline Solar Modernizacao");

    app.run(move |_app_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            cleanup_backend(&backend_child_run, &backend_pid_run, &already_cleaned_run);
        }
    });
}
