"""Pruebas de resultados finalizados, fuentes y protección de históricos."""
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from football_ai_lab.verified_results import augment_results
from football_ai_lab.value_watchlist import evaluate as evaluate_offers


class FinalResultsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 16, 11, tzinfo=timezone.utc)
        self.kickoff = datetime(2026, 11, 15, 13, tzinfo=timezone.utc)
        self.record = {
            "liga": "Segunda División", "local": "Tenerife", "visitante": "Ceuta",
            "fecha_utc": self.kickoff.isoformat(),
            "archivado_utc": (self.kickoff - timedelta(days=1)).isoformat(),
        }

    def _verified(self, directory):
        path = Path(directory) / "verified.json"
        path.write_text(json.dumps({"partidos": [{
            "liga_codigo": "SP2", "fecha": "2026-11-15",
            "local": "CD Tenerife", "visitante": "AD Ceuta FC",
            "goles_local": 2, "goles_visitante": 0, "estado": "FINALIZADO",
            "fuente_url": "https://www.laliga.com/es-GB/partido/temporada-2026-2027-test",
        }]}), encoding="utf-8")
        return path

    def test_official_result_and_original_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, audit = augment_results({"SP2": []}, [self.record], self.now,
                self._verified(tmp), fetcher=lambda u: b'{"events":[]}')
            self.assertEqual(audit["agregados_laliga"], 1)
            self.assertEqual(audit["sin_marcador"], 0)
            self.assertEqual((result["SP2"][0]["home_goals"], result["SP2"][0]["away_goals"]), (2, 0))

    def test_no_posthoc_or_future(self):
        invalid = dict(self.record, archivado_utc=(self.kickoff + timedelta(minutes=1)).isoformat())
        with tempfile.TemporaryDirectory() as tmp:
            path = self._verified(tmp)
            for row in (invalid, dict(self.record, fecha_utc=(self.now + timedelta(days=1)).isoformat())):
                result, audit = augment_results({"SP2":[]}, [row], self.now, path,
                    fetcher=lambda u: b'{"events":[]}')
                self.assertEqual(audit["objetivos"], 0)
                self.assertEqual(result["SP2"], [])

    def test_espn_only_full_time_correct_fixture(self):
        event = {"date": self.kickoff.isoformat(),
                 "status":{"type":{"name":"STATUS_FULL_TIME","completed":True}},
                 "competitions":[{"competitors":[
                    {"homeAway":"home","score":"2","team":{"displayName":"CD Tenerife"}},
                    {"homeAway":"away","score":"0","team":{"displayName":"AD Ceuta FC"}},
                 ]}]}
        with tempfile.TemporaryDirectory() as tmp:
            no_file = Path(tmp)/"missing.json"
            payload = json.dumps({"events":[event]}).encode()
            result, audit = augment_results({"SP2":[]}, [self.record], self.now, no_file,
                fetcher=lambda u: payload)
            self.assertEqual(audit["agregados_espn"], 1)
            self.assertEqual(result["SP2"][0]["home_goals"], 2)
            event["status"]["type"]["completed"] = False
            result, audit = augment_results({"SP2":[]}, [self.record], self.now, no_file,
                fetcher=lambda u: json.dumps({"events":[event]}).encode())
            self.assertEqual(audit["sin_marcador"], 1)

    def test_official_four_scores_and_simulated_return(self):
        repo_results = Path("data/resultados_finales_verificados.json")
        if not repo_results.is_file():
            self.skipTest("Datos de referencia ausentes")
        matches = [
            ("SP2|202611151730|eldense|sabadell","Eldense","CD Sabadell","2026-11-15T17:30:00+00:00","Total goles","Menos de 2,5 goles",0.63063,1.65),
            ("SP2|202611151300|tenerife|ceuta","Tenerife","Ceuta","2026-11-15T13:00:00+00:00","Total goles","Menos de 2,5 goles",0.57017,1.93),
            ("SP2|202611151515|granada|las palmas","Granada","Las Palmas","2026-11-15T15:15:00+00:00","Doble oportunidad","X2: empate o Las Palmas",0.57517,1.80),
            ("SP2|202611151730|eibar|cadiz","Eibar","Cádiz","2026-11-15T17:30:00+00:00","Total goles","Menos de 2,5 goles",0.50204,2.17),
        ]
        rows = []
        for ident, home, away, kickoff, market, label, prob, odd in matches:
            spec = ({"tipo":"doble","pick":"X2"} if market == "Doble oportunidad"
                    else {"tipo":"total","direccion":"Menos","linea":2.5})
            rows.append({"clave":ident+"|"+market+"|"+label,"id":ident,
                "liga":"Segunda División","local":home,"visitante":away,
                "fecha_utc":kickoff,"archivado_utc":"2026-11-15T00:47:52+00:00",
                "mercado":market,"seleccion":label,"familia":"resultado",
                "origen":"Modelo archivado","nivel":"EXPERIMENTAL",
                "probabilidad":str(prob),"cuota_justa":str(1/prob),
                "contrato":json.dumps(spec),"cuota_decimal":str(odd),
                "tipo_cuota":"INDICATIVA_NO_VERIFICADA","origen_cuota":"No verificada"})
        histories, audit = augment_results({"SP2":[]}, rows, self.now, repo_results,
            fetcher=lambda u: b'{"events":[]}')
        self.assertEqual(audit["agregados_laliga"], 4)
        settled, summary = evaluate_offers(rows, histories, self.now)
        self.assertEqual(summary["finalizadas"], 4)
        self.assertEqual(summary["global"]["aciertos"], 3)
        self.assertAlmostEqual(summary["global"]["retorno_simulado_unidad"], 1.75)
        self.assertEqual([x["resultado"] for x in settled], ["1","1","0","1"])


if __name__ == "__main__":
    unittest.main()
