import unittest
from datetime import date, datetime, timedelta, timezone
import json
from football_ai_lab.core import normalize_team, probabilities, estimate_goals
from football_ai_lab.pipeline import forecast, evaluate
from football_ai_lab.sources import parse_date, parse_history, season_codes, parse_espn_events

class ModelTests(unittest.TestCase):
    def test_probabilities(self):
        for h,a in [(1.2,0.9),(2.4,1.5),(0.4,0.7)]:
            p=probabilities(h,a)
            self.assertAlmostEqual(sum(p[k] for k in ("home","draw","away")),1,places=8)
            self.assertTrue(all(0<x<1 for x in p.values()))
    def test_name_alias(self):
        self.assertEqual(normalize_team("Atlético de Madrid"),normalize_team("Ath Madrid"))
        self.assertEqual(normalize_team("Manchester City"),normalize_team("Man City"))
    def test_csv_parsing(self):
        b=b"Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nE0,04/11/2026,Arsenal,Chelsea,2,0,H\nE0,05/11/2026,Arsenal,Chelsea,,,\n"
        self.assertEqual(len(parse_history(b)),1)
    def test_espn_fixture(self):
        later=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()
        b=json.dumps({"events":[{"id":"abc","date":later,"status":{"type":{"name":"STATUS_SCHEDULED"}},"competitions":[{"competitors":[{"homeAway":"home","team":{"displayName":"Barcelona"}},{"homeAway":"away","team":{"displayName":"Real Madrid"}}]}]}]}).encode()
        self.assertEqual(len(parse_espn_events(b,"SP1",date.today())),1)
    def test_no_future_leakage(self):
        d=date(2026,10,1)
        h=[{"date":d-timedelta(days=i+1),"home":"Arsenal","away":"Chelsea","home_goals":1,"away_goals":0} for i in range(22)]
        h += [{"date":d+timedelta(days=1),"home":"Arsenal","away":"Chelsea","home_goals":19,"away_goals":19}]
        self.assertEqual(estimate_goals(h,"Arsenal","Chelsea",d),estimate_goals(h[:-1],"Arsenal","Chelsea",d))
    def test_season_code(self):
        self.assertEqual(season_codes(date(2026,11,14),2),["2526","2627"])

if __name__ == "__main__":
    unittest.main()
