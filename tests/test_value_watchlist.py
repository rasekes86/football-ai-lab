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

    def _price_comparison(self, match=None, now=None, **overrides):
        m=match or self.match
        dt=now or self.now
        quote={
            "fixture_id":m["id"],"liga":m["liga"],
            "local":m["local"],"visitante":m["visitante"],
            "fecha_utc":m["fecha_utc"],
            "categoria":"goals","seleccion":"Menos de 2,5 goles",
            "probabilidad_modelo":.68,
            "nivel":"MODELO_NO_CALIBRADO",
            "cuota_real":1.8,
            "bookmaker":"Bet 365","bookmaker_id":"bet365",
            "mercado_proveedor":"totals",
            "resultado_proveedor":"under","linea":2.5,
            "actualizado_utc":dt.isoformat(),
            "capturado_utc":dt.isoformat(),
            "proveedor":"5DollarFootballAPI",
            "evento_id":"provider-fixture-123",
            "fuente":"https://5dollarfootballapi.com/",
            "etiqueta":"COMPARACION_INFORMATIVA_NO_VALIDADA",
            "marca_tiempo_tipo":"CAPTURA_NO_ACTUALIZACION",
            "fase_cuota":"ULTIMA_CUOTA_PREPARTIDO"
        }
        quote.update(overrides)
        return quote

    def test_real_price_automatically_frozen_and_settled(self):
        q=self._price_comparison()
        chosen=freeze([],{"selecciones":[]},[self.match],self.now,
                      comparisons={"comparaciones":[q]})
        self.assertEqual(len(chosen),1)
        self.assertEqual(chosen[0]["tipo_cuota"],API)
        self.assertEqual(chosen[0]["mercado"],"Total goles")
        self.assertEqual(chosen[0]["seleccion"],"Menos de 2,5 goles")
        self.assertEqual(chosen[0]["bookmaker"],"Bet 365")
        self.assertEqual(chosen[0]["proveedor_cuota"],"5DollarFootballAPI")
        self.assertEqual(chosen[0]["evento_id"],"provider-fixture-123")
        self.assertEqual(chosen[0]["marca_tiempo_tipo"],"CAPTURA_NO_ACTUALIZACION")
        finished,report=evaluate(chosen,self.g,self.kick+timedelta(hours=4))
        self.assertEqual(report["finalizadas"],1)
        self.assertEqual(report["global"]["aciertos"],1)
        self.assertEqual(report["verificacion"]["cuotas_api_observadas_antes_del_partido"],1)
        self.assertEqual(finished[0]["resultado"],"1")
        self.assertEqual(finished[0]["retorno_simulado_unidad"],"0.800")
        self.assertEqual(finished[0]["retorno_precio_api_unidad"],"0.800")

    def test_six_leagues_one_price_each_no_backfill_or_top3_change(self):
        names=("LaLiga","Segunda División","Premier League",
               "Bundesliga","Serie A","Ligue 1")
        teams=(
            ("Athletic Club","Espanyol"),
            ("Tenerife","Ceuta"),
            ("Manchester City","Fulham"),
            ("Bayern Munich","FC Cologne"),
            ("AC Milan","Roma"),
            ("Lyon","Marseille")
        )
        matches=[dict(self.match,id=f"{name}|game",liga=name,local=home,visitante=away)
                 for name,(home,away) in zip(names,teams)]
        quotes=[self._price_comparison(match=m) for m in matches]
        old_top=[{
            "id":matches[0]["id"],"mercado":"Total goles",
            "seleccion":"Más de 2,5 goles"
        }]
        frozen=freeze([],{"selecciones":[]},matches,self.now,
                      comparisons={"comparaciones":quotes},top3=old_top)
        self.assertEqual(len(frozen),6)
        self.assertEqual({x["liga"] for x in frozen},set(names))
        self.assertTrue(all(float(x["cuota_decimal"])>1.50 for x in frozen))
        self.assertEqual(old_top,[{
            "id":matches[0]["id"],"mercado":"Total goles",
            "seleccion":"Más de 2,5 goles"
        }])
        changed_quotes=[dict(q,cuota_real=5.0,probabilidad_modelo=.99)
                        for q in quotes]
        rerun=freeze(frozen,{"selecciones":[]},matches,
                     self.now+timedelta(minutes=20),
                     comparisons={"comparaciones":changed_quotes},
                     top3=old_top)
        self.assertEqual(rerun,frozen)

    def test_missing_provider_or_finished_match_never_fabricates_quote(self):
        self.assertEqual(freeze([],{"selecciones":[]},[self.match],
                         self.now,comparisons={"comparaciones":[]}),[])
        self.assertEqual(freeze([],{"selecciones":[]},[self.match],
                         self.kick+timedelta(minutes=2),
                         comparisons={"comparaciones":[self._price_comparison()]}),[])

    def test_exact_line_team_market_outcome_timestamp_and_provider_required(self):
        q=self._price_comparison()
        invalid=[
            dict(q,local="Granada"),
            dict(q,liga="LaLiga"),
            dict(q,fixture_id="another"),
            dict(q,fecha_utc="2026-11-15T14:00:00Z"),
            dict(q,linea=3.5),
            dict(q,mercado_proveedor="h2h"),
            dict(q,resultado_proveedor="over"),
            dict(q,etiqueta="NO_REAL"),
            dict(q,proveedor="UnknownBookmaker"),
            dict(q,bookmaker_id=""),
            dict(q,actualizado_utc=(self.now-timedelta(hours=7)).isoformat()),
            dict(q,capturado_utc=(self.now+timedelta(minutes=20)).isoformat()),
            dict(q,cuota_real=1.50),
            dict(q,probabilidad_modelo=.1),
            dict(q,seleccion="Menos de 1,5 goles"),
            dict(q,nivel="EXPLORATORIO_NO_VALIDADO"),
        ]
        for value in invalid:
            with self.subTest(q=value):
                self.assertEqual(freeze([],{"selecciones":[]},[self.match],
                                 self.now,comparisons={"comparaciones":[value]}),[])

    def test_only_one_bookmaker_one_extra_not_the_same_frozen_top3(self):
        base=self._price_comparison()
        other=dict(base,bookmaker="OtherBook",bookmaker_id="other",
                   cuota_real=1.95,evento_id="event-2")
        top=[{"id":self.match["id"],"mercado":"Total goles",
              "seleccion":"Menos de 2,5 goles"}]
        rows=freeze([],{"selecciones":[]},[self.match],self.now,
                    comparisons={"comparaciones":[base,other]},top3=top)
        self.assertEqual(rows,[])
        rows=freeze([],{"selecciones":[]},[self.match],self.now,
                    comparisons={"comparaciones":[base,other]})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["bookmaker_id"],"other")

    def test_existing_manual_offer_never_relabelled_as_verified_api(self):
        previous=freeze([],self.manual,[self.match],self.now)
        after=freeze(previous,{"selecciones":[]},[self.match],
                     self.now+timedelta(minutes=4),
                     comparisons={"comparaciones":[self._price_comparison()]})
        self.assertEqual(after,previous)
        self.assertEqual(after[0]["tipo_cuota"],INDICATIVE)

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
