import unittest
from datetime import datetime,timezone
from football_ai_lab.context_machina import collect,summarize_standings,summarize_missing

def ok(data): return {"status":True,"data":data}

class Fake:
    def get_current_season(self,*,competition_id):
        return ok({"season":{"id":competition_id+"-2026"}})
    def get_season_standings(self,*,season_id):
        return ok({"standings":[{"entries":[{"team":{"name":"Arsenal"},"position":1,"points":30,"played":12}]}]})
    def get_missing_players(self,*,season_id):
        return ok({"teams":[{"team":{"name":"Arsenal"},"players":[{"status":"injured"},{"status":"doubtful"}]}]})

class ContextTests(unittest.TestCase):
    def test_summary(self):
        l=summarize_standings(Fake().get_season_standings(season_id="premier-league-2026"))
        self.assertEqual(l[0]["nombre"],"Arsenal")
        missing=summarize_missing(Fake().get_missing_players(season_id="premier-league-2026"))
        self.assertEqual(missing[0]["bajas_reportadas"],2)
    def test_offline_mock(self):
        result=collect(datetime(2026,11,14,tzinfo=timezone.utc),football=Fake())
        self.assertEqual(len(result["clasificaciones"]),5)
        self.assertEqual(result["estado"],"PARCIAL")
        self.assertEqual(result["bajas_premier"][0]["estados"]["injured"],1)
    def test_bad_payload_never_invents(self):
        self.assertEqual(summarize_standings({"status":False,"data":{}}),[])
if __name__=="__main__":
    unittest.main()
