import unittest
from datetime import datetime,timezone
from football_ai_lab.player_readiness import report

class PlayerReadinessTests(unittest.TestCase):
    def test_unused_bench_not_counted(self):
        rows=[{"event_id":"a","jugador_id":"1","jugador":"P A","equipo":"A",
               "fecha_utc":"2026-11-01T12:00:00Z","titular":False,
               "participacion_confirmada":False,"estadisticas":{"totalShots":0}},
              {"event_id":"b","jugador_id":"1","jugador":"P A","equipo":"A",
               "fecha_utc":"2026-11-02T12:00:00Z","titular":True,
               "participacion_confirmada":True,"estadisticas":{"totalShots":2}}]
        out=report({"registros":rows},datetime(2026,11,14,tzinfo=timezone.utc))
        self.assertEqual(out["participaciones_confirmadas"],1)
        self.assertEqual(out["jugadores"][0]["cobertura_tiros"],1)
        self.assertEqual(out["jugadores_con_muestra_inicial"],0)
        self.assertEqual(out["jugadores"][0]["partidos_con_minutos"],0)
    def test_missing_fields_do_not_mean_zero(self):
        rows=[{"event_id":str(i),"jugador_id":"1","jugador":"P A","equipo":"A",
               "fecha_utc":"2026-11-01T12:00:00Z",
               "participacion_confirmada":True,"estadisticas":{"goals":0}} for i in range(13)]
        out=report({"registros":rows},datetime(2026,11,14,tzinfo=timezone.utc))
        self.assertEqual(out["jugadores"][0]["partidos_con_tiros"],0)
        self.assertEqual(out["jugadores_con_muestra_inicial"],0)
if __name__=="__main__":unittest.main()
