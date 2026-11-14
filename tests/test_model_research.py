import unittest
from datetime import date,timedelta
from football_ai_lab.model_research import validate,blend,score,observations

class WeightAuditTests(unittest.TestCase):
    def samples(self):
        start=date(2025,1,1)
        p={"home":.5,"draw":.25,"away":.25}
        e={"home":.6,"draw":.2,"away":.2}
        return [(start+timedelta(days=i),i%3,p,e) for i in range(180)]
    def test_validation_has_separate_future_holdout(self):
        result=validate(self.samples())
        self.assertEqual(result["estado"],"COMPARACION_COMPLETADA")
        self.assertFalse(result["se_aplica_automaticamente"])
        self.assertEqual(result["peso_produccion"],.30)
        self.assertGreater(result["prueba_posterior"],40)
    def test_candidate_scoring(self):
        p={"home":.5,"draw":.25,"away":.25}
        e={"home":.6,"draw":.2,"away":.2}
        q=blend(p,e,.3)
        self.assertAlmostEqual(sum(q),1,places=9)
        self.assertGreater(score([(date.today(),0,p,e)],.3)["logloss"],0)
    def test_small_samples_no_trick(self):
        r=validate(self.samples()[:10])
        self.assertEqual(r["estado"],"MUESTRA_INSUFICIENTE")
        self.assertFalse(r["se_aplica_automaticamente"])
if __name__=="__main__":
    unittest.main()
