from __future__ import annotations

import json
import queue
import re
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Callable


TELEMETRY_SCHEMA_VERSION = 1
_ALLOWED_STATUSES = {"error", "cancelled"}
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
_ERROR_CODE_RE = re.compile(r"^[A-Z0-9_]{2,80}$")


def _sanitize_endpoint(endpoint: str) -> str | None:
    text = str(endpoint or "").strip()
    if not text:
        return None
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return text


def _sanitize_token(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if _TOKEN_RE.fullmatch(text):
        return text
    compact = re.sub(r"[^A-Za-z0-9._:-]+", "", text)[:80]
    return compact or fallback


def _sanitize_error_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if _ERROR_CODE_RE.fullmatch(text):
        return text
    compact = re.sub(r"[^A-Z0-9_]+", "_", text)[:80].strip("_")
    return compact or "ERR_EXECUCAO_PIPELINE"


def _sanitize_timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = text
    if text.endswith("Z"):
        parsed = text[:-1] + "+00:00"
    try:
        datetime.fromisoformat(parsed)
    except Exception:
        return ""
    return text


def sanitize_error_event(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    status = str(payload.get("status") or "").strip().lower()
    if status not in _ALLOWED_STATUSES:
        return None
    job_id = _sanitize_token(payload.get("job_id"), "")
    if not job_id:
        return None
    schema_value = payload.get("schema_version")
    try:
        schema_version = int(schema_value)
    except (TypeError, ValueError):
        schema_version = TELEMETRY_SCHEMA_VERSION
    if schema_version < 1:
        schema_version = TELEMETRY_SCHEMA_VERSION
    return {
        "schema_version": schema_version,
        "app_version": _sanitize_token(payload.get("app_version"), "unknown"),
        "job_id": job_id,
        "timestamp_inicio": _sanitize_timestamp(payload.get("timestamp_inicio")),
        "timestamp_fim": _sanitize_timestamp(payload.get("timestamp_fim")),
        "error_code": _sanitize_error_code(payload.get("error_code")),
        "status": status,
    }


def _post_json(endpoint: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2):
        return None


class TelemetrySidecar:
    def __init__(self, sender: Callable[[str, dict[str, Any]], None] | None = None, queue_size: int = 64) -> None:
        self._sender = sender or _post_json
        self._queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue(maxsize=max(1, int(queue_size)))
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="telemetry-sidecar")
        self._worker.start()

    def emit_error(self, endpoint: str, payload: dict[str, Any]) -> None:
        endpoint_value = _sanitize_endpoint(endpoint)
        if not endpoint_value:
            return
        sanitized_payload = sanitize_error_event(payload)
        if not sanitized_payload:
            return
        try:
            self._queue.put_nowait((endpoint_value, sanitized_payload))
        except queue.Full:
            return

    def _worker_loop(self) -> None:
        while True:
            endpoint, payload = self._queue.get()
            try:
                self._sender(endpoint, payload)
            except Exception:
                continue
