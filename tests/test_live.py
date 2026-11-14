import unittest
from datetime import datetime,date,timezone
from football_ai_lab.live import parse_live_request,validate_snapshot,live_reply

class LiveTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,21,16,10,tzinfo=timezone.utc)
        self.raw={"status":"ok","stale":False,"as_of":"2026-11-21T16:09:15Z",
                  "match":{"home_team":"Manchester City","away_team":"Fulham",
                           "scheduled_at":"2026-11-21T15:00:00Z","status":"live",
                           "score":{"home":2,"away":1},"clock":"71",
                           "red_cards":{"home":0,"away":0}},
                  "implied_probabilities":{"home":0.71,"draw":0.20,"away":0.09}}
    def test_live_parsing(self):
        self.assertEqual(parse_live_request("[DIRECTO] Man City vs Fulham | 2026-11-21"),
                         ("Man City","Fulham",date(2026,11,21)))
        self.assertIsNone(parse_live_request("[DIRECTO] A vs B | 2026-02-30"))
    def test_live_snapshot(self):
        value,err=validate_snapshot(self.raw,"Man City","Fulham",date(2026,11,21),self.now)
        self.assertIsNone(err)
        self.assertEqual(value["score"]["home"],2)
        self.assertIn("2–1",live_reply("[DIRECTO] Man City vs Fulham | 2026-11-21",self.now,self.raw))
    def test_stale_and_wrong_team(self):
        _,err=validate_snapshot(self.raw,"Man City","Fulham",date(2026,11,21),
                                datetime(2026,11,21,18,tzinfo=timezone.utc))
        self.assertIn("antigua",err)
        _,err=validate_snapshot(self.raw,"Arsenal","Fulham",date(2026,11,21),self.now)
        self.assertIn("coinciden",err)
    def test_no_inplay_if_not_live(self):
        self.raw["match"]["status"]="scheduled"
        text=live_reply("[DIRECTO] Man City vs Fulham | 2026-11-21",self.now,self.raw)
        self.assertIn("scheduled",text)
        self.assertNotIn("71.0%",text)

if __name__=="__main__":
    unittest.main()
