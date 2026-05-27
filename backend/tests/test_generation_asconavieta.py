import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pipeline_core


class GenerationAsconavietaFormatTests(unittest.TestCase):
    def test_le_formato_estatisticas_diarias(self):
        df = pd.DataFrame(
            {
                "Nome da Instalação": ["Asconavieta", "Asconavieta"],
                "Tempo atualizado": ["2025/05/27", "2025/05/28"],
                "Fuso horário": ["UTC-03:00", "UTC-03:00"],
                "Hoje Produção(kWh)": ["2.10", "4.70"],
                "Rendimento(BRL)": ["", ""],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Asconavieta-Estatisticas-Diarias.xlsx"
            df.to_excel(path, index=False)
            rows = pipeline_core._processar_xlsx(path)

        self.assertEqual(2, len(rows))
        self.assertEqual("2025-05-27", pd.to_datetime(rows[0]["data"]).date().isoformat())
        self.assertAlmostEqual(2.10, rows[0]["kwh"], places=2)
        self.assertEqual("2025-05-28", pd.to_datetime(rows[1]["data"]).date().isoformat())
        self.assertAlmostEqual(4.70, rows[1]["kwh"], places=2)


if __name__ == "__main__":
    unittest.main()
