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

    def test_additional_prioritizes_probability_over_higher_ev(self):
        low_p_high_ev=self._price_comparison(
            seleccion="Menos de 2,5 goles",linea=2.5,
            probabilidad_modelo=.55,cuota_real=2.50)
        high_p_lower_ev=self._price_comparison(
            seleccion="Menos de 3,5 goles",linea=3.5,
            probabilidad_modelo=.70,cuota_real=1.55)
        picked=freeze([],{"selecciones":[]},[self.match],self.now,
            comparisons={"comparaciones":[low_p_high_ev,high_p_lower_ev]})
        self.assertEqual(len(picked),1)
        self.assertEqual(picked[0]["seleccion"],"Menos de 3,5 goles")
        self.assertEqual(picked[0]["cuota_decimal"],"1.550")
        self.assertGreater(float(picked[0]["ev_teorico"]),.03)

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

    def test_exact_frozen_top3_pick_can_be_selected_as_additional_once(self):
        base=self._price_comparison()
        other=dict(base,bookmaker="OtherBook",bookmaker_id="other",
                   cuota_real=1.95,evento_id="event-2")
        top=[{"id":self.match["id"],"mercado":"Total goles",
              "seleccion":"Menos de 2,5 goles"}]
        rows=freeze([],{"selecciones":[]},[self.match],self.now,
                    comparisons={"comparaciones":[base,other]},top3=top)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["bookmaker_id"],"other")
        self.assertEqual(rows[0]["mercado"],top[0]["mercado"])
        self.assertEqual(rows[0]["seleccion"],top[0]["seleccion"])
        again=freeze(rows,{"selecciones":[]},[self.match],
                     self.now,comparisons={"comparaciones":[base,other]},top3=top)
        self.assertEqual(again,rows)  # congelada antes del partido

    def test_active_two_plus_one_exact_selection_and_original_preserved(self):
        from football_ai_lab.value_watchlist import active_top3
        m=self.match
        top=[
            {"id":m["id"],"mercado":"Total goles","seleccion":"Menos de 2,5 goles"},
            {"id":m["id"],"mercado":"Ambos marcan","seleccion":"Sí"},
            {"id":m["id"],"mercado":"Total goles","seleccion":"Más de 0,5 goles"},
        ]
        extra={"id":m["id"],"mercado":"Total goles","seleccion":"Menos de 2,5 goles",
               "archivado_utc":self.now.isoformat(),"fecha_utc":m["fecha_utc"],
               "cuota_decimal":"1.91","tipo_cuota":"OFRECIDA_API_REGISTRADA"}
        active=active_top3(top,[extra])
        self.assertEqual(len(active),2)
        self.assertEqual(len(top),3)
        self.assertEqual(active[0]["seleccion"],"Sí")
        diff=active_top3(top,[{**extra,"seleccion":"Menos de 3,5 goles"}])
        self.assertEqual(len(diff),3)
        invalid=active_top3(top,[{**extra,"cuota_decimal":"1.50"}])
        self.assertEqual(len(invalid),3)
        late=active_top3(top,[{**extra,"archivado_utc":m["fecha_utc"]}])
        self.assertEqual(len(late),3)

    def test_existing_manual_offer_never_relabelled_as_verified_api(self):
        previous=freeze([],self.manual,[self.match],self.now)
        after=freeze(previous,{"selecciones":[]},[self.match],
                     self.now+timedelta(minutes=4),
                     comparisons={"comparaciones":[self._price_comparison()]})
        self.assertEqual(after,previous)
        self.assertEqual(after[0]["tipo_cuota"],INDICATIVE)

    def test_real_quote_has_priority_over_new_manual_reference(self):
        comparison=self._price_comparison()
        result=freeze([],
            self.manual,[self.match],self.now,
            comparisons={"comparaciones":[comparison]})
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["tipo_cuota"],API)
        self.assertEqual(result[0]["cuota_decimal"],"1.800")
        self.assertEqual(result[0]["proveedor_cuota"],"5DollarFootballAPI")
        self.assertEqual(result[0]["bookmaker"],"Bet 365")
        self.assertEqual(result[0]["fecha_cuota_utc"],self.now.isoformat())
        # A second analysis must keep that first quote immutable.
        again=freeze(result,self.manual,[self.match],self.now+timedelta(minutes=3),
            comparisons={"comparaciones":[dict(comparison,cuota_real=2.8,
                actualizado_utc=(self.now+timedelta(minutes=3)).isoformat(),
                capturado_utc=(self.now+timedelta(minutes=3)).isoformat())]})
        self.assertEqual(again,result)

    def test_automatic_selection_audit_shows_abstentions_per_league(self):
        from football_ai_lab.value_watchlist import selection_audit
        other=dict(self.match,id="E0|other",liga="Premier League",
                   local="Manchester City",visitante="Fulham")
        quote=self._price_comparison()
        result=freeze([],{"selecciones":[]},[self.match,other],self.now,
                      comparisons={"comparaciones":[quote]})
        consulted={"fixtures":{other["id"]:{
            "consultado_utc":self.now.isoformat(),"con_cuotas":False}}}
        audit=selection_audit([],result,[self.match,other],
                 {"comparaciones":[quote]},self.now,[],
                 consultation_state=consulted)
        self.assertEqual(audit["comparaciones_recibidas"],1)
        self.assertEqual(audit["partidos_con_opcion_valida"],1)
        self.assertEqual(audit["nuevas_automaticas"],1)
        self.assertEqual(audit["abstenciones_sin_opcion_valida"],1)
        self.assertEqual(audit["por_liga"]["Segunda División"]["archivadas_automaticas"],1)
        self.assertEqual(audit["por_liga"]["Premier League"]["sin_opcion_valida"],1)
        self.assertTrue(audit["sin_cuota_real_no_se_inventa"])
        # Retaining prior picks counts as "already archived", not as a new pick.
        repeat=selection_audit(result,result,[self.match,other],
                 {"comparaciones":[quote]},self.now,[],
                 consultation_state=consulted)
        self.assertEqual(repeat["nuevas_automaticas"],0)
        self.assertEqual(repeat["abstenciones_ya_archivadas"],1)
        self.assertEqual(repeat["abstenciones_sin_opcion_valida"],1)

    def test_no_viable_only_after_real_consultation(self):
        from football_ai_lab.value_watchlist import selection_audit
        not_checked=dict(self.match,id="E0|not-checked",liga="Premier League",
                         local="City",visitante="United")
        no_market=dict(self.match,id="D1|no-market",liga="Bundesliga",
                       local="Bayern",visitante="Köln")
        rejected=dict(self.match,id="SP2|rejected",local="Burgos",
                      visitante="Albacete")
        compared=self._price_comparison(match=rejected,probabilidad_modelo=.54,
                                        cuota_real=1.55)
        consulted={"fixtures":{
            no_market["id"]:{"consultado_utc":self.now.isoformat(),"con_cuotas":False},
            rejected["id"]:{"consultado_utc":self.now.isoformat(),"con_cuotas":True}}}
        report=selection_audit([],[],[not_checked,no_market,rejected],
            {"comparaciones":[compared]},self.now,[],
            consultation_state=consulted)
        self.assertEqual(report["por_partido"][not_checked["id"]],"SIN_CONSULTAR")
        self.assertEqual(report["por_partido"][no_market["id"]],"SIN_CUOTAS_COMPATIBLES")
        self.assertEqual(report["por_partido"][rejected["id"]],"NO_SUPERA_FILTROS")
        self.assertEqual(report["abstenciones_sin_opcion_valida"],2)
        self.assertEqual(report["partidos_no_evaluados_sin_api"],1)
        self.assertEqual(report["por_estado_adicional"]["SIN_CONSULTAR"],1)
        self.assertTrue(report["por_partido_detalle"][rejected["id"]]["partido_consultado"])

    def test_push_without_api_preserves_last_real_audit(self):
        from football_ai_lab.value_watchlist import selection_audit
        consulted={"fixtures":{self.match["id"]:{
            "consultado_utc":self.now.isoformat(),"con_cuotas":True}}}
        previous={"por_partido":{self.match["id"]:"NO_SUPERA_FILTROS"}}
        report=selection_audit([],[],[self.match],
            {"estado":"DESACTIVADO","comparaciones":[]},self.now,[],
            consultation_state=consulted,previous_audit=previous)
        self.assertEqual(report["por_partido"][self.match["id"]],"NO_SUPERA_FILTROS")

    def test_unqueried_private_api_is_not_a_failed_bet_screen(self):
        from football_ai_lab.value_watchlist import selection_audit
        audit=selection_audit([],[],[self.match],
                {"estado":"DESACTIVADO","comparaciones":[]},self.now,[])
        self.assertEqual(audit["estado"],"FUENTES_NO_CONSULTADAS")
        self.assertEqual(audit["partidos_no_evaluados_sin_api"],1)
        self.assertEqual(audit["abstenciones_sin_opcion_valida"],0)
        self.assertEqual(audit["nuevas_automaticas"],0)
        self.assertEqual(audit["por_liga"]["Segunda División"]["no_evaluados_sin_api"],1)

    def test_auto_stale_quote_abstains_without_manually_fabricating_it(self):
        from football_ai_lab.value_watchlist import selection_audit
        later=self.now+timedelta(hours=7)
        raw={"comparaciones":[self._price_comparison()]}
        selected=freeze([],{"selecciones":[]},[self.match],later,
                        comparisons=raw)
        self.assertEqual(selected,[])
        audit=selection_audit([],selected,[self.match],raw,later,[])
        self.assertEqual(audit["abstenciones_sin_opcion_valida"],1)
        self.assertEqual(audit["nuevas_automaticas"],0)

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
