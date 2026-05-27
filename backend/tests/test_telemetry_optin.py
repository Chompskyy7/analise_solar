import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import error_codes, service, telemetry


class _CaptureSidecar:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def emit_error(self, endpoint: str, payload: dict) -> None:
        self.calls.append((endpoint, payload))


class TelemetryOptInTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="telemetry-optin-"))
        self._settings_file = self._tmp_dir / "settings.json"
        self._history_file = self._tmp_dir / "history.json"

        self._orig_settings_file = service.SETTINGS_FILE
        self._orig_history_file = service.HISTORY_FILE
        self._orig_sidecar = service.telemetry_sidecar

        service.SETTINGS_FILE = self._settings_file
        service.HISTORY_FILE = self._history_file
        service.telemetry_sidecar = _CaptureSidecar()

        self._settings_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "baseDir": str(self._tmp_dir / "base"),
                    "downloadsDir": str(self._tmp_dir / "downloads"),
                    "outputDir": str(self._tmp_dir / "output"),
                    "defaultDays": 7,
                    "importDownloads": True,
                    "quarantine": True,
                    "clientOutputDirs": {},
                    "updateUrl": "",
                    "telemetryOptIn": False,
                    "telemetryEndpoint": "",
                    "clientPresets": service._default_settings()["clientPresets"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        service.SETTINGS_FILE = self._orig_settings_file
        service.HISTORY_FILE = self._orig_history_file
        service.telemetry_sidecar = self._orig_sidecar
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _new_error_job(self, job_id: str = "job-telemetry-1") -> service.Job:
        job = service.Job(id=job_id, payload_input={"client": "Cliente Sigiloso", "days": 7})
        job.status = "error"
        job.started_at = "2026-05-26T12:00:00"
        job.finished_at = "2026-05-26T12:01:00"
        job.updated_at = "2026-05-26T12:01:00"
        job.error = "Falha ao processar arquivo C:\\Users\\User\\Secret\\Dados IA.xlsx"
        job.error_code = error_codes.ERR_PLANILHA_INVALIDA
        job.result = {"client": "Cliente Sigiloso", "generationKwh": 9999.99}
        return job

    def test_payload_telemetria_minimo_sem_dados_sensiveis(self):
        payload = service._build_job_error_telemetry_payload(self._new_error_job())
        self.assertEqual(
            set(payload.keys()),
            {"schema_version", "app_version", "job_id", "timestamp_inicio", "timestamp_fim", "error_code", "status"},
        )
        self.assertEqual(payload["schema_version"], telemetry.TELEMETRY_SCHEMA_VERSION)
        self.assertEqual(payload["status"], "error")

        raw = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("Cliente Sigiloso", raw)
        self.assertNotIn("C:\\Users\\User\\Secret", raw)
        self.assertNotIn("9999.99", raw)

    def test_optin_desligado_nao_envia(self):
        service.save_settings({"telemetryOptIn": False, "telemetryEndpoint": "https://collector.exemplo/telemetry"})
        service._emit_job_error_telemetry(self._new_error_job())
        self.assertEqual(service.telemetry_sidecar.calls, [])

    def test_optin_ativo_sem_endpoint_nao_envia(self):
        service.save_settings({"telemetryOptIn": True, "telemetryEndpoint": "   "})
        service._emit_job_error_telemetry(self._new_error_job())
        self.assertEqual(service.telemetry_sidecar.calls, [])

    def test_optin_ativo_com_endpoint_envia_payload_minimo(self):
        service.save_settings({"telemetryOptIn": True, "telemetryEndpoint": "https://collector.exemplo/telemetry"})
        service._emit_job_error_telemetry(self._new_error_job())

        self.assertEqual(len(service.telemetry_sidecar.calls), 1)
        endpoint, payload = service.telemetry_sidecar.calls[0]
        self.assertEqual(endpoint, "https://collector.exemplo/telemetry")
        self.assertEqual(
            set(payload.keys()),
            {"schema_version", "app_version", "job_id", "timestamp_inicio", "timestamp_fim", "error_code", "status"},
        )
        self.assertEqual(payload["job_id"], "job-telemetry-1")
        self.assertEqual(payload["error_code"], error_codes.ERR_PLANILHA_INVALIDA)

    def test_fluxo_falha_job_dispara_telemetria_sem_bloquear(self):
        service.save_settings({"telemetryOptIn": True, "telemetryEndpoint": "https://collector.exemplo/telemetry"})
        job = service.Job(id="job-failure-flow", payload_input={"client": "Cliente X", "days": 2, "importDownloads": False})

        with patch.object(service, "run_pipeline_sync", side_effect=RuntimeError("Falha forçada")):
            service.jobs._run(job, job.payload_input)

        self.assertEqual(job.status, "error")
        self.assertEqual(job.error_code, error_codes.ERR_EXECUCAO_PIPELINE)
        self.assertEqual(len(service.telemetry_sidecar.calls), 1)


class TelemetrySanitizationTests(unittest.TestCase):
    def test_sanitize_error_event_remove_campos_extras(self):
        sanitized = telemetry.sanitize_error_event(
            {
                "schema_version": 1,
                "app_version": "0.3.0",
                "job_id": "job-x-1",
                "timestamp_inicio": "2026-05-26T12:00:00",
                "timestamp_fim": "2026-05-26T12:01:00",
                "error_code": "ERR_PLANILHA_INVALIDA",
                "status": "error",
                "client": "Nome sigiloso",
                "valor": 123.45,
                "absolute_path": "C:\\Users\\User\\Secret\\dados.xlsx",
            }
        )
        self.assertIsNotNone(sanitized)
        sanitized = dict(sanitized or {})
        self.assertEqual(
            set(sanitized.keys()),
            {"schema_version", "app_version", "job_id", "timestamp_inicio", "timestamp_fim", "error_code", "status"},
        )
        self.assertNotIn("client", sanitized)
        self.assertNotIn("valor", sanitized)
        self.assertNotIn("absolute_path", sanitized)


if __name__ == "__main__":
    unittest.main()
