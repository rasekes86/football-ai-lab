"""Segunda División: cobertura de datos, equipos, aislamiento y mercados opcionales."""
import unittest
from datetime import date
from football_ai_lab.sources import LEAGUES,parse_history,parse_espn_events,HISTORY_URL,ESPN_URL
from football_ai_lab.core import normalize_team
from football_ai_lab.odds import get_optional_quotes,build_market_rows

class SegundaDivisionTests(unittest.TestCase):
    def test_source_codes(self):
        self.assertEqual(LEAGUES["SP2"],("Segunda División","esp.2"))
        self.assertIn("/2627/SP2.csv",HISTORY_URL.format(season="2627",league="SP2"))
        self.assertIn("/esp.2/scoreboard",ESPN_URL.format(code=LEAGUES["SP2"][1]))
    def test_aliases_avoid_confusing_reserve_and_senior_team(self):
        self.assertEqual(normalize_team("Real Sociedad II"),normalize_team("Real Sociedad B"))
        self.assertNotEqual(normalize_team("Real Sociedad II"),normalize_team("Real Sociedad"))
        self.assertEqual(normalize_team("CD Castellón"),normalize_team("Castellon"))
        self.assertEqual(normalize_team("Cultural Leonesa"),normalize_team("Cult Leonesa"))
        self.assertEqual(normalize_team("Real Sporting"),normalize_team("Sp Gijon"))
        self.assertEqual(normalize_team("Real Zaragoza"),normalize_team("Zaragoza"))
    def test_historical_sp2_csv(self):
        csv=b"Date,HomeTeam,AwayTeam,FTHG,FTAG,HS,AS,HST,AST,HC,AC,HY,AY\n12/11/2026,Zaragoza,Albacete,1,0,8,9,3,4,6,5,1,3\n"
        rows=parse_history(csv)
        self.assertEqual(rows[0]["home_goals"],1)
        self.assertEqual(rows[0]["away_shots"],9)
        self.assertEqual(rows[0]["home_corners"],6)
    def test_missing_bookmaker_not_an_error(self):
        from datetime import datetime,timezone
        from unittest.mock import patch
        with patch.dict("os.environ",{"ENABLE_ODDS":"0","THE_ODDS_API_KEY":""}):
            self.assertEqual(get_optional_quotes(["SP2"]),{})
        preds=[{"id":"test","fecha_utc":"2026-11-21T18:00:00+00:00",
                "liga":"Segunda División","local":"Zaragoza","visitante":"Albacete"}]
        rows=build_market_rows(preds,{},datetime(2026,11,14,tzinfo=timezone.utc))
        self.assertEqual(rows[0]["estado"],"PROVEEDOR_DESACTIVADO")
if __name__=="__main__": unittest.main()
