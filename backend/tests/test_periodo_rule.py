import unittest
from datetime import datetime, timedelta
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pipeline_core


def _parse_date(text):
    return datetime.strptime(text, "%d/%m/%Y")


class PeriodoRuleTests(unittest.TestCase):
    def test_periodo_usa_leitura_atual_menos_um(self):
        rows = [
            {
                "mes": "JAN/2026",
                "leitura_anterior": "03/01/2026",
                "leitura_atual": "02/02/2026",
                "energia_ativa_kwh": 1200,
                "energia_injetada_kwh": 600,
            }
        ]
        normalized = pipeline_core._normalizar_faturas_por_periodo(rows)
        item = normalized[0]
        start = _parse_date(item["leitura_anterior"])
        current = _parse_date(item["leitura_atual"])
        period_start, period_end = pipeline_core._parse_data_br(item["periodo"].split(" - ")[0]), pipeline_core._parse_data_br(item["periodo"].split(" - ")[1])
        self.assertEqual(start, period_start)
        self.assertEqual(period_end, current - timedelta(days=1))
        self.assertNotIn("period_rule_warning", item)

    def test_alerta_quando_mesmo_dia(self):
        rows = [
            {
                "mes": "JAN/2026",
                "leitura_anterior": "15/01/2026",
                "leitura_atual": "15/01/2026",
                "energia_ativa_kwh": 10,
                "energia_injetada_kwh": 5,
            }
        ]
        normalized = pipeline_core._normalizar_faturas_por_periodo(rows)
        item = normalized[0]
        self.assertEqual(item.get("period_rule_warning"), "PERIODO_SAME_DAY_OR_INVERTED")
        period_start = pipeline_core._parse_data_br(item["periodo"].split(" - ")[0])
        period_end = pipeline_core._parse_data_br(item["periodo"].split(" - ")[1])
        self.assertEqual(period_end, period_start - timedelta(days=1))


if __name__ == "__main__":
    unittest.main()
