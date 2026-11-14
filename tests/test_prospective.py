import unittest
from datetime import date,datetime,timezone,timedelta
from football_ai_lab.prospective import evaluate,summarize

class ProspectiveTests(unittest.TestCase):
    def setUp(self):
        self.start=datetime(2026,11,20,20,0,tzinfo=timezone.utc)
        self.base={"id":"fix","fecha_utc":self.start.isoformat(),"liga":"LaLiga",
            "local":"Athletic Club","visitante":"Espanyol","prob_local":"0.55",
            "prob_empate":"0.25","prob_visitante":"0.20",
            "fecha_analisis_utc":(self.start-timedelta(days=4)).isoformat(),
            "tipo":"REAL","modelo":"ensemble-v0.2"}
        self.finished={"SP1":[{"date":date(2026,11,20),"home":"Ath Bilbao","away":"Espanol",
              "home_goals":2,"away_goals":1}]}
    def test_first_forecast_scored_after_final(self):
        tracked=evaluate([self.base],self.finished,self.start+timedelta(hours=4))
        self.assertEqual(tracked[0]["estado"],"FINALIZADO")
        self.assertEqual(tracked[0]["resultado_real"],"H")
        summary=summarize(tracked,self.start+timedelta(hours=4))
        self.assertEqual(summary["finalizados_validos"],1)
        self.assertEqual(summary["global"]["acierto_favorito_pct"],100.)
    def test_future_and_posthoc_cannot_score(self):
        now=self.start-timedelta(days=2)
        self.assertEqual(evaluate([self.base],self.finished,now)[0]["estado"],"PENDIENTE")
        copy=dict(self.base,fecha_analisis_utc=(self.start+timedelta(minutes=1)).isoformat())
        self.assertEqual(evaluate([copy],self.finished,self.start+timedelta(days=1))[0]["estado"],"EXCLUIDO_NO_PREPARTIDO")
        demo=dict(self.base,tipo="DEMO")
        self.assertEqual(evaluate([demo],self.finished,self.start+timedelta(days=1))[0]["estado"],"EXCLUIDO_NO_PREPARTIDO")
    def test_missing_result_not_assumed_lost(self):
        t=evaluate([self.base],{"SP1":[]},self.start+timedelta(days=2))
        self.assertEqual(t[0]["estado"],"RESULTADO_NO_DISPONIBLE")
        self.assertEqual(summarize(t,self.start+timedelta(days=2))["finalizados_validos"],0)
    def test_invalid_probabilities_excluded(self):
        p=dict(self.base,prob_empate="0.99")
        t=evaluate([p],self.finished,self.start+timedelta(days=1))
        self.assertEqual(t[0]["estado"],"EXCLUIDO_DATOS_INVALIDOS")
    def test_never_score_data_from_future(self):
        now=self.start-timedelta(days=1)
        p=dict(self.base,fecha_analisis_utc=(self.start+timedelta(days=2)).isoformat())
        self.assertTrue(evaluate([p],self.finished,now)[0]["estado"].startswith("EXCLUIDO"))
if __name__=="__main__":
    unittest.main()
