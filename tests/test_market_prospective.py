import json
import unittest
from datetime import date,datetime,timedelta,timezone
from football_ai_lab.market_prospective import contract,archive,settle,summary,_observed

class MarketsProspectiveTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,14,20,tzinfo=timezone.utc)
        self.kick=datetime(2026,11,21,20,tzinfo=timezone.utc)
        self.base={"id":"SP1|A","liga":"LaLiga","local":"Real Madrid",
                   "visitante":"Celta Vigo","fecha_utc":self.kick.isoformat(),
                   "calculado_utc":self.now.isoformat(),
                   "top_probabilidad":[]}
        self.historical={"SP1":[{"date":date(2026,11,21),
                    "home":"Real Madrid","away":"Celta",
                    "home_goals":2,"away_goals":1,
                    "home_shots":14,"away_shots":11,
                    "home_corners":6,"away_corners":4,
                    "home_on_target":7,"away_on_target":3,
                    "home_yellow":3,"away_yellow":2}]}
    def candidate(self,market,label,**extra):
        return {"mercado":market,"seleccion":label,"familia":"test",
                "probabilidad":.8,"cuota_justa":1.25,**extra}
    def test_contract_all_markets_and_result(self):
        pairs=[
           (self.candidate("1X2","Real Madrid gana"),True),
           (self.candidate("Doble oportunidad","X2: empate o Celta Vigo"),False),
           (self.candidate("Doble oportunidad","1X: Real Madrid o empate"),True),
           (self.candidate("Ambos marcan","Sí"),True),
           (self.candidate("Total goles","Más de 2,5 goles"),True),
           (self.candidate("Goles equipo","Celta Vigo: menos de 1,5 goles"),True),
           (self.candidate("Hándicap 2 vías (medio gol)","Celta Vigo +1,5"),True),
           (self.candidate("Córners totales","Más de 9,5 córners totales",
                           metrica="corners",linea=9.5,direccion="mas"),True),
           (self.candidate("Tiros a puerta totales","Más de 8,5 tiros a puerta totales",
                           metrica="on_target",linea=8.5,direccion="mas"),True),
        ]
        for c,want in pairs:
            with self.subTest(c=c["seleccion"]):
                spec=contract(self.base,c)
                self.assertIsNotNone(spec)
                actual,_=_observed(spec,self.historical["SP1"][0])
                self.assertEqual(actual,want)
    def test_archived_first_three_never_replaced(self):
        m=dict(self.base,top_probabilidad=[
            self.candidate("Total goles","Más de 2,5 goles"),
            self.candidate("Doble oportunidad","1X: Real Madrid o empate")])
        first=archive([], [m],self.now)
        self.assertEqual(len(first),2)
        altered=dict(m,top_probabilidad=[self.candidate("1X2","Celta Vigo gana")])
        self.assertEqual(first,archive(first,[altered],self.now+timedelta(hours=1)))
        settled=settle(first,self.historical,self.kick+timedelta(hours=4))
        self.assertEqual([x["resultado"] for x in settled],["1","1"])
        self.assertEqual(summary(settled,self.kick+timedelta(hours=4))["finalizadas"],2)
    def test_results_never_assumed_before_final(self):
        m=dict(self.base,top_probabilidad=[self.candidate("1X2","Real Madrid gana")])
        recorded=archive([], [m],self.now)
        self.assertEqual(settle(recorded,self.historical,self.now)[0]["estado"],"PENDIENTE")
        self.assertEqual(settle(recorded,{"SP1":[]},self.kick+timedelta(days=1))[0]["estado"],
                         "RESULTADO_NO_DISPONIBLE")
    def test_missing_stat_not_loss(self):
        m=dict(self.base,top_probabilidad=[self.candidate("Córners totales",
                 "Más de 9,5 córners totales",metrica="corners",linea=9.5,direccion="mas")])
        rows=archive([], [m],self.now)
        history={"SP1":[dict(self.historical["SP1"][0],home_corners=None)]}
        tracked=settle(rows,history,self.kick+timedelta(hours=3))
        self.assertEqual(tracked[0]["estado"],"ESTADISTICA_NO_DISPONIBLE")
        self.assertEqual(summary(tracked,self.kick+timedelta(hours=3))["finalizadas"],0)
    def test_posthoc_snapshot_ignored(self):
        m=dict(self.base,calculado_utc=(self.kick+timedelta(minutes=3)).isoformat(),
               top_probabilidad=[self.candidate("1X2","Real Madrid gana")])
        self.assertEqual(archive([], [m],self.kick+timedelta(days=1)),[])
    def test_bad_label_not_persisted(self):
        m=dict(self.base,top_probabilidad=[self.candidate("Tiros de jugador","Vinicius +2")])
        self.assertEqual(archive([], [m],self.now),[])
if __name__=="__main__":unittest.main()
