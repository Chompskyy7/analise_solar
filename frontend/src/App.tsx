import { getCurrentWindow } from "@tauri-apps/api/window";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FileSpreadsheet,
  FolderOpen,
  History,
  ListChecks,
  Minus,
  Play,
  RefreshCw,
  Save,
  Search,
  Settings2,
  Stethoscope,
  TerminalSquare,
  X
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "./components/Button";
import { DataTable, type DataTableRow } from "./components/DataTable";
import { DetailPanel, type DetailSection } from "./components/DetailPanel";
import { Layout } from "./components/Layout";
import { Sidebar, type SidebarItem } from "./components/Sidebar";
import { StatusBar } from "./components/StatusBar";
import { Toast, type ToastItem } from "./components/Toast";

const API_BASE = "http://127.0.0.1:8765";

type TabId = "executar" | "validacao" | "revisao" | "diagnostico" | "historico" | "configuracoes";
type ApiState = "checking" | "online" | "offline";

type Health = {
  version?: string;
  baseDir?: string;
  downloadsDefault?: string;
  outputDir?: string;
  rollbackNotice?: {
    fromVersion?: string;
    toVersion?: string;
    channel?: string;
    reason?: string;
    rollbackAtEpochMs?: number;
    restoredFromBackup?: boolean;
  } | null;
};

type Settings = {
  baseDir: string;
  downloadsDir: string;
  outputDir: string;
  defaultDays: number;
  importDownloads: boolean;
  quarantine: boolean;
  telemetryOptIn: boolean;
  telemetryEndpoint: string;
};

type Client = { id?: string; name?: string; label?: string };
type DownloadItem = { name?: string; filename?: string; path?: string; size?: number; modifiedAt?: string; status?: string; kind?: "pdf" | "sheet" };
type PreviewResponse = { items?: DownloadItem[]; downloads?: DownloadItem[]; pdfs?: DownloadItem[]; sheets?: DownloadItem[]; warnings?: string[] };
type DiagnosticsResponse = { summary?: string; message?: string; status?: string; items?: Array<{ name?: string; label?: string; status?: string; message?: string; details?: string }> };
type JobStatus = { id?: string; status?: string; phase?: string; message?: string; logs?: string[]; progress?: number; output_path?: string; result?: { output?: string; pdfs?: number; sheets?: number; invoices?: number } };
type RunResponse = { job_id?: string; id?: string; status?: string; message?: string };
type ComparisonRow = { key?: string; periodo_pdf?: string; periodo_gerado?: string; consumo_pdf?: number; consumo_gerado?: number; leitura_anterior_gerado?: string; leitura_atual_gerado?: string };
type ComparisonResponse = { rows?: ComparisonRow[]; summary?: { total?: number; divergent?: number; dateBlocking?: number } };
type UpdateResponse = { latestVersion?: string; currentVersion?: string; updateAvailable?: boolean; message?: string };
type HistoryItem = { id?: string; job_id?: string; client?: string; status?: string; finished_at?: string; started_at?: string; output?: string; output_path?: string; message?: string };
type HistoryResponse = HistoryItem[] | { items?: HistoryItem[]; history?: HistoryItem[] };

const defaultSettings: Settings = {
  baseDir: "",
  downloadsDir: "",
  outputDir: "",
  defaultDays: 7,
  importDownloads: true,
  quarantine: true,
  telemetryOptIn: false,
  telemetryEndpoint: ""
};

const tabs: Array<{ id: TabId; label: string; icon: SidebarItem["icon"]; bottom?: boolean }> = [
  { id: "executar", label: "Executar", icon: Play },
  { id: "validacao", label: "Validação", icon: ListChecks },
  { id: "revisao", label: "Revisão", icon: FileSpreadsheet },
  { id: "diagnostico", label: "Diagnóstico", icon: Stethoscope },
  { id: "historico", label: "Histórico", icon: History },
  { id: "configuracoes", label: "Configurações", icon: Settings2, bottom: true }
];

async function apiFetch<T>(path: string, init?: RequestInit, timeoutMs = 30000): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), Math.max(500, timeoutMs));
  const outerSignal = init?.signal;
  const abortFromOuter = () => controller.abort();

  if (outerSignal) {
    if (outerSignal.aborted) {
      controller.abort();
    } else {
      outerSignal.addEventListener("abort", abortFromOuter, { once: true });
    }
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(body || `Falha HTTP ${response.status}`);
    }
    const text = await response.text();
    return (text ? JSON.parse(text) : undefined) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Tempo limite de comunicação com o backend.");
    }
    throw err;
  } finally {
    window.clearTimeout(timeoutId);
    if (outerSignal) {
      outerSignal.removeEventListener("abort", abortFromOuter);
    }
  }
}

function clientKey(client: Client): string {
  return String(client.id || client.name || client.label || "");
}

function clientLabel(client: Client): string {
  return String(client.label || client.name || client.id || "");
}

function normalizeClient(value: string | Client): Client {
  if (typeof value === "string") return { id: value, name: value, label: value };
  return { id: value.id || value.name || value.label, name: value.name || value.id || value.label, label: value.label || value.name || value.id };
}

