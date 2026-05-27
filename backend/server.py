from __future__ import annotations

import json
import argparse
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from backend import service


HOST = "127.0.0.1"
PORT = 8765


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "PipelineSolarBackend/1.0"

    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                self._send_json(service.health())
            elif parsed.path == "/api/settings":
                self._send_json(service.get_settings())
            elif parsed.path == "/api/updates/check":
                self._send_json(service.check_updates())
            elif parsed.path == "/api/install/check-locks":
                self._send_json(service.check_installation_locks())
            elif parsed.path == "/api/clients":
                filter_text = query.get("filter", [""])[0]
                self._send_json(service.list_clients(filter_text))
            elif parsed.path == "/api/history":
                self._send_json(service.list_history())
            elif parsed.path == "/api/jobs":
                self._send_json(service.list_jobs())
            elif parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/logs"):
                job_id = parsed.path.split("/")[-2]
                tail = int(query.get("tail", ["400"])[0] or 400)
                self._send_json(service.job_logs(job_id, tail))
            elif parsed.path.startswith("/api/jobs/"):
                job_id = parsed.path.rsplit("/", 1)[-1]
                job = service.jobs.get(job_id)
                if not job:
                    self._send_error(404, "Tarefa não encontrada.")
                    return
                self._send_json(job.payload())
            else:
                self._send_error(404, "Endpoint não encontrado.")
        except Exception as exc:
            self._send_error(500, str(exc))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/downloads/preview":
                self._send_json(
                    service.preview_downloads(
                        origin=payload.get("origin") or payload.get("downloads"),
                        days=int(payload.get("days") or 7),
                    )
                )
            elif parsed.path == "/api/client-files/preview":
                self._send_json(service.preview_client_files(str(payload.get("client") or "")))
            elif parsed.path == "/api/preflight":
                self._send_json(service.preflight_check(payload))
            elif parsed.path == "/api/settings":
                self._send_json(service.save_settings(payload))
            elif parsed.path == "/api/diagnostics/run":
                self._send_json(service.run_diagnostics(payload))
            elif parsed.path == "/api/clients/create":
                base_dir = str(payload.get("baseDir") or "").strip()
                if base_dir:
                    service.save_settings({"baseDir": base_dir})
                self._send_json(service.create_client(str(payload.get("client") or ""), base_dir=base_dir or None), status=201)
            elif parsed.path == "/api/pipeline/run":
                date_guard = service.validate_dates_for_generation(str(payload.get("client") or ""))
                if not date_guard.get("ok"):
                    self._send_json(
                        {
                            "ok": False,
                            "error": "Bloqueio de datas: corrija divergências de período antes de gerar.",
                            "dateIssues": date_guard.get("issues", []),
                        },
                        status=422,
                    )
                    return
                job = service.jobs.create(payload)
                self._send_json(job.payload(), status=202)
            elif parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/cancel"):
                job_id = parsed.path.split("/")[-2]
                self._send_json(service.jobs.cancel(job_id).payload())
            elif parsed.path == "/api/open/output":
                self._send_json(service.open_output_folder())
            elif parsed.path == "/api/open/client":
                self._send_json(service.open_client_folder(str(payload.get("client") or "")))
            elif parsed.path == "/api/open/file":
                self._send_json(service.open_file(str(payload.get("path") or payload.get("output") or "")))
            elif parsed.path == "/api/history/open-output":
                self._send_json(service.open_history_output(payload.get("output") or payload.get("output_path")))
            elif parsed.path == "/api/logs/export":
                self._send_json(service.export_logs(payload.get("jobId") or payload.get("job_id")))
            elif parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/logs/copy"):
                job_id = parsed.path.split("/")[-3]
                self._send_json(service.job_logs_copy(job_id, bool(payload.get("onlyErrors", False))))
            elif parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/retry"):
                job_id = parsed.path.split("/")[-2]
                self._send_json(service.jobs.retry(job_id).payload(), status=202)
            elif parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/retry-smart"):
                job_id = parsed.path.split("/")[-2]
                self._send_json(service.jobs.retry_smart(job_id, int(payload.get("maxAttempts") or 2)).payload(), status=202)
            elif parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/resume"):
                job_id = parsed.path.split("/")[-2]
                self._send_json(service.jobs.resume(job_id).payload(), status=202)
            elif parsed.path == "/api/compare/build":
                self._send_json(service.compare_pdf_vs_generated(payload))
            elif parsed.path == "/api/compare/apply-corrections":
                self._send_json(service.apply_quick_corrections(payload))
            elif parsed.path == "/api/audit/export":
                self._send_json(service.export_audit_report(payload))
            elif parsed.path == "/api/support/export":
                self._send_json(service.export_support_package(payload))
            elif parsed.path == "/api/install/repair":
                self._send_json(service.repair_installation())
            elif parsed.path == "/api/shutdown":
                self._send_json(service.shutdown_backend())
            else:
                self._send_error(404, "Endpoint não encontrado.")
        except Exception as exc:
            self._send_error(500, str(exc))

    def log_message(self, fmt: str, *args) -> None:
        print(f"[api] {self.address_string()} - {fmt % args}")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw.strip() else {}

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"ok": False, "error": message}, status=status)


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--self-check", action="store_true")
    args, _ = parser.parse_known_args()

    if args.self_check:
        result = self_check()
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if result.get("ok") else 2)

    server = ThreadingHTTPServer((HOST, PORT), ApiHandler)
    print(f"Pipeline Solar backend em http://{HOST}:{PORT}")
    print("Pressione Ctrl+C para parar.")
    server.serve_forever()


def self_check() -> dict:
    modules = [
        "pipeline_core",
        "backend.service",
        "pdfplumber",
        "pandas",
        "openpyxl",
        "xlrd",
    ]
    checks = []
    ok = True
    for module_name in modules:
        try:
            __import__(module_name)
            checks.append({"module": module_name, "ok": True})
        except Exception as exc:
            ok = False
            checks.append({"module": module_name, "ok": False, "error": str(exc)})

    return {
        "ok": ok,
        "host": HOST,
        "port": PORT,
        "python": sys.version.split()[0],
        "checks": checks,
    }


if __name__ == "__main__":
    main()
