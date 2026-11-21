"""La cuarta referencia del modelo jamás se confunde con cuota observada."""
from datetime import datetime, timedelta, timezone
import unittest
from football_ai_lab.fourth_reference import freeze, KIND

NOW = datetime(2026, 11, 21, 9, tzinfo=timezone.utc)
MATCH = {
    "id": "SP1|example", "tipo": "REAL", "liga": "LaLiga",
    "fecha_utc": (NOW+timedelta(days=1)).isoformat(),
    "local": "Equipo Local", "visitante": "Equipo Visitante",
    "goles_esperados_local": 1.4, "goles_esperados_visitante": 1.2,
    "prob_local": .42, "prob_empate": .29, "prob_visitante": .29,
}

class FourthReferenceTests(unittest.TestCase):
    def test_freeze_is_pre_game_distinct_and_unquoted(self):
        top = [{"id":MATCH["id"],"mercado":"Total goles","seleccion":"Más de 1,5 goles"}]
        rows=freeze([MATCH],[],top,NOW)
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["tipo_cuota"],KIND)
        self.assertEqual(r["cuota_decimal"],"")
        self.assertGreater(float(r["cuota_justa"]),1.5)
        self.assertLess(r["archivado_utc"],r["fecha_utc"])
        self.assertNotEqual((r["mercado"],r["seleccion"]),
                            (top[0]["mercado"],top[0]["seleccion"]))
        self.assertEqual(freeze([MATCH],rows,top,NOW+timedelta(minutes=1)),rows)
    def test_no_postmatch_creation(self):
        self.assertEqual(freeze([MATCH],[],[],NOW+timedelta(days=2)),[])

if __name__=="__main__":
    unittest.main()