function statusText(state: ApiState): string {
  if (state === "online") return "online";
  if (state === "offline") return "offline";
  return "checando";
}

function taskStatusLabel(value?: string): string {
  const status = String(value || "").toLowerCase();
  if (!status) return "pendente";
  if (status === "done" || status === "success") return "concluído";
  if (status === "running") return "rodando";
  if (status === "queued") return "na fila";
  if (status === "error" || status === "cancelled") return "erro";
  return status;
}

function mapStatus(value?: string): "idle" | "running" | "success" | "error" {
  const status = String(value || "").toLowerCase();
  if (status === "running" || status === "queued") return "running";
  if (status === "done" || status === "success") return "success";
  if (status === "error" || status === "cancelled") return "error";
  return "idle";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>("executar");
  const [apiState, setApiState] = useState<ApiState>("checking");
  const [health, setHealth] = useState<Health | null>(null);
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClient, setSelectedClient] = useState("");
  const [days, setDays] = useState(7);
  const [importDownloads, setImportDownloads] = useState(true);
  const [quarantine, setQuarantine] = useState(true);

  const [preview, setPreview] = useState<DownloadItem[]>([]);
  const [clientFiles, setClientFiles] = useState<DownloadItem[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [preflight, setPreflight] = useState<DiagnosticsResponse | null>(null);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [comparisonOnlyDiff, setComparisonOnlyDiff] = useState(false);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsResponse | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [updateInfo, setUpdateInfo] = useState<UpdateResponse | null>(null);

  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const [busyPreview, setBusyPreview] = useState(false);
  const [busyCreateClient, setBusyCreateClient] = useState(false);
  const [busyPreflight, setBusyPreflight] = useState(false);
  const [busyRun, setBusyRun] = useState(false);
  const [busyCompare, setBusyCompare] = useState(false);
  const [busyAudit, setBusyAudit] = useState(false);
  const [busyDiagnostics, setBusyDiagnostics] = useState(false);
  const [busySupport, setBusySupport] = useState(false);
  const [busyRepair, setBusyRepair] = useState(false);
  const [busyHistory, setBusyHistory] = useState(false);
  const [busySettings, setBusySettings] = useState(false);
  const [busyUpdate, setBusyUpdate] = useState(false);
  const [busyCopyLogs, setBusyCopyLogs] = useState(false);
  const [busyReconnect, setBusyReconnect] = useState(false);

  const [selectedPreviewIndex, setSelectedPreviewIndex] = useState(0);
  const [selectedComparisonIndex, setSelectedComparisonIndex] = useState(0);
  const [selectedHistoryIndex, setSelectedHistoryIndex] = useState(0);
  const [selectedClientFileIndex, setSelectedClientFileIndex] = useState(0);
  const [detailCollapsed, setDetailCollapsed] = useState(false);

  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [lastRollbackNoticeTs, setLastRollbackNoticeTs] = useState(0);

  const running = busyRun || mapStatus(job?.status) === "running";
  const dateBlocked = Number(comparison?.summary?.dateBlocking || 0) > 0;
  const canGenerate = Boolean(preflight) && !dateBlocked;
  const currentTab = tabs.find((tab) => tab.id === activeTab);
  const statusState = mapStatus(job?.status);
  const statusMessage = job?.message || job?.phase || taskStatusLabel(job?.status);

  const sidebarItems: SidebarItem[] = tabs.map((tab) => ({
    id: tab.id,
    label: tab.label,
    icon: tab.icon,
    placement: tab.bottom ? "bottom" : "top"
  }));

  const previewRows = useMemo<DataTableRow[]>(
    () =>
      preview.map((item, index) => ({
        id: `preview-${index}`,
        fileName: item.filename || item.name || item.path || "arquivo",
        type: item.kind || "-",
        size: item.size ?? null,
        modifiedAt: item.modifiedAt || "-",
        status: item.status || "pendente"
      })),
    [preview]
  );

  const clientRows = useMemo<DataTableRow[]>(
    () =>
      clientFiles.map((item, index) => ({
        id: `client-${index}`,
        fileName: item.filename || item.name || item.path || "arquivo",
        type: item.kind || "-",
        size: item.size ?? null,
        modifiedAt: item.modifiedAt || "-",
        status: item.status || "pendente"
      })),
    [clientFiles]
  );

  const historyRows = useMemo<DataTableRow[]>(
    () =>
      history.map((item, index) => ({
        id: `history-${index}`,
        fileName: item.client || "cliente",
        type: "tarefa",
        size: null,
        modifiedAt: item.finished_at || item.started_at || "-",
        status: item.status || "pendente"
      })),
    [history]
  );

  const selectedComparisonRow = comparison?.rows?.[selectedComparisonIndex];
  const selectedHistoryRow = history[selectedHistoryIndex];

  const pushToast = useCallback((type: ToastItem["type"], message: string) => {
    const text = message.trim();
    if (!text) return;
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((current) => [...current, { id, type, message: text }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4000);
  }, []);

  useEffect(() => {
    if (!notice.trim()) return;
    pushToast("success", notice);
    setNotice("");
  }, [notice, pushToast]);

  useEffect(() => {
    if (!error.trim()) return;
    pushToast("error", error);
    setError("");
  }, [error, pushToast]);

  useEffect(() => {
    const rollback = health?.rollbackNotice;
    if (!rollback?.restoredFromBackup) return;
    const ts = Number(rollback.rollbackAtEpochMs || 0);
    if (!ts || ts === lastRollbackNoticeTs) return;
    setLastRollbackNoticeTs(ts);
    const from = rollback.fromVersion || "versão anterior";
    const to = rollback.toVersion || "versão atual";
    const reason = rollback.reason || "health check falhou após atualização";
    pushToast("warning", `Rollback automático executado (${from} -> ${to}). Motivo: ${reason}.`);
  }, [health?.rollbackNotice, lastRollbackNoticeTs, pushToast]);

  useEffect(() => {
    if (!startedAt || !running) return;
    const timer = window.setInterval(() => setElapsedMs(Date.now() - startedAt), 500);
    return () => window.clearInterval(timer);
  }, [startedAt, running]);

  useEffect(() => {
    const done = ["done", "success", "error", "cancelled"].includes(String(job?.status || "").toLowerCase());
    if (done && startedAt) {
      setElapsedMs(Date.now() - startedAt);
      setStartedAt(null);
    }
  }, [job?.status, startedAt]);

  useEffect(() => {
    const onClose = () => requestShutdownOnClose();
    window.addEventListener("beforeunload", onClose);
    window.addEventListener("pagehide", onClose);
    return () => {
      window.removeEventListener("beforeunload", onClose);
      window.removeEventListener("pagehide", onClose);
    };
  }, []);

  async function refreshHealth(options?: { retries?: number; intervalMs?: number; silent?: boolean }): Promise<boolean> {
    const retries = Math.max(1, options?.retries ?? 1);
    const intervalMs = Math.max(100, options?.intervalMs ?? 350);
    const silent = Boolean(options?.silent);
    let lastError: unknown = null;
    setApiState("checking");

    for (let attempt = 1; attempt <= retries; attempt += 1) {
      try {
        const data = await apiFetch<Health>("/api/health", undefined, 2500);
        setHealth(data);
        setSettings((current) => ({
          ...current,
          baseDir: current.baseDir || data.baseDir || "",
          downloadsDir: current.downloadsDir || data.downloadsDefault || "",
          outputDir: current.outputDir || data.outputDir || ""
        }));
        setApiState("online");
        return true;
      } catch (err) {
        lastError = err;
        if (attempt < retries) {
          await sleep(intervalMs);
        }
      }
    }

    setApiState("offline");
    if (!silent) {
      setError(lastError instanceof Error ? lastError.message : "Backend indisponível");
    }
    return false;
  }

  async function loadSettings() {
    try {
      const data = await apiFetch<Partial<Settings>>("/api/settings");
      setSettings((current) => ({ ...current, ...data }));
      if (typeof data.defaultDays === "number") setDays(Number(data.defaultDays));
      if (typeof data.importDownloads === "boolean") setImportDownloads(Boolean(data.importDownloads));
      if (typeof data.quarantine === "boolean") setQuarantine(Boolean(data.quarantine));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar configurações");
    }
  }

  async function saveSettings(event?: FormEvent) {
    event?.preventDefault();
    setBusySettings(true);
    try {
      await apiFetch("/api/settings", {
        method: "POST",
        body: JSON.stringify({ ...settings, defaultDays: days, importDownloads, quarantine })
      });
      setNotice("Configurações salvas.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar configurações");
    } finally {
      setBusySettings(false);
    }
  }

  async function persistSettingsSilently() {
    await apiFetch("/api/settings", {
      method: "POST",
      body: JSON.stringify({ ...settings, defaultDays: days, importDownloads, quarantine })
    });
  }

  async function loadClients() {
    try {
      const data = await apiFetch<Array<string | Client> | { clients?: Array<string | Client> }>("/api/clients");
      const raw = Array.isArray(data) ? data : data.clients ?? [];
      const list = raw.map(normalizeClient);
      setClients(list);
      setSelectedClient((current) => current || clientKey(list[0] || {}));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar clientes");
    }
  }

  async function reconnectBackend() {
    setBusyReconnect(true);
    try {
      const online = await refreshHealth({ retries: 10, intervalMs: 450, silent: false });
      if (!online) return;
      await Promise.all([loadSettings(), loadClients()]);
      setNotice("Backend conectado.");
    } finally {
      setBusyReconnect(false);
    }
  }

  async function createClient() {
    if (!selectedClient.trim()) return;
    setBusyCreateClient(true);
    try {
      await persistSettingsSilently();
      await apiFetch("/api/clients/create", { method: "POST", body: JSON.stringify({ client: selectedClient, baseDir: settings.baseDir }) });
      await loadClients();
      setNotice("Cliente criado/verificado com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar cliente");
    } finally {
      setBusyCreateClient(false);
    }
  }

  async function loadPreview(event?: FormEvent) {
    event?.preventDefault();
    if (!selectedClient.trim()) return;
    setBusyPreview(true);
    try {
      await persistSettingsSilently();
      const data = await apiFetch<PreviewResponse>("/api/downloads/preview", {
        method: "POST",
        body: JSON.stringify({
          client: selectedClient,
          origin: settings.downloadsDir,
          downloads: settings.downloadsDir,
          downloadsDir: settings.downloadsDir,
          outputDir: settings.outputDir,
          days,
          importDownloads,
          quarantine
        })
      });
      const pdfs = (data.pdfs ?? []).map((item) => ({ ...item, kind: "pdf" as const }));
      const sheets = (data.sheets ?? []).map((item) => ({ ...item, kind: "sheet" as const }));
      setPreview(data.items ?? data.downloads ?? [...pdfs, ...sheets]);
      setWarnings(data.warnings ?? []);
      const local = await apiFetch<PreviewResponse>("/api/client-files/preview", { method: "POST", body: JSON.stringify({ client: selectedClient }) });
      setClientFiles([...(local.pdfs ?? []).map((item) => ({ ...item, kind: "pdf" as const })), ...(local.sheets ?? []).map((item) => ({ ...item, kind: "sheet" as const }))]);
      setActiveTab("validacao");
      setSelectedPreviewIndex(0);
      setNotice("Prévia carregada.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar prévia");
    } finally {
      setBusyPreview(false);
    }
  }

  async function runPreflight() {
    setBusyPreflight(true);
    try {
      await persistSettingsSilently();
      const data = await apiFetch<DiagnosticsResponse>("/api/preflight", {
        method: "POST",
        body: JSON.stringify({
          client: selectedClient,
          downloads: settings.downloadsDir,
          downloadsDir: settings.downloadsDir,
          outputDir: settings.outputDir,
          days,
          importDownloads
        })
      });
      setPreflight(data);
      setActiveTab("validacao");
      setNotice(data.summary || "Checklist concluído.");
      if (selectedClient) await loadComparison(comparisonOnlyDiff);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no checklist");
    } finally {
      setBusyPreflight(false);
    }
  }

  async function runPipeline() {
    if (!selectedClient.trim()) return;
    if (!preflight) {
      setError("Execute a validação antes de gerar.");
      return;
    }
    if (dateBlocked) {
      setError("Geração bloqueada por divergências de data.");
      return;
    }
    setBusyRun(true);
    try {
      await persistSettingsSilently();
      const data = await apiFetch<RunResponse>("/api/pipeline/run", {
        method: "POST",
        body: JSON.stringify({
          client: selectedClient,
          downloads: settings.downloadsDir,
          downloadsDir: settings.downloadsDir,
          origin: settings.downloadsDir,
          outputDir: settings.outputDir,
          days,
          importDownloads,
          quarantine
        })
      });
      const id = data.job_id || data.id || "";
      setJobId(id);
      setJob({ id, status: data.status || "queued", message: data.message });
      setStartedAt(Date.now());
      setElapsedMs(0);
      setActiveTab("executar");
      setNotice("Tarefa enviada para execução.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao executar pipeline");
    } finally {
      setBusyRun(false);
    }
  }

  async function loadComparison(onlyDivergences = comparisonOnlyDiff) {
    if (!selectedClient.trim()) return;
    setBusyCompare(true);
    try {
      const data = await apiFetch<ComparisonResponse>("/api/compare/build", {
        method: "POST",
        body: JSON.stringify({ client: selectedClient, output_path: job?.result?.output || job?.output_path, onlyDivergences })
      }, 60000);
      setComparison(data);
      setNotice("Comparação atualizada.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na comparação");
    } finally {
      setBusyCompare(false);
    }
  }

  async function exportAudit() {
    setBusyAudit(true);
    try {
      await apiFetch("/api/audit/export", { method: "POST", body: JSON.stringify({ client: selectedClient, output_path: job?.result?.output || job?.output_path }) });
      setNotice("Auditoria exportada.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar auditoria");
    } finally {
      setBusyAudit(false);
    }
  }

  async function runDiagnostics() {
    setBusyDiagnostics(true);
    try {
      await persistSettingsSilently();
      const data = await apiFetch<DiagnosticsResponse>("/api/diagnostics/run", {
        method: "POST",
        body: JSON.stringify({
          client: selectedClient,
          baseDir: settings.baseDir,
          downloads: settings.downloadsDir,
          downloadsDir: settings.downloadsDir,
          origin: settings.downloadsDir,
          outputDir: settings.outputDir,
          days,
          defaultDays: days
        })
      });
      setDiagnostics(data);
      setNotice(data.summary || data.message || "Diagnóstico concluído.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no diagnóstico");
    } finally {
      setBusyDiagnostics(false);
    }
  }

  async function loadHistory() {
    setBusyHistory(true);
    try {
      const data = await apiFetch<HistoryResponse>("/api/history");
      setHistory(Array.isArray(data) ? data : data.items ?? data.history ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar histórico");
    } finally {
      setBusyHistory(false);
    }
  }

  async function checkUpdates() {
    setBusyUpdate(true);
    try {
      const data = await apiFetch<UpdateResponse>("/api/updates/check");
      setUpdateInfo(data);
      setNotice(data.message || (data.updateAvailable ? "Nova versão disponível." : "Sem atualização."));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao verificar atualização");
    } finally {
      setBusyUpdate(false);
    }
  }

  async function exportSupportPackage() {
    setBusySupport(true);
    try {
      await apiFetch("/api/support/export", { method: "POST", body: JSON.stringify({ client: selectedClient, job_id: jobId }) });
      setNotice("Pacote de suporte exportado.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar suporte");
    } finally {
      setBusySupport(false);
    }
  }

  async function repairInstallation() {
    setBusyRepair(true);
    try {
      await apiFetch("/api/install/repair", { method: "POST", body: "{}" });
      setNotice("Reparo concluído.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no reparo");
    } finally {
      setBusyRepair(false);
    }
  }

  async function openHistoryOutput(item: HistoryItem) {
    try {
      await apiFetch("/api/history/open-output", { method: "POST", body: JSON.stringify({ id: item.id, job_id: item.job_id || item.id, output: item.output, output_path: item.output_path }) });
      setNotice("Abertura solicitada.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao abrir saída");
    }
  }

  async function retryTask(item: HistoryItem) {
    const id = item.job_id || item.id;
    if (!id) return;
    try {
      const data = await apiFetch<JobStatus>(`/api/jobs/${encodeURIComponent(id)}/retry-smart`, { method: "POST", body: JSON.stringify({ maxAttempts: 2 }) });
      if (data.id) {
        setJobId(data.id);
        setJob(data);
      }
      setNotice("Reexecução solicitada.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao reexecutar");
    }
  }

  async function resumeTask(item: HistoryItem) {
    const id = item.job_id || item.id;
    if (!id) return;
    try {
      const data = await apiFetch<JobStatus>(`/api/jobs/${encodeURIComponent(id)}/resume`, { method: "POST", body: "{}" });
      if (data.id) {
        setJobId(data.id);
        setJob(data);
      }
      setNotice("Retomada solicitada.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao retomar");
    }
  }

  async function copyTaskLogs() {
    if (!jobId) return;
    setBusyCopyLogs(true);
    try {
      const data = await apiFetch<{ text?: string }>(`/api/jobs/${encodeURIComponent(jobId)}/logs/copy`, { method: "POST", body: JSON.stringify({ onlyErrors: false }) });
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(data.text || "");
        setNotice("Logs copiados.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao copiar logs");
    } finally {
      setBusyCopyLogs(false);
    }
  }

  function requestShutdownOnClose() {
    try {
      const payload = JSON.stringify({});
      const url = `${API_BASE}/api/shutdown`;
      if (navigator.sendBeacon) {
        navigator.sendBeacon(url, new Blob([payload], { type: "application/json" }));
      } else {
        fetch(url, { method: "POST", body: payload, headers: { "Content-Type": "application/json" }, keepalive: true }).catch(() => {});
      }
    } catch {
      // no-op
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const online = await refreshHealth({ retries: 12, intervalMs: 450, silent: true });
      if (!online) {
        if (!cancelled) setError("Backend indisponível. Aguarde alguns segundos e tente reconectar.");
        return;
      }
      if (cancelled) return;
      await Promise.all([loadSettings(), loadClients()]);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (apiState !== "offline") return;
    const timer = window.setTimeout(async () => {
      const online = await refreshHealth({ retries: 2, intervalMs: 350, silent: true });
      if (online) {
        await Promise.all([loadSettings(), loadClients()]);
      }
    }, 1800);
    return () => window.clearTimeout(timer);
  }, [apiState]);

  useEffect(() => {
    if (!jobId) return;
    const timer = window.setInterval(async () => {
      try {
        const data = await apiFetch<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}`, undefined, 2500);
        setJob(data);
      } catch {
        // silent
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [jobId]);

  const detailSections: DetailSection[] = [
    {
      id: "informacoes",
      title: "Informações",
      defaultOpen: true,
      content: (
        <div className="detail-date-grid">
          <div className="detail-date-row"><span className="detail-date-label">Cliente</span><span className="detail-date-value">{selectedClient || "-"}</span></div>
          <div className="detail-date-row"><span className="detail-date-label">Conexão</span><span className="detail-date-value">{statusText(apiState)}</span></div>
          <div className="detail-date-row"><span className="detail-date-label">Status</span><span className="detail-date-value">{taskStatusLabel(job?.status)}</span></div>
        </div>
      )
    },
    {
      id: "datas",
      title: "Datas Extraídas",
      defaultOpen: true,
      content: (
        <div className="detail-date-grid">
          <div className="detail-date-row"><span className="detail-date-label">Período PDF</span><span className="detail-date-value">{selectedComparisonRow?.periodo_pdf || "-"}</span></div>
          <div className="detail-date-row"><span className="detail-date-label">Período gerado</span><span className="detail-date-value">{selectedComparisonRow?.periodo_gerado || "-"}</span></div>
          <div className="detail-date-row"><span className="detail-date-label">Leitura anterior</span><span className="detail-date-value">{selectedComparisonRow?.leitura_anterior_gerado || "-"}</span></div>
          <div className="detail-date-row"><span className="detail-date-label">Leitura atual</span><span className="detail-date-value">{selectedComparisonRow?.leitura_atual_gerado || "-"}</span></div>
        </div>
      )
    },
    {
      id: "checklist",
      title: "Checklist",
      defaultOpen: true,
      content: (
        <div className="detail-date-grid">
          <div className="detail-date-row"><span className="detail-date-label">Pré-execução</span><span className="detail-date-value">{preflight?.summary || "não executado"}</span></div>
          <div className="detail-date-row"><span className="detail-date-label">Bloqueio de data</span><span className="detail-date-value">{dateBlocked ? "sim" : "não"}</span></div>
          <div className="detail-date-row"><span className="detail-date-label">Pode gerar</span><span className="detail-date-value">{canGenerate ? "sim" : "não"}</span></div>
        </div>
      )
    }
  ];

  const center = (
    <div className="content-stack">
      {activeTab === "executar" && (
        <>
          <section className="panel-surface">
            <div className="panel-row">
              <h3 className="panel-heading">Executar</h3>
              <Button variant="secondary" onClick={reconnectBackend} loading={busyReconnect} leftIcon={<RefreshCw size={14} />}>
                Reconectar
              </Button>
            </div>
            <p className="panel-note">Conexão backend: {statusText(apiState)}</p>
            <form className="form-grid" onSubmit={loadPreview}>
              <label className="field">
                <span className="field-label">Diretório base</span>
                <input className="field-control" title={settings.baseDir} value={settings.baseDir} onChange={(event) => setSettings((current) => ({ ...current, baseDir: event.target.value }))} />
              </label>
              <label className="field">
                <span className="field-label">Cliente</span>
                <input className="field-control" list="clients-list" value={selectedClient} onChange={(event) => setSelectedClient(event.target.value)} />
                <datalist id="clients-list">{clients.map((client) => <option key={clientKey(client)} value={clientKey(client)}>{clientLabel(client)}</option>)}</datalist>
              </label>
              <label className="field">
                <span className="field-label">Pasta de downloads</span>
                <input className="field-control" title={settings.downloadsDir} value={settings.downloadsDir} onChange={(event) => setSettings((current) => ({ ...current, downloadsDir: event.target.value }))} />
              </label>
              <label className="field">
                <span className="field-label">Dias</span>
                <input className="field-control" type="number" min={1} max={365} value={days} onChange={(event) => setDays(Number(event.target.value))} />
              </label>
              <label className="field">
                <span className="field-label">Pasta de saída</span>
                <input className="field-control" title={settings.outputDir} value={settings.outputDir} onChange={(event) => setSettings((current) => ({ ...current, outputDir: event.target.value }))} />
              </label>
            </form>
            <div className="inline-checks">
              <label className="check-item"><input type="checkbox" checked={importDownloads} onChange={(event) => setImportDownloads(event.target.checked)} /><span>Importar downloads</span></label>
              <label className="check-item"><input type="checkbox" checked={quarantine} onChange={(event) => setQuarantine(event.target.checked)} /><span>Usar quarentena</span></label>
            </div>
            <div className="inline-actions">
              <Button variant="secondary" onClick={createClient} loading={busyCreateClient} leftIcon={<FolderOpen size={14} />} disabled={apiState !== "online" || !selectedClient.trim()}>Criar cliente</Button>
              <Button variant="secondary" onClick={loadPreview} loading={busyPreview} leftIcon={<Search size={14} />} disabled={apiState !== "online"}>Prévia</Button>
              <Button variant="secondary" onClick={runPreflight} loading={busyPreflight} leftIcon={<ListChecks size={14} />} disabled={apiState !== "online" || !selectedClient.trim()}>Validação</Button>
              <Button variant="primary" onClick={runPipeline} loading={running} leftIcon={<Play size={14} />} disabled={apiState !== "online" || !canGenerate}>Executar</Button>
            </div>
            {warnings.length > 0 && <p className="panel-note">{warnings.join(" | ")}</p>}
          </section>
          <section className="panel-surface">
            <h3 className="panel-heading">Arquivos baixados encontrados</h3>
            <DataTable rows={previewRows} selectedId={`preview-${selectedPreviewIndex}`} onSelect={(row) => setSelectedPreviewIndex(Number(row.id.replace("preview-", "")) || 0)} emptyText="Execute a prévia para listar arquivos." />
          </section>
        </>
      )}

      {activeTab === "validacao" && (
        <>
          <section className="panel-surface">
            <div className="panel-row">
              <h3 className="panel-heading">Validação</h3>
              <div className="inline-actions">
                <Button variant="secondary" onClick={() => loadComparison(comparisonOnlyDiff)} loading={busyCompare} leftIcon={<RefreshCw size={14} />}>Atualizar</Button>
                <Button variant="secondary" onClick={exportAudit} loading={busyAudit} leftIcon={<Save size={14} />} disabled={!selectedClient}>Auditoria</Button>
              </div>
            </div>
            <label className="check-item">
              <input type="checkbox" checked={comparisonOnlyDiff} onChange={(event) => { const next = event.target.checked; setComparisonOnlyDiff(next); loadComparison(next); }} />
              <span>Somente divergências</span>
            </label>
            <table className="data-table">
              <thead><tr><th>Chave</th><th>Período PDF</th><th>Período gerado</th><th>Consumo PDF</th><th>Consumo gerado</th></tr></thead>
              <tbody>
                {(comparison?.rows ?? []).length === 0 && <tr><td colSpan={5}>Sem comparação carregada.</td></tr>}
                {(comparison?.rows ?? []).map((row, index) => (
                  <tr key={`${row.key || index}`} className={index === selectedComparisonIndex ? "is-selected" : ""} onClick={() => setSelectedComparisonIndex(index)}>
                    <td>{row.key || "-"}</td><td>{row.periodo_pdf || "-"}</td><td>{row.periodo_gerado || "-"}</td><td>{row.consumo_pdf ?? "-"}</td><td>{row.consumo_gerado ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}

      {activeTab === "revisao" && <section className="panel-surface"><h3 className="panel-heading">Revisão</h3><DataTable rows={clientRows} selectedId={`client-${selectedClientFileIndex}`} onSelect={(row) => setSelectedClientFileIndex(Number(row.id.replace("client-", "")) || 0)} emptyText="Nenhum arquivo no cliente." /></section>}

      {activeTab === "diagnostico" && (
        <section className="panel-surface">
          <div className="panel-row">
            <h3 className="panel-heading">Diagnóstico</h3>
            <Button variant="primary" onClick={runDiagnostics} loading={busyDiagnostics} leftIcon={<Stethoscope size={14} />} disabled={apiState !== "online"}>Diagnosticar</Button>
          </div>
          <div className="inline-actions">
            <Button variant="secondary" onClick={exportSupportPackage} loading={busySupport} leftIcon={<Save size={14} />}>Suporte</Button>
            <Button variant="secondary" onClick={repairInstallation} loading={busyRepair} leftIcon={<RefreshCw size={14} />}>Reparar instalação</Button>
          </div>
          <p className="panel-note">{diagnostics?.summary || diagnostics?.message || "Nenhum diagnóstico executado."}</p>
          <div className="check-list-grid">
            {(diagnostics?.items ?? []).map((item, index) => (
              <article key={`${item.name || item.label}-${index}`} className={`diag-card diag-${item.status || "pending"}`}>
                <strong>{item.label || item.name || "Verificação"}</strong>
                <span>{item.message || item.details || item.status || "-"}</span>
              </article>
            ))}
          </div>
        </section>
      )}

      {activeTab === "historico" && (
        <section className="panel-surface">
          <div className="panel-row">
            <h3 className="panel-heading">Histórico</h3>
            <Button variant="secondary" onClick={loadHistory} loading={busyHistory} leftIcon={<RefreshCw size={14} />} disabled={apiState !== "online"}>Atualizar</Button>
          </div>
          <DataTable rows={historyRows} selectedId={`history-${selectedHistoryIndex}`} onSelect={(row) => setSelectedHistoryIndex(Number(row.id.replace("history-", "")) || 0)} emptyText="Sem histórico." />
          <div className="inline-actions">
            <Button variant="secondary" onClick={() => selectedHistoryRow && openHistoryOutput(selectedHistoryRow)} disabled={!selectedHistoryRow} leftIcon={<ExternalLink size={14} />}>Abrir</Button>
            <Button variant="secondary" onClick={() => selectedHistoryRow && retryTask(selectedHistoryRow)} disabled={!selectedHistoryRow} leftIcon={<RefreshCw size={14} />}>Reexecutar</Button>
            <Button variant="secondary" onClick={() => selectedHistoryRow && resumeTask(selectedHistoryRow)} disabled={!selectedHistoryRow} leftIcon={<Play size={14} />}>Retomar</Button>
          </div>
        </section>
      )}

      {activeTab === "configuracoes" && (
        <section className="panel-surface">
          <h3 className="panel-heading">Configurações</h3>
          <form className="form-grid" onSubmit={saveSettings}>
            <label className="field"><span className="field-label">Diretório base</span><input className="field-control" title={settings.baseDir} value={settings.baseDir} onChange={(event) => setSettings((current) => ({ ...current, baseDir: event.target.value }))} /></label>
            <label className="field"><span className="field-label">Pasta de downloads</span><input className="field-control" title={settings.downloadsDir} value={settings.downloadsDir} onChange={(event) => setSettings((current) => ({ ...current, downloadsDir: event.target.value }))} /></label>
            <label className="field"><span className="field-label">Pasta de saída</span><input className="field-control" title={settings.outputDir} value={settings.outputDir} onChange={(event) => setSettings((current) => ({ ...current, outputDir: event.target.value }))} /></label>
            <label className="field"><span className="field-label">Dias padrão</span><input className="field-control" type="number" min={1} max={365} value={days} onChange={(event) => setDays(Number(event.target.value))} /></label>
            <div className="inline-checks">
              <label className="check-item"><input type="checkbox" checked={importDownloads} onChange={(event) => setImportDownloads(event.target.checked)} /><span>Importar downloads por padrão</span></label>
              <label className="check-item"><input type="checkbox" checked={quarantine} onChange={(event) => setQuarantine(event.target.checked)} /><span>Usar quarentena por padrão</span></label>
              <label className="check-item"><input type="checkbox" checked={Boolean(settings.telemetryOptIn)} onChange={(event) => setSettings((current) => ({ ...current, telemetryOptIn: event.target.checked }))} /><span>Ativar telemetria de erros (opt-in)</span></label>
            </div>
            <label className="field">
              <span className="field-label">Endpoint da telemetria</span>
              <input
                className="field-control"
                placeholder="https://seu-endpoint/telemetria (opcional)"
                value={settings.telemetryEndpoint || ""}
                onChange={(event) => setSettings((current) => ({ ...current, telemetryEndpoint: event.target.value }))}
              />
            </label>
            <div className="telemetry-disclosure">
              <p className="panel-note telemetry-title">Dados coletados quando o opt-in está ativo:</p>
              <ul className="telemetry-list">
                <li>ID da tarefa e timestamps de início/fim</li>
                <li>Código de erro padronizado do backend</li>
                <li>Versão do aplicativo e versão de schema local</li>
                <li>Status resumido da execução (sem conteúdo de cliente)</li>
              </ul>
              <p className="panel-note">Não são enviados por padrão: nome de cliente, valores financeiros, caminhos absolutos ou dados pessoais.</p>
            </div>
            <div className="inline-actions">
              <Button variant="primary" type="submit" loading={busySettings} leftIcon={<Save size={14} />} disabled={apiState !== "online"}>Salvar</Button>
              <Button variant="secondary" type="button" onClick={checkUpdates} loading={busyUpdate} leftIcon={<RefreshCw size={14} />} disabled={apiState !== "online"}>Versão</Button>
            </div>
            <p className="panel-note">Atual: {updateInfo?.latestVersion || health?.version || updateInfo?.currentVersion || "-"}</p>
          </form>
        </section>
      )}
    </div>
  );

  return (
    <>
      <header className="window-frame">
        <div className="window-drag" data-tauri-drag-region>Análise Solar Plus</div>
        <div className="window-actions">
          <button
            type="button"
            className="window-btn"
            onClick={async () => {
              try {
                await getCurrentWindow().minimize();
              } catch {
                // no-op
              }
            }}
            aria-label="Minimizar"
          >
            <Minus size={14} />
          </button>
          <button
            type="button"
            className="window-btn"
            onClick={async () => {
              requestShutdownOnClose();
              try {
                await getCurrentWindow().close();
                return;
              } catch {
                // fallback
              }
              try {
                window.close();
              } catch {
                // no-op
              }
            }}
            aria-label="Fechar"
          >
            <X size={14} />
          </button>
        </div>
      </header>
      <div className="window-body">
        <Layout
          sidebar={<Sidebar items={sidebarItems} activeId={activeTab} onSelect={(id) => { const next = id as TabId; setActiveTab(next); if (next === "historico") loadHistory(); }} />}
          sectionTitle={currentTab?.label || "Executar"}
          breadcrumb={`${currentTab?.label || "Executar"} / ${selectedClient || "Sem cliente selecionado"}`}
          center={center}
          statusBar={<StatusBar status={statusState} message={statusMessage} elapsedMs={elapsedMs} />}
          detail={
            <DetailPanel
              collapsed={detailCollapsed}
              onToggleCollapsed={() => setDetailCollapsed((current) => !current)}
              sections={detailSections}
              footerActions={
                <>
                  <Button variant="secondary" onClick={copyTaskLogs} loading={busyCopyLogs} leftIcon={<TerminalSquare size={14} />} disabled={!jobId}>Logs</Button>
                  <Button variant="secondary" onClick={runPreflight} loading={busyPreflight} leftIcon={<CheckCircle2 size={14} />} disabled={apiState !== "online" || !selectedClient.trim()}>Checklist</Button>
                  <Button variant="primary" onClick={runPipeline} loading={running} leftIcon={<Play size={14} />} disabled={apiState !== "online" || !canGenerate}>Executar</Button>
                </>
              }
            />
          }
          detailCollapsed={detailCollapsed}
        />
      </div>

      <div className="toast-stack">
        {toasts.map((toast) => (
          <Toast key={toast.id} toast={toast} onClose={(id) => setToasts((current) => current.filter((item) => item.id !== id))} />
        ))}
      </div>
    </>
  );
}
