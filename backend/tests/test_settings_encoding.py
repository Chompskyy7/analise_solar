import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import service


class SettingsEncodingTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="settings-encoding-"))
        self._settings_file = self._tmp_dir / "settings.json"
        self._original_settings_file = service.SETTINGS_FILE
        service.SETTINGS_FILE = self._settings_file

    def tearDown(self):
        service.SETTINGS_FILE = self._original_settings_file
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_get_settings_ler_json_utf8_bom(self):
        payload = {
            "schema_version": 1,
            "baseDir": "H:\\dados\\Analise de geração",
            "downloadsDir": "C:\\Users\\User\\Downloads",
            "defaultDays": 11,
            "quarantine": False,
        }
        self._settings_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8-sig")

        settings = service.get_settings()

        self.assertEqual(settings["baseDir"], payload["baseDir"])
        self.assertEqual(settings["downloadsDir"], payload["downloadsDir"])
        self.assertEqual(settings["defaultDays"], payload["defaultDays"])
        self.assertFalse(settings["quarantine"])

    def test_get_settings_ler_json_cp1252(self):
        payload = {"schema_version": 1, "baseDir": "C:\\Analise de geração", "defaultDays": 9}
        raw = json.dumps(payload, ensure_ascii=False).encode("cp1252")
        self._settings_file.write_bytes(raw)

        settings = service.get_settings()

        self.assertEqual(settings["baseDir"], payload["baseDir"])
        self.assertEqual(settings["defaultDays"], payload["defaultDays"])


class SettingsSchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="settings-schema-migration-"))
        self._settings_file = self._tmp_dir / "settings.json"
        self._history_file = self._tmp_dir / "history.json"
        self._original_settings_file = service.SETTINGS_FILE
        self._original_history_file = service.HISTORY_FILE
        service.SETTINGS_FILE = self._settings_file
        service.HISTORY_FILE = self._history_file

    def tearDown(self):
        service.SETTINGS_FILE = self._original_settings_file
        service.HISTORY_FILE = self._original_history_file
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_settings_legacy_sem_schema_migra_com_bak(self):
        legacy = {"baseDir": "C:\\Legacy\\Base", "defaultDays": 33, "quarantine": False}
        self._settings_file.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

        settings = service.get_settings()

        self.assertEqual(settings["baseDir"], service._default_settings()["baseDir"])
        self.assertEqual(settings["defaultDays"], service._default_settings()["defaultDays"])
        self.assertEqual(settings["quarantine"], service._default_settings()["quarantine"])

        backup = self._settings_file.with_suffix(".json.bak")
        self.assertTrue(backup.exists())
        self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), legacy)

        migrated = json.loads(self._settings_file.read_text(encoding="utf-8"))
        self.assertEqual(migrated["schema_version"], 1)
        self.assertEqual(migrated["baseDir"], service._default_settings()["baseDir"])

    def test_history_legacy_sem_schema_migra_com_bak(self):
        legacy = [{"id": "job-1", "status": "done"}]
        self._history_file.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

        result = service.list_history()

        self.assertEqual(result["items"], [])
        backup = self._history_file.with_suffix(".json.bak")
        self.assertTrue(backup.exists())
        self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), legacy)

        migrated = json.loads(self._history_file.read_text(encoding="utf-8"))
        self.assertEqual(migrated["schema_version"], 1)
        self.assertEqual(migrated["items"], [])

    def test_settings_schema_desconhecido_retorna_erro_e_nao_sobrescreve(self):
        unknown = {"schema_version": 99, "baseDir": "C:\\NaoPodeSobrescrever"}
        self._settings_file.write_text(json.dumps(unknown, ensure_ascii=False), encoding="utf-8")

        with self.assertRaises(service.StorageSchemaError) as ctx:
            service.get_settings()

        self.assertIn("schema_version desconhecido", str(ctx.exception))
        self.assertEqual(json.loads(self._settings_file.read_text(encoding="utf-8")), unknown)
        self.assertFalse(self._settings_file.with_suffix(".json.bak").exists())

    def test_history_schema_desconhecido_retorna_erro_e_preserva_arquivo(self):
        unknown = {"schema_version": 7, "items": [{"id": "legado"}]}
        self._history_file.write_text(json.dumps(unknown, ensure_ascii=False), encoding="utf-8")

        with self.assertRaises(service.StorageSchemaError) as ctx:
            service.list_history()

        self.assertIn("schema_version desconhecido", str(ctx.exception))
        self.assertEqual(json.loads(self._history_file.read_text(encoding="utf-8")), unknown)
        self.assertFalse(self._history_file.with_suffix(".json.bak").exists())


if __name__ == "__main__":
    unittest.main()
