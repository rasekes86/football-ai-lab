"""Pruebas de auditoría temporal sin fuentes externas ni apuestas."""
import unittest
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
from football_ai_lab.count_validation import _score,_baseline,market_key,validate,VERSION
from football_ai_lab.selector import select_match,exploratory_counts

class CountValidationTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,14,20,tzinfo=timezone.utc)
        self.p={"id":"f1","liga":"LaLiga","fecha_utc":"2026-11-21T20:00:00+00:00",
                "local":"Real Madrid","visitante":"Celta Vigo","tipo":"REAL",
                "prob_local":"0.6","prob_empate":"0.25","prob_visitante":"0.15",
                "goles_esperados_local":"1.65","goles_esperados_visitante":"0.8"}

    def test_scoring_and_reference_baseline(self):
        scored=_score([1,0,1],[.9,.1,.8],[.6,.6,.6])
        self.assertLess(scored["brier_modelo"],scored["brier_referencia"])
        self.assertLess(scored["logloss_modelo"],scored["logloss_referencia"])
        self.assertEqual(_score([],[],[])["n"],0)

    def test_baseline_latest_only_and_no_future(self):
        first=date(2025,1,1)
        rows=[{"date":first+timedelta(days=i),"home_corners":1 if i<200 else 6,
               "away_corners":1 if i<200 else 6} for i in range(420)]
        recent=_baseline(rows,"corners",9.5)
        assert recent is not None
        old=_baseline(rows[:200],"corners",9.5)
        self.assertLess(recent,old)
        self.assertEqual(market_key("SP1","corners",9.5),"SP1|corners|9.5")

    def test_unapproved_corners_never_enter_top3(self):
        fake={"metrica":"corners","linea":9.5,"direccion":"menos",
              "mercado":"Córners totales","seleccion":"Menos de 9,5 córners totales",
              "familia":"exp_corners","probabilidad":.85,"cuota_justa":1/.85,
              "nivel":"EXPLORATORIO_NO_VALIDADO","origen":"Histórico",
              "motivo":"Datos de ensayo"}
        good={"version":VERSION,"calculado_utc":self.now.isoformat(),
              "aprobados":["SP1|corners|9.5"]}
        with patch("football_ai_lab.selector.exploratory_counts",return_value=[fake]):
            no=select_match(self.p,[],[],self.now)
            self.assertEqual(no["mercados_conteos_habilitados_retro"],0)
            self.assertFalse(any(x["mercado"]=="Córners totales" for x in no["top_probabilidad"]))
            yes=select_match(self.p,[],[],self.now,validation=good)
            self.assertEqual(yes["mercados_conteos_habilitados_retro"],1)
            self.assertTrue(any(x["mercado"]=="Córners totales" for x in yes["top_probabilidad"]))
            self.assertTrue(any(x["nivel"].startswith("BACKTEST_RETROSPECTIVO")
                                for x in yes["top_probabilidad"]))
            stale=dict(good,calculado_utc=(self.now-timedelta(days=9)).isoformat())
            self.assertEqual(select_match(self.p,[],[],self.now,validation=stale)
                             ["mercados_conteos_habilitados_retro"],0)

    def test_walk_forward_cannot_use_unobserved_stats(self):
        first=date(2023,1,1)
        hist=[{"date":first+timedelta(days=i),"home":"Real Madrid","away":"Celta Vigo",
               "home_goals":1,"away_goals":0,
               "home_corners":None,"away_corners":None} for i in range(280)]
        result=validate({"SP1":hist},self.now,max_games=40)
        self.assertEqual(result["aprobados"],[])
        self.assertEqual(result["por_liga"]["SP1"]["partidos_holdout"],40)
        self.assertEqual(result["por_liga"]["SP1"]["lineas"]["SP1|corners|9.5"]
                         ["partidos_con_resultado"],0)

    def test_exploratory_produces_metadata_and_uses_only_prior(self):
        first=date(2024,1,1)
        hist=[{"date":first+timedelta(days=i),"home":"Real Madrid","away":"Celta Vigo",
               "home_goals":2,"away_goals":1,
               "home_corners":5,"away_corners":4,
               "home_shots":10,"away_shots":7,
               "home_on_target":4,"away_on_target":2,
               "home_yellow":2,"away_yellow":2} for i in range(220)]
        d=date(2026,11,21)
        e=exploratory_counts(self.p,hist,d)
        self.assertGreater(len(e),0)
        self.assertTrue(any(x["metrica"]=="corners" and
                            x["linea"]==9.5 and x["direccion"]=="menos" for x in e))
        future=dict(hist[-1],date=d+timedelta(days=1),home_corners=100)
        self.assertEqual(e,exploratory_counts(self.p,hist+[future],d))
if __name__=="__main__":
    unittest.main()
