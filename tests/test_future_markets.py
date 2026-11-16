"""Los pronósticos futuros por mercado no reescriben ni eligen un nuevo Top 3."""
import unittest
from football_ai_lab.selector import _market_future_previews

class FutureMarketsTests(unittest.TestCase):
    def test_markets_and_quality_without_inventing_fouls(self):
        goals=[
            {"mercado":"1X2","seleccion":"Local gana","probabilidad":.51,"cuota_justa":1.961,
             "origen":"Consenso Poisson/Elo","nivel":"MODELO_NO_CALIBRADO"},
            {"mercado":"Doble oportunidad","seleccion":"1X: local o empate","probabilidad":.74,
             "cuota_justa":1.351,"origen":"Consenso Poisson/Elo","nivel":"MODELO_NO_CALIBRADO"},
            {"mercado":"Ambos marcan","seleccion":"Sí","probabilidad":.53,
             "cuota_justa":1.887,"origen":"Poisson de goles","nivel":"MODELO_NO_CALIBRADO"},
            {"mercado":"Total goles","seleccion":"Más de 2,5 goles","probabilidad":.60,
             "cuota_justa":1.667,"origen":"Poisson de goles","nivel":"MODELO_NO_CALIBRADO"}
        ]
        exploratory=[
            {"mercado":"Córners totales","seleccion":"Más de 8,5 córners","probabilidad":.65,
             "cuota_justa":1.538,"origen":"Histórico de conteos","nivel":"EXPLORATORIO_NO_VALIDADO",
             "metrica":"corners","linea":8.5,"direccion":"mas"},
            {"mercado":"Tiros totales","seleccion":"Más de 19,5 tiros","probabilidad":.7,
             "cuota_justa":1.429,"origen":"Histórico de conteos","nivel":"EXPLORATORIO_NO_VALIDADO",
             "metrica":"shots","linea":19.5,"direccion":"mas"},
        ]
        promoted=[dict(exploratory[0],
                       nivel="BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA")]
        top=[dict(goals[1],posicion=2)]
        res=_market_future_previews(goals,promoted,exploratory,top)
        self.assertEqual(res["double"][0]["posicion_top3"],2)
        self.assertEqual(res["corners"][0]["nivel"],
                         "BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA")
        self.assertEqual(res["shots"][0]["nivel"],"EXPLORATORIO_NO_VALIDADO")
        self.assertEqual(res["result"][0]["seleccion"],"Local gana")
        self.assertIn("btts",res)
        self.assertIn("goals",res)
        self.assertNotIn("fouls",res)
        self.assertNotIn("red",res)
        self.assertEqual(top[0]["posicion"],2)
        self.assertNotIn("posicion_top3",goals[1])

    def test_priority_and_top_limit_without_duplicates(self):
        rows=[]
        for i in range(15):
            rows.append({"mercado":"Córners totales","metrica":"corners",
                        "seleccion":f"Más de {i},5","probabilidad":.51+.02*i,
                        "cuota_justa":1.1,"nivel":"EXPLORATORIO_NO_VALIDADO",
                        "origen":"Histórico","linea":i+.5,"direccion":"mas"})
        out=_market_future_previews([],[],rows,[])
        self.assertEqual(len(out["corners"]),8)
        self.assertGreater(out["corners"][0]["probabilidad"],out["corners"][-1]["probabilidad"])

    def test_no_fabricated_from_missing_data(self):
        self.assertEqual(_market_future_previews([],[],[],[]),{})

if __name__ == "__main__":
    unittest.main()
