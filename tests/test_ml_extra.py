import unittest
from datetime import date
from football_ai_lab.ml import compare_to_production,_available_stat,feature_for_fixture

class AdvancedMLFeatures(unittest.TestCase):
    def test_missing_vs_zero(self):
        data=[(date(2026,11,1),1,1,1,None,0,3),
              (date(2026,11,2),2,0,3,8,1,4)]
        self.assertEqual(_available_stat(data,4),[8.,.5])
        self.assertEqual(_available_stat(data,5),[.5,1.])
    def test_disagreement_flag(self):
        ml=[{"fecha_utc":"2026-11-21T20:00:00+00:00","liga":"LaLiga",
             "local":"Real Madrid","visitante":"Celta Vigo",
             "ml_prob_local":"0.83","ml_prob_empate":"0.11","ml_prob_visitante":"0.06"}]
        base=[{"fecha_utc":"2026-11-21T20:00:00+00:00","liga":"LaLiga",
               "local":"Real Madrid","visitante":"Celta",
               "prob_local":"0.59","prob_empate":"0.24","prob_visitante":"0.17"}]
        r=compare_to_production(ml,base)
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]["alerta"],"REVISAR")
    def test_disagreement_requires_same_fixture(self):
        ml=[{"fecha_utc":"2026-11-21T20:00:00+00:00","liga":"LaLiga",
             "local":"Madrid","visitante":"Celta","ml_prob_local":"0.5","ml_prob_empate":"0.2","ml_prob_visitante":"0.3"}]
        self.assertEqual(compare_to_production(ml,[]),[])
if __name__=="__main__":
    unittest.main()
