import unittest
from datetime import datetime,timezone
from football_ai_lab.full_report import build_one,markdown,build_all

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.p={"id":"i1","liga":"LaLiga","fecha_utc":"2026-11-21T20:00:00+00:00",
                "local":"Real Madrid","visitante":"Celta Vigo","modelo":"poisson-test",
                "prob_local":"0.59","prob_empate":"0.25","prob_visitante":"0.16",
                "prob_mas_2_5":"0.45","goles_esperados_local":"1.62",
                "goles_esperados_visitante":"0.8","fecha_analisis_utc":"2026-11-14T20:00:00+00:00"}
    def test_full_dossier_never_fakes_injuries_or_market(self):
        d=build_one(self.p,None,None)
        self.assertEqual(d["top_3"],[])
        self.assertIsNone(d["equipos"]["local"]["clasificacion"])
        text=markdown(d)
        self.assertIn("xG auténtico no integrado",text)
        self.assertIn("cuotas ofrecidas",text.lower())
        self.assertNotIn("Mbappé",text)
    def test_context_and_selection_attached_by_key(self):
        x={"liga":"SP1","fecha_utc":self.p["fecha_utc"],
           "local":"Real Madrid","visitante":"Celta Vigo",
           "local_datos":{"v":3,"e":1,"d":1,"dias_descanso":5,
                          "ultimos":[{"resultado":"V"}],"medias":{"tiros":14}},
           "visitante_datos":{"v":1,"e":2,"d":2,"dias_descanso":7,"medias":{}},
           "enfrentamientos":[],"calidad":{"motivos":[]}}
        s={"id":"i1","top_probabilidad":[{"mercado":"Total goles","seleccion":"Más de 1,5 goles",
              "probabilidad":.7,"cuota_justa":1.43,"nivel":"MODELO",
              "origen":"Poisson"}]}
        r=build_all([self.p],[x],[s],now=datetime(2026,11,14,20,tzinfo=timezone.utc))
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]["equipos"]["local"]["reciente"]["v"],3)
        self.assertEqual(r[0]["top_3"][0]["seleccion"],"Más de 1,5 goles")
if __name__=="__main__":unittest.main()
