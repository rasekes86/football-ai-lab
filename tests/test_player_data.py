import json
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from football_ai_lab.player_data import normalize_summary,collect

class PlayerSourceTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,14,20,tzinfo=timezone.utc)
        self.event={"event_id":"123","league":"SP1","fecha_utc":"2026-11-10T20:00:00+00:00",
                    "local":"Real Madrid","visitante":"Celta Vigo"}
        self.summary={"header":{"competitions":[{"competitors":[
             {"team":{"displayName":"Real Madrid"}},
             {"team":{"displayName":"Celta Vigo"}}]}]},
             "rosters":[{"team":{"displayName":"Real Madrid"},"roster":[
                 {"athlete":{"id":"34","displayName":"Jugador Ejemplo"},"starter":True,
                  "stats":[{"name":"shots","value":3},{"name":"shotsOnTarget","value":1},
                           {"name":"yellowCards","value":0}]}]}]}
    def test_real_stat_zero_vs_missing(self):
        rows=normalize_summary(self.summary,self.event)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["estadisticas"]["shots"],3)
        self.assertEqual(rows[0]["estadisticas"]["yellowCards"],0)
        self.assertNotIn("goals",rows[0]["estadisticas"])
        self.assertTrue(rows[0]["titular"])
    def test_other_match_never_assigned(self):
        self.summary["header"]["competitions"][0]["competitors"][0]["team"]["displayName"]="Barcelona"
        self.assertEqual(normalize_summary(self.summary,self.event),[])
    def test_no_data_without_activation(self):
        with patch.dict("os.environ",{"ENABLE_PLAYER_SAMPLE":"0"}):
            result=collect(self.now,reader=lambda _: (_ for _ in ()).throw(AssertionError))
        self.assertEqual(result["estado"],"DESACTIVADO")
        self.assertEqual(result["registros"],[])
if __name__=="__main__":unittest.main()
