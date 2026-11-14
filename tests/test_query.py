import unittest
from datetime import date,datetime,timezone
from football_ai_lab.query import parse_request,select_match,reply

class OnDemandTests(unittest.TestCase):
    def test_title(self):
        self.assertEqual(parse_request("[ANALISIS] Athletic Club vs Espanyol | 2026-11-20"),
                         ("Athletic Club","Espanyol",date(2026,11,20)))
        self.assertIsNone(parse_request("[ANALISIS] A vs B | 2026-02-30"))
        self.assertIsNone(parse_request("rm -rf"))
    def test_match_validation(self):
        fixture={"league":"E0","home":"Manchester City","away":"Fulham",
                 "kickoff":datetime(2026,11,21,12,30,tzinfo=timezone.utc)}
        self.assertEqual(select_match([fixture],"Man City","Fulham",date(2026,11,21)),[fixture])
        self.assertFalse(select_match([fixture],"Fulham","Man City",date(2026,11,21)))
    def test_missing_match_never_invents(self):
        text=reply("[ANALISIS] Barcelona vs Madrid | 2026-11-20",
             now=datetime(2026,11,14,tzinfo=timezone.utc),fixtures=[])
        self.assertIn("No hay una coincidencia",text)
        self.assertNotIn("Probabilidad:",text)
if __name__=="__main__":
    unittest.main()
