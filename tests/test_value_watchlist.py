import json
import unittest
from datetime import datetime,date,timedelta,timezone
from football_ai_lab.value_watchlist import (freeze,evaluate,summary,markdown,API,INDICATIVE)

class ValueWatchlistTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,15,1,tzinfo=timezone.utc)
        self.kick=datetime(2026,11,15,13,tzinfo=timezone.utc)
        self.match={"id":"SP2|test","fecha_utc":self.kick.isoformat(),
                    "liga":"Segunda División","local":"Tenerife","visitante":"Ceuta",
                    "calculado_utc":self.now.isoformat(),"top_valor_exploratorio":[]}
        self.manual={"selecciones":[{
            "id":"SP2|test","fecha_utc":self.kick.isoformat(),
            "liga":"Segunda División","local":"Tenerife","visitante":"Ceuta",
            "mercado":"Total goles","seleccion":"Menos de 2,5 goles",
            "familia":"total_goles","probabilidad":.57017,"cuota_decimal":1.93,
            "tipo_cuota":INDICATIVE,"origen_cuota":"Conversación no verificada",
            "ref_modelo_utc":self.now.isoformat()}]}
        self.g={"SP2":[{"date":date(2026,11,15),"home":"Tenerife","away":"Ceuta",
                        "home_goals":1,"away_goals":0}]}
    def test_initial_freeze_and_not_revised(self):
        rows=freeze([],self.manual,[self.match],self.now)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["tipo_cuota"],INDICATIVE)
        self.assertEqual(rows[0]["fecha_cuota_utc"],"")
        self.assertAlmostEqual(float(rows[0]["ev_teorico"]),.57017*1.93-1,places=5)
        edited={"selecciones":[dict(self.manual["selecciones"][0],probabilidad=.99,cuota_decimal=3.4)]}
        self.assertEqual(freeze(rows,edited,[self.match],self.now+timedelta(minutes=5)),rows)
    def test_settlement_with_hypothetical_return(self):
        rows=freeze([],self.manual,[self.match],self.now)
        pending,s=evaluate(rows,self.g,self.now)
        self.assertEqual(s["finalizadas"],0)
        self.assertEqual(pending[0]["estado"],"PENDIENTE")
        finished,report=evaluate(rows,self.g,self.kick+timedelta(hours=4))
        self.assertEqual(report["finalizadas"],1)
        self.assertEqual(report["global"]["aciertos"],1)
        self.assertEqual(report["por_tipo_cuota"][INDICATIVE]["evaluadas"],1)
        self.assertEqual(finished[0]["retorno_simulado_unidad"],"0.930")
        self.assertEqual(finished[0]["retorno_precio_api_unidad"],"")
        self.assertIn("no se efectuaron apuestas",markdown(finished,report))
    def test_outcome_verified_without_historical_bookmaker_proof(self):
        rows=freeze([],self.manual,[self.match],self.now)
        done,report=evaluate(rows,self.g,self.kick+timedelta(hours=4))
        ver=report["verificacion"]
        self.assertEqual(ver["resultados_verificados"],1)
        self.assertEqual(ver["cuotas_indicativas_no_acreditadas"],1)
        self.assertEqual(ver["cuotas_api_observadas_antes_del_partido"],0)
        self.assertEqual(ver["resultados_pendientes_o_sin_dato"],0)
        self.assertEqual(done[0]["estado"],"FINALIZADO")
        self.assertEqual(done[0]["tipo_cuota"],INDICATIVE)

    def test_api_quote_requires_pre_match_timestamp_proof(self):
        from football_ai_lab.value_watchlist import verification_summary
        baseline={"tipo_cuota":API,
             "cuota_decimal":"2.20",
             "fecha_cuota_utc":self.now.isoformat(),
             "archivado_utc":(self.now+timedelta(minutes=5)).isoformat(),
             "fecha_utc":self.kick.isoformat(),
             "estado":"FINALIZADO","resultado":"1"}
        self.assertEqual(verification_summary([baseline])[
            "cuotas_api_observadas_antes_del_partido"],1)
        no_time=dict(baseline,fecha_cuota_utc="")
        self.assertEqual(verification_summary([no_time])[
            "cuotas_api_observadas_antes_del_partido"],0)
        self.assertEqual(verification_summary([no_time])[
            "cuotas_api_sin_prueba_temporal"],1)
        too_late=dict(baseline,archivado_utc=(self.kick+timedelta(minutes=5)).isoformat())
        self.assertEqual(verification_summary([too_late])[
            "cuotas_api_observadas_antes_del_partido"],0)

    def test_missing_result_not_loss(self):
        rows=freeze([],self.manual,[self.match],self.now)
        finished,summary=evaluate(rows,{"SP2":[]},self.kick+timedelta(hours=5))
        self.assertEqual(summary["resultados_no_disponibles"],1)
        self.assertEqual(summary["finalizadas"],0)
        self.assertEqual(finished[0]["retorno_simulado_unidad"],"")
    def test_manual_not_backfilled_after_kickoff(self):
        self.assertEqual(freeze([],self.manual,[self.match],self.kick+timedelta(minutes=2)),[])
    def test_bad_odds_or_team_rejected(self):
        bad={"selecciones":[dict(self.manual["selecciones"][0],cuota_decimal=1.49)]}
        self.assertEqual(freeze([],bad,[self.match],self.now),[])
        bad={"selecciones":[dict(self.manual["selecciones"][0],local="Real Madrid")]}
        self.assertEqual(freeze([],bad,[self.match],self.now),[])
    def test_api_quote_only_timestamped(self):
        quote={"mercado":"1X2","seleccion":"Tenerife gana","familia":"resultado",
               "probabilidad":.6,"cuota_real":1.90,"casa":"Fuente",
               "fecha_cuota_utc":self.now.isoformat(),"nivel":"MODELO","origen":"Poisson"}
        m=dict(self.match,top_valor_exploratorio=[quote])
        rows=freeze([],{"selecciones":[]},[m],self.now)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["tipo_cuota"],API)
        self.assertEqual(rows[0]["cuota_decimal"],"1.900")
        stale=dict(m,top_valor_exploratorio=[dict(quote,fecha_cuota_utc=
                   (self.now-timedelta(hours=7)).isoformat())])
        self.assertEqual(freeze([],{"selecciones":[]},[stale],self.now),[])
    def test_no_profit_from_unverified_price(self):
        rows=freeze([],self.manual,[self.match],self.now)
        rows[0]["cuota_decimal"]="1.93"
        updated,e=evaluate(rows,self.g,self.kick+timedelta(hours=4))
        self.assertEqual(updated[0]["retorno_precio_api_unidad"],"")
        self.assertEqual(e["por_tipo_cuota"][INDICATIVE]["evaluadas"],1)
if __name__=="__main__":unittest.main()
