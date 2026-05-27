import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import service


class ClientsListingTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="clients-listing-"))
        self._settings_file = self._tmp_dir / "settings.json"
        self._base_dir = self._tmp_dir / "clientes"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        (self._base_dir / "Zeta").mkdir()
        (self._base_dir / "Alpha").mkdir()
        (self._base_dir / "Beta cliente").mkdir()

        self._original_settings_file = service.SETTINGS_FILE
        service.SETTINGS_FILE = self._settings_file
        service.save_settings({"baseDir": str(self._base_dir)})

    def tearDown(self):
        service.SETTINGS_FILE = self._original_settings_file
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_list_clients_nao_depende_de_get_core(self):
        with patch.object(service, "get_core", side_effect=AssertionError("get_core nao deveria ser chamado")):
            result = service.list_clients()
        self.assertEqual(result["clients"], ["Alpha", "Beta cliente", "Zeta"])
        self.assertTrue(result["baseDirExists"])

    def test_list_clients_com_filtro(self):
        result = service.list_clients("beta")
        self.assertEqual(result["clients"], ["Beta cliente"])


if __name__ == "__main__":
    unittest.main()
