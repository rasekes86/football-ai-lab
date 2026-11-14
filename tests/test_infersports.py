import unittest
from datetime import datetime,timezone
from football_ai_lab.infersports import parse_fair,merge_infer_prices

class InferSportsTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,14,12,tzinfo=timezone.utc)
        self.p={"id":"match1","liga":"LaLiga","local":"Athletic Club","visitante":"Espanyol",
                "fecha_utc":"2026-11-20T20:00:00+00:00","prob_local":"0.44",
                "prob_empate":"0.28","prob_visitante":"0.28"}
        self.d={"status":"ok","stale":False,"match":{"home_team":"Athletic Club","away_team":"Espanyol"},
                "comparison":{"market_type":"1x2","stale":False,"as_of":"2026-11-14T11:59:00Z",
                               "fair_odds":{"home":2.5,"draw":3.3333333333,"away":3.3333333333},
                               "fair_from":"TestBook"}}
    def test_fair_reference(self):
        value=parse_fair(self.d,self.p,self.now)
        self.assertIsNotNone(value)
        self.assertAlmostEqual(sum(value["fair"]),1,places=8)
        rows=merge_infer_prices([{"id":"match1","estado":"PROVEEDOR_DESACTIVADO"}],{"match1":value},[self.p])
        self.assertEqual(rows[0]["estado"],"REFERENCIA_INFERSPORTS_SIN_VALIDAR")
        self.assertEqual(rows[0].get("cuota_local"),None)
    def test_reject_stale_and_wrong_fixture(self):
        self.assertIsNone(parse_fair(self.d,self.p,self.now.replace(day=16)))
        self.d["match"]["away_team"]="Otro equipo"
        self.assertIsNone(parse_fair(self.d,self.p,self.now))
    def test_reject_non_normalized_odds(self):
        self.d["comparison"]["fair_odds"]={"home":1.2,"draw":2.,"away":3.}
        self.assertIsNone(parse_fair(self.d,self.p,self.now))

if __name__=="__main__":
    unittest.main()
