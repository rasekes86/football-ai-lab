"""Pruebas de probabilidades, mercados, precios y abstención por datos insuficientes."""
import math
import unittest
from datetime import date,datetime,timedelta,timezone
from football_ai_lab.selector import (_distribution,goal_candidates,exploratory_counts,
                                       select_match,global_top,offered_prices,_count_cdf)

class MarketSelectorTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,14,20,tzinfo=timezone.utc)
        self.p={"id":"p1","fecha_utc":"2026-11-21T20:00:00+00:00",
                "liga":"LaLiga","local":"Real Madrid","visitante":"Celta Vigo",
                "prob_local":"0.6","prob_empate":"0.25","prob_visitante":"0.15",
                "goles_esperados_local":"1.65","goles_esperados_visitante":"0.80",
                "tipo":"REAL"}
    def test_poisson_distribution_and_btts_complements(self):
        m=_distribution(1.65,.8)
        self.assertAlmostEqual(sum(x[2] for x in m),1,places=10)
        c=goal_candidates(self.p)
        lookup={x["seleccion"]:x["probabilidad"] for x in c}
        self.assertAlmostEqual(lookup["Sí"]+lookup["No"],1,places=5)
        self.assertAlmostEqual(lookup["1X: Real Madrid o empate"],.85,places=8)
        self.assertAlmostEqual(lookup["X2: empate o Celta Vigo"],.4,places=8)
        self.assertAlmostEqual(lookup["Más de 2,5 goles"]+lookup["Menos de 2,5 goles"],1,places=5)
    def test_top_3_is_sorted_and_diversified(self):
        x=select_match(self.p,[],[],self.now)
        pick=x["top_probabilidad"]
        self.assertEqual(len(pick),3)
        self.assertEqual(len({v["familia"] for v in pick}),3)
        self.assertTrue(all(v["probabilidad"]>=.55 for v in pick))
        self.assertEqual(x["top_valor_exploratorio"],[])
        self.assertEqual(x["estado_valor"],"SIN_CUOTAS_REALES_VERIFICADAS")
    def test_no_value_from_infersports_fair(self):
        prices=[{"id":"p1","estado":"REFERENCIA_INFERSPORTS_SIN_VALIDAR",
                 "proveedor":"InferSports (keyless)","casa":"test",
                 "cuota_local":"3.0","fecha_cuota_utc":self.now.isoformat()}]
        self.assertEqual(offered_prices(self.p,prices,self.now),{})
    def test_value_only_real_fresh_offered_1x2_price(self):
        price=[{"id":"p1","estado":"COMPARACIÓN_SIN_VALIDAR",
                "proveedor":"The Odds API","casa":"Proveedor ficticio",
                "cuota_local":"2.1","cuota_empate":"3.4","cuota_visitante":"6.0",
                "fecha_cuota_utc":self.now.isoformat()}]
        x=select_match(self.p,[],price,self.now)
        self.assertTrue(x["top_valor_exploratorio"])
        self.assertEqual(x["top_valor_exploratorio"][0]["cuota_real"],2.1)
        old=self.now-timedelta(hours=7)
        price[0]["fecha_cuota_utc"]=old.isoformat()
        self.assertFalse(select_match(self.p,[],price,self.now)["top_valor_exploratorio"])
    def test_shots_are_exploratory_not_top_three(self):
        start=date(2024,1,1)
        rows=[{"date":start+timedelta(days=i),"home":"Real Madrid",
               "away":"Celta Vigo","home_corners":7,"away_corners":4,
               "home_shots":12,"away_shots":6,"home_on_target":5,
               "away_on_target":2,"home_yellow":2,"away_yellow":3} for i in range(200)]
        ex=exploratory_counts(self.p,rows,date(2026,11,21))
        self.assertGreater(len(ex),0)
        self.assertTrue(all(v["nivel"]=="EXPLORATORIO_NO_VALIDADO" for v in ex))
        x=select_match(self.p,rows,[],self.now)
        self.assertTrue(x["exploratorios"])
        self.assertFalse(any(y["origen"]=="Histórico de conteos con dispersión" for y in x["top_probabilidad"]))
    def test_invalid_or_started_match_rejected(self):
        with self.assertRaises(ValueError):
            select_match(dict(self.p,fecha_utc="2026-11-01T20:00:00+00:00"),[],[],self.now)
    def test_global_top_one_per_match(self):
        a=select_match(self.p,[],[],self.now)
        b=select_match(dict(self.p,id="p2",local="Barcelona"),[],[],self.now)
        self.assertEqual(len(global_top([a,b])),2)
    def test_count_cdf(self):
        self.assertLess(_count_cdf(2,3,5),1)
        self.assertAlmostEqual(_count_cdf(3,2,2),sum(math.exp(-2)*2**i/math.factorial(i) for i in range(4)),places=7)
if __name__=="__main__":
    unittest.main()
