"""Radar: solo datos anteriores al encuentro, sedes y métricas no inventadas."""
import unittest
from datetime import date, datetime, timezone
from football_ai_lab.radar_context import build_radar_context
from football_ai_lab.sources import LEAGUES

NOW=datetime(2026,11,16,12,tzinfo=timezone.utc)
START="2026-11-20T20:00:00+00:00"
FIXTURE={"id":"SP2|202611202000|tenerife|ceuta","liga":"Segunda División",
         "local":"Tenerife","visitante":"Ceuta","fecha_utc":START}


def game(when,home,away,hg,ag,**extra):
    return {"date":date.fromisoformat(when),"home":home,"away":away,
            "home_goals":hg,"away_goals":ag,**extra}


class RadarContextTests(unittest.TestCase):
    def test_recent_venues_windows_and_goals(self):
        matches=[
            game("2026-11-10","CD Tenerife","AD Ceuta",2,1,
                 home_corners=6,away_corners=4,home_shots=13,away_shots=8),
            game("2026-11-05","Mallorca","CD Tenerife",0,1,
                 home_corners=3,away_corners=2),
            game("2026-11-03","CD Tenerife","Cadiz",1,1,
                 home_corners=7,away_corners=6),
            game("2026-11-01","AD Ceuta","Zaragoza",2,0,
                 home_corners=5,away_corners=3),
            game("2026-10-29","Burgos","AD Ceuta",1,1,
                 home_corners=4,away_corners=4),
        ]
        data=build_radar_context({"SP2":matches},[FIXTURE],NOW)
        self.assertEqual(len(data["partidos"]),1)
        home=data["partidos"][0]["equipos"]["local"]
        away=data["partidos"][0]["equipos"]["visitante"]
        self.assertEqual(home["overall"]["5"]["matches"],3)
        self.assertEqual(home["venue_only"]["5"]["matches"],2)
        self.assertEqual(home["overall"]["5"]["wins"],2)
        self.assertEqual(home["venue_only"]["5"]["draws"],1)
        self.assertEqual(home["overall"]["5"]["metrics"]["corners"]["n"],3)
        self.assertEqual(home["venue_only"]["5"]["metrics"]["corners"]["values"],[10,13])
        self.assertEqual(away["venue_only"]["5"]["matches"],2)
        self.assertEqual(away["venue_only"]["5"]["metrics"]["corners"]["values"],[10,8])
        self.assertEqual(home["overall"]["20"]["matches"],3)

    def test_same_day_and_future_result_never_leak(self):
        entries=[
            game("2026-11-19","CD Tenerife","Getafe",0,1),
            game("2026-11-20","CD Tenerife","AD Ceuta",12,0,
                 home_corners=20,away_corners=40),
            game("2026-11-21","CD Tenerife","Sevilla",5,0),
        ]
        row=build_radar_context({"SP2":entries},[FIXTURE],NOW)["partidos"][0]
        self.assertEqual(row["equipos"]["local"]["overall"]["20"]["matches"],1)
        self.assertEqual(row["equipos"]["local"]["overall"]["20"]["goals_for"],0)
        self.assertIsNone(row["equipos"]["local"]["overall"]["20"]["metrics"]["corners"]["mean"])

    def test_missing_and_valid_zero_distinct(self):
        entries=[
            game("2026-11-18","CD Tenerife","Elche",0,0,
                 home_corners=0,away_corners=0,home_yellow=None,away_yellow=2),
            game("2026-11-15","CD Tenerife","Granada",2,1,
                 home_corners=4,away_corners=None),
            game("2026-11-01","CD Tenerife","Malaga",2,1,
                 home_corners=1,away_corners=3),
        ]
        row=build_radar_context({"SP2":entries},[FIXTURE],NOW)["partidos"][0]["equipos"]["local"]["overall"]["5"]
        self.assertEqual(row["metrics"]["corners"]["values"],[0,None,4])
        self.assertEqual(row["metrics"]["corners"]["n"],2)
        self.assertEqual(row["metrics"]["corners"]["mean"],2)
        self.assertEqual(row["metrics"]["yellow"]["n"],0)
        self.assertIsNone(row["metrics"]["yellow"]["mean"])
        self.assertEqual(row["metrics"]["goals"]["n"],3)

    def test_repeated_source_match_doesnt_count_twice(self):
        duplicated=game("2026-11-10","CD Tenerife","AD Ceuta",2,1)
        data=build_radar_context({"SP2":[duplicated,duplicated]},[FIXTURE],NOW)
        self.assertEqual(data["partidos"][0]["equipos"]["local"]["overall"]["10"]["matches"],1)

    def test_no_history_wrong_competition_no_fantasy(self):
        data=build_radar_context({"SP1":[game("2026-11-10","CD Tenerife","Elche",1,1)]},
                                 [FIXTURE],NOW)
        self.assertEqual(data["partidos"][0]["equipos"]["local"]["overall"]["10"]["matches"],0)
        self.assertEqual(data["partidos"][0]["equipos"]["visitante"]["overall"]["10"]["matches"],0)
        self.assertEqual(len(LEAGUES),6)

    def test_timestamp_and_no_prior_forecast(self):
        invalid=[dict(FIXTURE,fecha_utc="2026-11-15T20:00:00+00:00"),
                 dict(FIXTURE,id="x",fecha_utc="2026-11-20T19:00:00")]
        self.assertEqual(build_radar_context({},invalid,NOW)["partidos"],[])
        with self.assertRaises(ValueError):
            build_radar_context({},[FIXTURE],datetime(2026,11,16))

if __name__=="__main__":
    unittest.main()
