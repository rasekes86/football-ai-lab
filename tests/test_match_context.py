import unittest
from datetime import date,datetime,timedelta,timezone
from football_ai_lab.sources import parse_history
from football_ai_lab.match_context import dossier,quality
from football_ai_lab.core import normalize_team

class ContextDetails(unittest.TestCase):
    def test_history_stat_columns_are_optional(self):
        sample=b"Date,HomeTeam,AwayTeam,FTHG,FTAG,HS,AS,HST,AST,HC,AC\n08/11/2026,Real Madrid,Celta,2,1,11,5,4,2,6,3\n"
        m=parse_history(sample)[0]
        self.assertEqual(m["home_shots"],11)
        self.assertEqual(m["away_corners"],3)
        self.assertIsNone(m["away_red"])
    def test_only_prior_results_count(self):
        when=datetime(2026,11,21,20,tzinfo=timezone.utc)
        hist=[{"date":when.date()-timedelta(days=i+1),
               "home":"Real Madrid","away":"Celta",
               "home_goals":2,"away_goals":0,"home_shots":9} for i in range(10)]
        future={"date":when.date()+timedelta(days=1),
                "home":"Real Madrid","away":"Celta","home_goals":0,"away_goals":99,
                "home_shots":0}
        f={"league":"SP1","kickoff":when,"home":"Real Madrid","away":"Celta"}
        x=dossier(hist,f);y=dossier(hist+[future],f)
        self.assertEqual(x,y)
        self.assertEqual(x["local_datos"]["v"],5)
        self.assertEqual(x["local_datos"]["medias"]["tiros"],9)
        self.assertEqual(x["local_datos"]["dias_descanso"],1)
        self.assertEqual(x["xg"]["estado"],"NO_DISPONIBLE_EN_CSV")
    def test_quality_does_not_guess_promoted_club(self):
        f=[{"date":date(2026,11,10),"home":"Real Madrid",
            "away":"Celta","home_goals":1,"away_goals":0}]
        q=quality(f,"Real Madrid","Racing Santander",date(2026,11,22))
        self.assertFalse(q["suficiente_modelo_actual"])
        self.assertFalse(q["equipos"]["visitante"]["identificado"])
    def test_aliases_never_fuzzy_match_random_team(self):
        self.assertNotEqual(normalize_team("Manchester City"),normalize_team("Manchester United"))
if __name__=="__main__":
    unittest.main()
