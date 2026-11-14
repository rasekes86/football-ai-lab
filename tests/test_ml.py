"""Verifica la causalidad de las features sin necesitar instalar XGBoost."""
import unittest
from datetime import date,datetime,timedelta,timezone
from football_ai_lab.ml import build_samples,feature_for_fixture,split_by_date,score

class MLTemporalTests(unittest.TestCase):
    def sample(self):
        teams=["Arsenal","Chelsea","Fulham","Liverpool"]
        first=date(2023,1,1)
        games=[]
        for i in range(520):
            h=teams[i%4];a=teams[(i+1+(i//4)%3)%4]
            if h==a:a=teams[(i+1)%4]
            games.append({"date":first+timedelta(days=i),"home":h,"away":a,
                          "home_goals":i%4,"away_goals":(i+1)%3})
        return games
    def test_same_day_future_cannot_change_training_features(self):
        original=self.sample()
        features=build_samples({"E0":original})
        changed=[dict(x) for x in original]
        changed[-1]["home_goals"]=0
        changed[-1]["away_goals"]=45
        new=build_samples({"E0":changed})
        self.assertEqual(len(features),len(new))
        self.assertEqual(features[-1][2],new[-1][2])
        self.assertNotEqual(features[-1][3],new[-1][3])
    def test_future_outcome_does_not_change_fixture_features(self):
        original=self.sample()
        f={"league":"E0","kickoff":datetime(2023,10,1,tzinfo=timezone.utc),
           "home":"Arsenal","away":"Chelsea"}
        before=feature_for_fixture({"E0":original},f)
        mutated=[dict(x) for x in original]
        mutated[-1]["home_goals"]=500
        self.assertEqual(before,feature_for_fixture({"E0":mutated},f))
        self.assertIsNotNone(before)
    def test_split_keeps_dates_disjoint(self):
        train,test,boundary=split_by_date(build_samples({"E0":self.sample()}))
        self.assertTrue(train and test)
        self.assertLess(max(r[0] for r in train),boundary)
        self.assertGreaterEqual(min(r[0] for r in test),boundary)
    def test_scores(self):
        self.assertAlmostEqual(score([0,1],[[1.,0.,0.],[0.,1.,0.]])["brier"],0.)
        self.assertGreater(score([0],[[0.1,0.6,0.3]])["logloss"],0.)

if __name__=="__main__":
    unittest.main()
