"""Dataset observacional: cobertura, procedencia y conservación de huecos."""
import unittest
from datetime import date, datetime, timezone
from football_ai_lab.market_history import build_market_history
from football_ai_lab.sources import LEAGUES

NOW=datetime(2026,11,16,12,tzinfo=timezone.utc)

class MarketHistoryTests(unittest.TestCase):
    def test_six_leagues_observation_and_missingness(self):
        histories={league:[] for league in LEAGUES}
        histories["SP2"]=[
            {"date":date(2026,11,15),"home":"Tenerife","away":"Ceuta",
             "home_goals":2,"away_goals":0,
             "home_corners":5,"away_corners":7,
             "home_shots":11,"away_shots":15,
             "home_on_target":5,"away_on_target":2,
             "home_yellow":2,"away_yellow":2,
             "home_red":0,"away_red":0,
             "home_fouls":None,"away_fouls":None},
            {"date":date(2026,11,15),"home":"CD Tenerife","away":"AD Ceuta",
             "home_goals":2,"away_goals":0}, # duplicado, no contar dos veces
            {"date":date(2026,11,18),"home":"A","away":"B",
             "home_goals":4,"away_goals":0}, # fecha futura, no contar
            {"date":date(2025,7,20),"home":"C","away":"D",
             "home_goals":4,"away_goals":0}, # fuera de ventana
        ]
        payload=build_market_history(histories,NOW)
        self.assertEqual(len(payload["cobertura"]),6)
        self.assertEqual(len(payload["partidos"]),1)
        match=payload["partidos"][0]
        self.assertEqual(match["goles_local"],2)
        self.assertEqual(match["resultado"],"1")
        self.assertEqual(match["estadisticas"]["corners"]["total"],12)
        self.assertEqual(match["estadisticas"]["shots"]["total"],26)
        self.assertIsNone(match["estadisticas"]["fouls"]["total"])
        self.assertEqual(match["estadisticas"]["red"]["total"],0)
        self.assertTrue(match["estadisticas"]["corners"]["fuentes"])
        self.assertEqual(payload["cobertura"]["Segunda División"]["partidos"],1)
        self.assertEqual(payload["cobertura"]["Segunda División"]["metricas"]["fouls"],0)

    def test_provenance_espn_and_one_sided_missing(self):
        source="https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/summary?event=123"
        histories={"SP1":[{
            "date":date(2026,11,14),"home":"Real Madrid","away":"Getafe",
            "home_goals":1,"away_goals":1,"home_fouls":13,"away_fouls":11,
            "home_corners":3,"away_corners":None,
            "fuentes_metricas":{"home_fouls":source,"away_fouls":source},
            "fuente_resultado":source,
        }]}
        m=build_market_history(histories,NOW)["partidos"][0]
        self.assertEqual(m["estadisticas"]["fouls"]["total"],24)
        self.assertEqual(m["estadisticas"]["fouls"]["fuentes"],[source])
        self.assertIsNone(m["estadisticas"]["corners"]["total"])
        self.assertEqual(m["estadisticas"]["corners"]["local"],3)
        self.assertIsNone(m["estadisticas"]["corners"]["visitante"])
        self.assertEqual(m["resultado"],"X")

    def test_no_bad_score_no_bogus_metrics(self):
        histories={"E0":[{
            "date":date(2026,11,14),"home":"Liverpool","away":"Chelsea",
            "home_goals":1,"away_goals":None,"home_corners":0,
            "away_corners":0}]}
        payload=build_market_history(histories,NOW)
        self.assertEqual(payload["partidos"],[])

    def test_no_naive_datetime(self):
        with self.assertRaises(ValueError):
            build_market_history({},datetime(2026,11,16))


if __name__=="__main__":
    unittest.main()
