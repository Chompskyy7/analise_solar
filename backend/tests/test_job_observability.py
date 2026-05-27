import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import error_codes, service


class JobObservabilityTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="job-observability-"))
        self._settings_file = self._tmp_dir / "settings.json"
        self._history_file = self._tmp_dir / "history.json"
        self._support_dir = self._tmp_dir / "support"

        self._orig_settings_file = service.SETTINGS_FILE
        self._orig_history_file = service.HISTORY_FILE
        self._orig_support_dir = service.SUPPORT_DIR

        service.SETTINGS_FILE = self._settings_file
        service.HISTORY_FILE = self._history_file
        service.SUPPORT_DIR = self._support_dir

        self._settings_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "baseDir": "C:\\Users\\User\\Secret\\Clientes",
                    "downloadsDir": "C:\\Users\\User\\Secret\\Downloads",
                    "outputDir": "C:\\Users\\User\\Secret\\Out",
                    "defaultDays": 7,
                    "importDownloads": True,
                    "quarantine": True,
                    "clientOutputDirs": {"Cliente Sigiloso": "C:\\Users\\User\\Secret\\Out\\Cliente"},
                    "apiToken": "token-super-secreto",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        service.SETTINGS_FILE = self._orig_settings_file
        service.HISTORY_FILE = self._orig_history_file
        service.SUPPORT_DIR = self._orig_support_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _new_done_job(self, job_id: str, output_path: Path) -> service.Job:
        job = service.Job(id=job_id)
        job.status = "done"
        job.started_at = "2026-05-26T10:00:00"
        job.finished_at = "2026-05-26T10:01:00"
        job.updated_at = "2026-05-26T10:01:00"
        job.error_code = error_codes.OK
        job.result = {
            "client": "Cliente Sigiloso",
            "output": str(output_path),
            "outputSha256": service._sha256_file(output_path),
            "generationKwh": 1234.56,
        }
        return job

    def test_history_persiste_hash_e_detecta_drift(self):
        output_a = self._tmp_dir / "a.xlsx"
        output_b = self._tmp_dir / "b.xlsx"
        output_a.write_bytes(b"conteudo-a")
        output_b.write_bytes(b"conteudo-b")

        job1 = self._new_done_job("job-1", output_a)
        service.jobs._append_job_history(job1)

        history_after_first = service._read_history()
        self.assertEqual(history_after_first[0]["outputSha256"], service._sha256_file(output_a))
        self.assertFalse(history_after_first[0]["hashComparison"]["hasPrevious"])
        self.assertIsNone(history_after_first[0]["hashDrift"])

        job2 = self._new_done_job("job-2", output_b)
        service.jobs._append_job_history(job2)
        history = service._read_history()
        latest = history[0]

        self.assertEqual(latest["job_id"], "job-2")
        self.assertEqual(latest["outputSha256"], service._sha256_file(output_b))
        self.assertTrue(latest["hashComparison"]["hasPrevious"])
        self.assertEqual(latest["hashComparison"]["previousJobId"], "job-1")
        self.assertTrue(latest["hashDrift"])
        self.assertEqual(latest["jobLog"]["error_code"], error_codes.OK)
        self.assertEqual(latest["jobLog"]["job_id"], "job-2")
        self.assertEqual(latest["jobLog"]["timestamp_inicio"], "2026-05-26T10:00:00")
        self.assertEqual(latest["jobLog"]["timestamp_fim"], "2026-05-26T10:01:00")

    def test_export_diagnostico_por_job_redige_sensiveis_por_padrao(self):
        self._history_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "items": [
                        {
                            "job_id": "job-export-1",
                            "id": "job-export-1",
                            "status": "done",
                            "started_at": "2026-05-26T11:00:00",
                            "finished_at": "2026-05-26T11:01:00",
                            "updatedAt": "2026-05-26T11:01:00",
                            "client": "Cliente Sigiloso",
                            "errorCode": "OK",
                            "outputSha256": "abc123",
                            "hashComparison": {"hasPrevious": False, "drift": None},
                            "jobLog": {
                                "job_id": "job-export-1",
                                "timestamp_inicio": "2026-05-26T11:00:00",
                                "timestamp_fim": "2026-05-26T11:01:00",
                                "error_code": "OK",
                                "stack_trace_sanitizado": None,
                            },
                            "logs": "Cliente: Cliente Sigiloso\nAtivo: 999 kWh\nArquivo: C:\\Users\\User\\Secret\\Dados IA.xlsx\n[IMPORT] Importando arquivos recentes.\n",
                            "generationKwh": 9999.99,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        exported = service.export_support_package({"job_id": "job-export-1"})
        self.assertTrue(exported["ok"])
        archive_path = Path(exported["path"])
        self.assertTrue(archive_path.exists())

        with zipfile.ZipFile(archive_path, "r") as archive:
            names = archive.namelist()
            self.assertIn("manifest.json", names)
            self.assertIn("diagnostico.job.json", names)
            self.assertIn("logs-job-export-1.txt", names)
            diagnostics_raw = archive.read("diagnostico.job.json").decode("utf-8")
            logs_raw = archive.read("logs-job-export-1.txt").decode("utf-8")

        diagnostics = json.loads(diagnostics_raw)
        self.assertEqual(diagnostics["job"]["job_id"], "job-export-1")
        self.assertEqual(diagnostics["app"]["version"], service.APP_VERSION)
        self.assertEqual(diagnostics["schema_version"]["settings"]["expected"], 1)
        self.assertEqual(diagnostics["schema_version"]["history"]["expected"], 1)
        self.assertNotIn("Cliente Sigiloso", diagnostics_raw)
        self.assertNotIn("C:\\Users\\User\\Secret", diagnostics_raw)
        self.assertNotIn("generationKwh", diagnostics_raw)
        self.assertNotIn("token-super-secreto", diagnostics_raw)
        self.assertNotIn("Cliente Sigiloso", logs_raw)
        self.assertNotIn("C:\\Users\\User\\Secret", logs_raw)
        self.assertNotIn("kWh", logs_raw)

    def test_classificacao_codigo_erro_padronizado(self):
        self.assertEqual(
            service._error_code_from_message("Nenhum arquivo encontrado para processar."),
            error_codes.ERR_ARQUIVO_NAO_ENCONTRADO,
        )
        self.assertEqual(
            error_codes.classify_error("Fim do periodo nao corresponde a leitura atual - 1 dia."),
            error_codes.ERR_PERIODO_INVALIDO,
        )


if __name__ == "__main__":
    unittest.main()
