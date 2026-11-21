"""Seguimiento separado de mercados con cotización >1,50.

Registra las selecciones antes del inicio y las liquida después, conservando
probabilidad, precio, tipo de evidencia y fuente. Si el precio no fue verificado,
el rendimiento monetario es exclusivamente una SIMULACIÓN, jamás beneficio real.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
import json
from math import isfinite
from .core import normalize_team
from .market_prospective import contract, settle

VERSION="value-watchlist-0.9"
MIN_QUOTE=1.50
FIELDS=[
    "clave","id","liga","local","visitante","fecha_utc","archivado_utc",
    "mercado","seleccion","familia","origen","nivel","probabilidad",
    "cuota_justa","contrato","cuota_decimal","tipo_cuota","origen_cuota",
    "fecha_cuota_utc","ref_modelo_utc","ev_teorico","estado","resultado",
    "valor_real","brier","logloss","partidos_fuente",
    "retorno_simulado_unidad","retorno_precio_api_unidad",
    "proveedor_cuota","bookmaker","bookmaker_id","evento_id",
    "mercado_proveedor","resultado_proveedor","linea_cuota",
    "marca_tiempo_tipo","fase_cuota"
]
INDICATIVE="INDICATIVA_NO_VERIFICADA"
API="OFRECIDA_API_REGISTRADA"

def _utc(s: str)->datetime:
    dt=datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("Timestamp sin zona horaria")
    return dt.astimezone(timezone.utc)

def _valid_price(raw)->float|None:
    try:
        odd=float(raw)
        if not isfinite(odd) or odd<=MIN_QUOTE or odd>1000:return None
        return odd
    except (TypeError,ValueError):return None

def _candidate(m:dict, c:dict, *,price:float,origin:str,kind:str,
               now:datetime,observed:str="",model_ref:str="")->dict|None:
    try:
        fixture=_utc(m["fecha_utc"])
        if now>=fixture:return None
        p=float(c["probabilidad"])
        if not isfinite(p) or not 0<p<1:return None
        spec=contract(m,c)
        if spec is None:return None
        if kind==API:
            tick=_utc(observed)
            if tick>=fixture or not 0<=(now-tick).total_seconds()<=6*3600:return None
        else:
            observed=""
        key=m["id"]+"|"+c["mercado"]+"|"+c["seleccion"]
        return dict(clave=key,id=m["id"],liga=m["liga"],local=m["local"],
                    visitante=m["visitante"],fecha_utc=m["fecha_utc"],
                    archivado_utc=now.isoformat(),mercado=c["mercado"],
                    seleccion=c["seleccion"],familia=c.get("familia",""),
                    origen=c.get("origen",""),nivel=c.get("nivel",""),
                    probabilidad=f"{p:.6f}",cuota_justa=f"{1/p:.3f}",
                    contrato=json.dumps(spec,ensure_ascii=False,sort_keys=True),
                    cuota_decimal=f"{price:.3f}",tipo_cuota=kind,
                    origen_cuota=origin,fecha_cuota_utc=observed,
                    ref_modelo_utc=model_ref,
                    ev_teorico=f"{(p*price-1):.6f}",estado="PENDIENTE",
                    resultado="",valor_real="",brier="",logloss="",
                    partidos_fuente="",retorno_simulado_unidad="",
                    retorno_precio_api_unidad="")
    except (KeyError,TypeError,ValueError):return None

def _manual_candidates(manual:dict, matches:list[dict], now:datetime)->list[dict]:
    """Manuales: probabilidad del informe previo congelada, sin validar la cuota."""
    refs={m["id"]:m for m in matches}
    output=[]
    for item in manual.get("selecciones",[]):
        if item.get("tipo_cuota")!=INDICATIVE:continue
        price=_valid_price(item.get("cuota_decimal"))
        if price is None:continue
        m=refs.get(item.get("id"))
        if m is None:continue
        # Cross-check identity against the captured original display; never
        # silently match a different fixture with a similar name.
        try:
            if m["liga"]!=item["liga"] or _utc(m["fecha_utc"])!=_utc(item["fecha_utc"]):
                continue
            if (normalize_team(m["local"])!=normalize_team(item["local"]) or
                    normalize_team(m["visitante"])!=normalize_team(item["visitante"])):
                continue
        except (KeyError,TypeError,ValueError):continue
        candidate={"mercado":item["mercado"],"seleccion":item["seleccion"],
                   "probabilidad":item["probabilidad"],
                   "familia":item.get("familia","mercado"),
                   "origen":"Modelo archivado (no recalculado)",
                   "nivel":"ESTIMACION_EXPERIMENTAL_NO_CALIBRADA"}
        source=str(item.get("origen_cuota") or "Referencia indicativa sin verificación")
        found=_candidate(m,candidate,price=price,origin=source,kind=INDICATIVE,
                         now=now,model_ref=str(item.get("ref_modelo_utc") or ""))
        if found:
            # No external odds timestamp is known. This is honest missingness.
            found["fecha_cuota_utc"]=""
            output.append(found)
    return output

def _api_candidates(matches:list[dict],now:datetime)->list[dict]:
    out=[]
    for m in matches:
        for c in m.get("top_valor_exploratorio") or []:
            price=_valid_price(c.get("cuota_real"))
            if price is None or c.get("mercado")!="1X2":continue
            orig="The Odds API · "+str(c.get("casa") or "casa sin nombre")
            row=_candidate(m,c,price=price,origin=orig,kind=API,now=now,
                           observed=str(c.get("fecha_cuota_utc") or ""),
                           model_ref=m.get("calculado_utc",""))
            if row:out.append(row)
    return out

# Pre-match third-party prices are observations, not placed bets.
# A positive model EV is a SCREEN, not proof of profitable value.
MIN_AUTO_PROB=0.50
MIN_AUTO_EV=0.03
MAX_QUOTE_HOURS=6
TRUSTED_COMPARISONS={"5DollarFootballAPI","API-Football","The Odds API V4"}
CATEGORY_MARKETS={
    "result":"1X2","goals":"Total goles",
    "corners":"Córners totales","yellow":"Tarjetas amarillas totales",
    "btts":"Ambos marcan",
}


def _verified_comparison(match:dict, raw:dict, now:datetime)->dict|None:
    """An observed quote for the same future fixture, market, line and pick.

    Free-feed actualizado_utc may be local capture, NOT a bookmaker tick.
    We preserve this provenance and never infer an executable wager.
    """
    try:
        if not isinstance(raw,dict) or raw.get("fixture_id")!=match["id"]:
            return None
        if (raw.get("liga")!=match["liga"] or
                raw.get("local")!=match["local"] or
                raw.get("visitante")!=match["visitante"] or
                _utc(raw["fecha_utc"])!=_utc(match["fecha_utc"])):
            return None
        kickoff=_utc(match["fecha_utc"])
        seen=_utc(raw["actualizado_utc"])
        capture=_utc(raw["capturado_utc"])
        if not (capture<=now<kickoff and seen<=now and seen<kickoff and
                0<=(now-capture).total_seconds()<=MAX_QUOTE_HOURS*3600 and
                0<=(now-seen).total_seconds()<=MAX_QUOTE_HOURS*3600):
            return None
        if raw.get("proveedor") not in TRUSTED_COMPARISONS:
            return None
        if raw.get("etiqueta")!="COMPARACION_INFORMATIVA_NO_VALIDADA":
            return None
        if not (str(raw.get("bookmaker") or "").strip() and
                str(raw.get("bookmaker_id") or "").strip() and
                str(raw.get("evento_id") or "").strip() and
                str(raw.get("fuente") or "").startswith("https://")):
            return None
        market=CATEGORY_MARKETS.get(raw.get("categoria"))
        if market is None:return None
        price=_valid_price(raw.get("cuota_real"))
        prob=float(raw.get("probabilidad_modelo"))
        if (price is None or not isfinite(prob) or
                not MIN_AUTO_PROB<=prob<1):
            return None
        # Count forecasts are used only after retrospective validation;
        # this does not mean that profit has been prospectively validated.
        level=str(raw.get("nivel") or "")
        if level=="EXPLORATORIO_NO_VALIDADO":
            return None
        quote=dict(raw)
        forecast={
            "mercado":market,"seleccion":str(raw.get("seleccion") or ""),
            "probabilidad":prob,"familia":str(raw.get("categoria")),
            "origen":"Pronóstico prepartido / comparación exacta con bookmaker",
            "nivel":level
        }
        if raw.get("categoria") in ("corners","yellow"):
            direction=(
                "mas" if forecast["seleccion"].startswith("Más de ") else
                "menos" if forecast["seleccion"].startswith("Menos de ") else None)
            forecast.update(metrica="corners" if raw["categoria"]=="corners" else "yellow",
                            direccion=direction,linea=raw.get("linea"))
        spec=contract(match,forecast)
        if spec is None:return None
        expected_market={
            "resultado":"h2h","total":"totals","ambos":"btts",
            "conteo":spec.get("metrica")
        }.get(spec["tipo"])
        if raw.get("mercado_proveedor")!=expected_market:
            return None
        direction=spec.get("direccion")
        expected_result=(
            {"H":"1","D":"X","A":"2"}.get(spec.get("pick"))
            if spec["tipo"]=="resultado" else
            ("over" if direction in ("mas","Más") else "under")
            if spec["tipo"] in ("total","conteo") else
            "yes" if spec.get("pick")=="Sí" else "no"
        )
        if raw.get("resultado_proveedor")!=expected_result:
            return None
        expected_line=spec.get("linea")
        supplied_line=raw.get("linea")
        if expected_line is None:
            if supplied_line is not None:return None
        else:
            if supplied_line is None or abs(float(supplied_line)-expected_line)>1e-8:
                return None
        ev=prob*price-1
        if ev<=MIN_AUTO_EV:return None
        return {"forecast":forecast,"raw":quote,"price":price,"ev":ev,
                "captured":capture,"seen":seen}
    except (KeyError,TypeError,ValueError,OverflowError):
        return None


def _compared_candidates(matches:list[dict],comparisons:dict|list[dict],
                         now:datetime,top3:list[dict]|None=None)->list[dict]:
    """At most one automatic candidate per match, prospectively selected."""
    rows=(comparisons.get("comparaciones") if isinstance(comparisons,dict)
          else comparisons if isinstance(comparisons,list) else []) or []
    if not isinstance(rows,list):return []
    by_fixture=defaultdict(list)
    for row in rows:
        if isinstance(row,dict) and row.get("fixture_id"):
            by_fixture[row["fixture_id"]].append(row)
    # Una misma selección puede ofrecer cuota real >1,50 y estar en el Top 3.
    # Se permite como adicional: al contabilizar, se elimina del Top 3 ACTIVO,
    # no del histórico congelado (la prueba exacta incluye mercado y línea).
    selected=[]
    for match in matches:
        if not isinstance(match,dict) or not match.get("id"):
            continue
        options=[]
        for quote in by_fixture.get(match["id"],[]):
            candidate=_verified_comparison(match,quote,now)
            if candidate is None:continue
            # No descartar coincidencias con el Top 3: en la app e informes
            # se cuenta como adicional y se retira del Top 3 activo.
            options.append(candidate)
        # Objetivo 3+1: maximizar la probabilidad estimada de ACIERTO entre
        # cotizaciones reales >1,50 que superan calidad y EV mínimo.
        # El EV solo filtra/desempata; no predomina sobre la probabilidad.
        options.sort(key=lambda x:(
            -x["forecast"]["probabilidad"],-x["ev"],-x["price"],
            str(x["raw"]["seleccion"]),str(x["raw"]["bookmaker_id"])))
        if not options:continue
        chosen=options[0]
        row=chosen["raw"];forecast=chosen["forecast"]
        origin=(f'{row["proveedor"]} · {row["bookmaker"]} · '
                f'{row["fuente"]}')
        new=_candidate(match,forecast,price=chosen["price"],
                       origin=origin,kind=API,now=now,
                       observed=chosen["seen"].isoformat(),
                       model_ref=str(match.get("calculado_utc") or ""))
        if new is None:continue
        new.update({
            "proveedor_cuota":str(row["proveedor"]),
            "bookmaker":str(row["bookmaker"]),
            "bookmaker_id":str(row["bookmaker_id"]),
            "evento_id":str(row["evento_id"]),
            "mercado_proveedor":str(row["mercado_proveedor"]),
            "resultado_proveedor":str(row["resultado_proveedor"]),
            "linea_cuota":str(row["linea"]) if row.get("linea") is not None else "",
            "marca_tiempo_tipo":str(row.get("marca_tiempo_tipo") or ""),
            "fase_cuota":str(row.get("fase_cuota") or ""),
        })
        selected.append(new)
    return selected


 
def selection_audit(previous:list[dict],current:list[dict],matches:list[dict],
                    comparisons:dict|list[dict],now:datetime,
                    top3:list[dict]|None=None,
                    consultation_state:dict|None=None,
                    previous_audit:dict|None=None)->dict:
    """Explain autonomous decisions without inventing picks, prices or returns.

    Separately report exact comparisons, valid choices, archived selections
    and abstentions. Only current authorized pre-match comparisons may qualify.
    A fixture can be covered even when it has no matching bookmaker line.
    """
    raw=(comparisons.get("comparaciones") if isinstance(comparisons,dict)
         else comparisons if isinstance(comparisons,list) else []) or []
    if not isinstance(raw,list):raw=[]
    # On code push the workflow intentionally disables the private APIs.
    # Missing comparisons in that run are "not checked", not failed screens.
    not_queried=(isinstance(comparisons,dict) and not raw and
                 comparisons.get("estado") in ("DESACTIVADO","SIN_CLAVE"))
    eligible=_compared_candidates(matches,raw,now,top3)
    valid_by_id={r["id"]:r for r in eligible}
    old_ids={r.get("id") for r in previous if r.get("id")}
    current_by_id={r.get("id"):r for r in current if r.get("id")}
    totals={"estado":"FUENTES_NO_CONSULTADAS" if not_queried else "EVALUADO",
            "comparaciones_recibidas":len(raw),
            "partidos_con_comparaciones":len({r.get("fixture_id") for r in raw
                                            if isinstance(r,dict) and r.get("fixture_id")}),
            "partidos_con_opcion_valida":len(eligible),
            "nuevas_automaticas":sum(r.get("id") not in old_ids and
                r.get("tipo_cuota")==API and r.get("id") in valid_by_id
                for r in current if isinstance(r,dict)),
            "partidos_ya_archivados":len(old_ids),
            "partidos_con_adicional_archivada":len(current_by_id),
            "abstenciones_sin_opcion_valida":0,
            "partidos_no_evaluados_sin_api":0,
            "abstenciones_ya_archivadas":0,
            "sin_cuota_real_no_se_inventa":True,
            "por_liga":{},"por_partido":{}}
    # Un fixture sin peticion real NO es una cuota inviable. El libro de
    # peticiones acredita que se consultó, incluso si no hubo mercados aptos.
    consulted=(consultation_state or {}).get("fixtures") or {}
    prior_reasons=(previous_audit or {}).get("por_partido") or {}
    totals["por_estado_adicional"]={}
    totals["por_partido_detalle"]={}
    by_fixture=defaultdict(int)
    for quote in raw:
        if isinstance(quote,dict) and quote.get("fixture_id"):
            by_fixture[quote["fixture_id"]]+=1
    for match in matches:
        if not isinstance(match,dict):continue
        match_id=match.get("id")
        if not match_id or match.get("liga") not in (
            "LaLiga","Segunda División","Premier League","Bundesliga",
            "Serie A","Ligue 1"):continue
        try:
            if _utc(match["fecha_utc"])<=now:continue
        except (KeyError,TypeError,ValueError):continue
        league=match["liga"]
        item=totals["por_liga"].setdefault(league,{
            "partidos_futuros":0,"partidos_con_comparaciones":0,
            "comparaciones_recibidas":0,"opciones_validas":0,
            "archivadas_automaticas":0,"ya_archivadas":0,
            "sin_opcion_valida":0,"no_evaluados_sin_api":0
        })
        item["partidos_futuros"]+=1
        previous_reason=prior_reasons.get(match_id)
        record=consulted.get(match_id) or {}
        if match_id in current_by_id:
            reason="ARCHIVADA_INMUTABLE"
        elif match_id in valid_by_id:
            reason="SELECCIONABLE"
        elif not_queried and record and previous_reason in (
                "NO_SUPERA_FILTROS","SIN_CUOTAS_COMPATIBLES"):
            # En un push de código se desactiva la API; no se borran los
            # hallazgos reales de la última consulta ni se crean otros.
            reason=previous_reason
        elif not record and not by_fixture[match_id]:
            reason="SIN_CONSULTAR"
        elif by_fixture[match_id]:
            reason="NO_SUPERA_FILTROS"
        elif record:
            reason="SIN_CUOTAS_COMPATIBLES"
        else:
            reason="SIN_CONSULTAR"
        totals["por_partido"][match_id]=reason
        totals["por_estado_adicional"][reason]=totals["por_estado_adicional"].get(reason,0)+1
        totals["por_partido_detalle"][match_id]={
            "estado":reason,
            "ultima_consulta_utc":record.get("consultado_utc") or None,
            "partido_consultado":bool(record or by_fixture[match_id]),
            "comparaciones_ultima_ejecucion":by_fixture[match_id],
        }
        item["comparaciones_recibidas"]+=by_fixture[match_id]
        item["partidos_con_comparaciones"]+=bool(by_fixture[match_id])
        item["opciones_validas"]+=match_id in valid_by_id
        if match_id in old_ids:
            item["ya_archivadas"]+=1
            totals["abstenciones_ya_archivadas"]+=1
        elif reason=="SIN_CONSULTAR":
            item["no_evaluados_sin_api"]+=1
            totals["partidos_no_evaluados_sin_api"]+=1
        elif reason in ("NO_SUPERA_FILTROS","SIN_CUOTAS_COMPATIBLES"):
            item["sin_opcion_valida"]+=1
            totals["abstenciones_sin_opcion_valida"]+=1
        elif (current_by_id.get(match_id) or {}).get("tipo_cuota")==API:
            item["archivadas_automaticas"]+=1
    totals["reglas"]={
        "maximo_por_partido":1,
        "cuota_decimal_estrictamente_mayor_que":MIN_QUOTE,
        "probabilidad_minima":MIN_AUTO_PROB,
        "ev_teorico_estrictamente_mayor_que":MIN_AUTO_EV,
        "antiguedad_maxima_horas":MAX_QUOTE_HOURS,
        "top3_original":"Archivo inmutable; si la adicional repite mercado y seleccion, se excluye del Top 3 activo (2+1)",
        "historico":"Primera adicional valida archivada antes del inicio; inmutable salvo revisión excepcional del usuario antes del encuentro",
        "orden_seleccion":"Mayor probabilidad del modelo entre cuotas verificadas >1,50 y EV>3%, con calidad mínima",
        "calibracion":"NO_CALIBRADA: muestra prospectiva insuficiente; no confundir probabilidad estimada con acierto probado"
    }
    totals["advertencia"]=(
        "La ordenación prioriza probabilidad estimada, no calibrada prospectivamente. "
        "El valor esperado usa probabilidades experimentales no calibradas. "
        "Las cuotas son observaciones prepartido, no ofertas ejecutadas. "
        "No existe ventaja economica demostrada."
    )
    return totals


def freeze(previous:list[dict],manual:dict,matches:list[dict],now:datetime,
           comparisons:dict|list[dict]|None=None,
           top3:list[dict]|None=None)->list[dict]:
    """Freeze one additional per match; earliest valid pre-match write wins.

    Already archived records including five manual examples are immutable.
    We never post-hoc replace an indicative price with a current API quote.
    """
    old=[dict(x) for x in previous]
    covered={x.get("id") for x in old if x.get("id")}
    new_manual=_manual_candidates(manual,matches,now)
    automatic=(_compared_candidates(matches,comparisons,now,top3)
               if comparisons is not None else _api_candidates(matches,now))
    # For new fixtures observed bookmaker data takes priority over manual
    # indicative examples. The existing 3+1 archive is never changed.
    # A fallback manual record is only used if no eligible real quote exists.
    for row in [*automatic,*new_manual]:
        if not row.get("id") or row["id"] in covered:continue
        old.append(row)
        covered.add(row["id"])
    return old

def evaluate(rows:list[dict],histories:dict,now:datetime)->tuple[list[dict],dict]:
    """Se reaprovecha la liquidación de resultados ya probada."""
    updated=settle(rows,histories,now)
    for r in updated:
        r["retorno_simulado_unidad"]=""
        r["retorno_precio_api_unidad"]=""
        if r.get("estado")!="FINALIZADO":continue
        price=_valid_price(r.get("cuota_decimal"))
        if price is None:continue
        outcome=int(r["resultado"])
        result=(price-1) if outcome else -1.
        r["retorno_simulado_unidad"]=f"{result:.3f}"
        if r.get("tipo_cuota")==API:
            r["retorno_precio_api_unidad"]=f"{result:.3f}"
    return updated,summary(updated,now)

def _group_stats(rows:list[dict])->dict:
    finished=[x for x in rows if x.get("estado")=="FINALIZADO"]
    count=len(finished)
    hits=sum(int(x["resultado"]) for x in finished)
    theoretical=sum(float(x["retorno_simulado_unidad"]) for x in finished)
    brier=sum(float(x["brier"]) for x in finished)/count if count else None
    return {"registradas":len(rows),"evaluadas":count,"aciertos":hits,
            "acierto_pct":round(hits/count*100,2) if count else None,
            "brier_medio":round(brier,6) if count else None,
            "retorno_simulado_unidad":round(theoretical,3) if count else None,
            "roi_simulado_pct":round(theoretical/count*100,2) if count else None,
            "advertencia":"Retorno HIPOTÉTICO de 1 unidad por selección, no dinero apostado, "
                          "no beneficio real ni ventaja financiera demostrada."}

def _api_quote_has_pre_match_proof(row:dict)->bool:
    """Separate timestamped API price evidence from finished match outcomes."""
    if row.get("tipo_cuota")!=API:return False
    try:
        observed=_utc(row["fecha_cuota_utc"])
        frozen=_utc(row["archivado_utc"])
        kickoff=_utc(row["fecha_utc"])
        price=_valid_price(row.get("cuota_decimal"))
        return (price is not None and observed<=frozen<kickoff and
                0<=(frozen-observed).total_seconds()<=6*3600)
    except (KeyError,TypeError,ValueError):
        return False


def verification_summary(rows:list[dict])->dict:
    """A verified settlement never upgrades a historical indicative quote."""
    finished=[r for r in rows if (r.get("estado")=="FINALIZADO" and
              str(r.get("resultado")) in ("0","1"))]
    proven=[r for r in rows if _api_quote_has_pre_match_proof(r)]
    indicative=[r for r in rows if r.get("tipo_cuota")==INDICATIVE]
    return {
        "resultados_verificados":len(finished),
        "resultados_pendientes_o_sin_dato":len(rows)-len(finished),
        "cuotas_api_observadas_antes_del_partido":len(proven),
        "cuotas_indicativas_no_acreditadas":len(indicative),
        "cuotas_api_sin_prueba_temporal":sum(
            r.get("tipo_cuota")==API and not _api_quote_has_pre_match_proof(r)
            for r in rows),
        "nota":"El marcador y la liquidación pueden estar verificados aunque "
               "la cuota sea una referencia no acreditada. Terminar el "
               "partido no demuestra retroactivamente el precio ofrecido."
    }


def summary(rows:list[dict],now:datetime)->dict:
    by_kind=defaultdict(list);by_market=defaultdict(list);by_league=defaultdict(list)
    for r in rows:
        by_kind[r.get("tipo_cuota","DESCONOCIDA")].append(r)
        by_market[r["mercado"]].append(r)
        by_league[r["liga"]].append(r)
    return {"version":VERSION,"generado_utc":now.isoformat(),
            "registradas":len(rows),
            "finalizadas":sum(x.get("estado")=="FINALIZADO" for x in rows),
            "pendientes":sum(x.get("estado")=="PENDIENTE" for x in rows),
            "resultados_no_disponibles":sum(x.get("estado")=="RESULTADO_NO_DISPONIBLE" for x in rows),
            "estadisticas_no_disponibles":sum(x.get("estado")=="ESTADISTICA_NO_DISPONIBLE" for x in rows),
            "excluidas":sum(x.get("estado","").startswith("EXCLUIDO") for x in rows),
            "verificacion":verification_summary(rows),
            "global":_group_stats(rows),
            "por_tipo_cuota":{k:_group_stats(v) for k,v in by_kind.items()},
            "por_mercado":{k:_group_stats(v) for k,v in by_market.items()},
            "por_liga":{k:_group_stats(v) for k,v in by_league.items()},
            "nota":"Las referencias sin fecha ni oferta contrastada se liquidan solo como "
                   "escenario hipotético; jamás como rentabilidad o cuota real. "
                   "Las selecciones quedan congeladas antes del encuentro."}

def markdown(rows:list[dict],report:dict)->str:
    lines=["# Football AI Lab · Seguimiento de cuotas superiores a 1,50","",
           "**Estudio experimental: no se efectuaron apuestas ni se verificaron las cuotas indicativas.**","",
           f'**Registradas:** {report["registradas"]} · '
           f'**Finalizadas:** {report["finalizadas"]} · '
           f'**Pendientes:** {report["pendientes"]}',"",
           "| Partido | Mercado | Prob. modelo | Cuota orientativa/API | Resultado | Simulación 1 u. |",
           "|---|---|---:|---:|---|---:|"]
    for r in rows:
        status=r.get("estado","")
        result=("Acertada" if r.get("resultado")=="1" else
                "Fallada" if r.get("resultado")=="0" else
                "Sin estadística" if status=="ESTADISTICA_NO_DISPONIBLE" else
                "Sin resultado" if status=="RESULTADO_NO_DISPONIBLE" else "Pendiente")
        lines.append(f'| {r["local"]} – {r["visitante"]} | '
                     f'{r["seleccion"]} ({r["tipo_cuota"]}) | '
                     f'{float(r["probabilidad"])*100:.1f}% | {float(r["cuota_decimal"]):.2f} | '
                     f'{result} | {r.get("retorno_simulado_unidad") or "—"} |')
    if not rows:lines.append("| Sin selecciones registradas | — | — | — | — | — |")
    lines.extend(["","Las cuotas **INDICATIVA_NO_VERIFICADA** proceden de referencias "
                  "conversacionales sin prueba de precio realmente ofertado. "
                  "El retorno es hipotético y no mide ganancias ni calidad del precio.",
                  "Una cuota API registrada tampoco implica que se haya realizado una apuesta."])
    return "\n".join(lines)+"\n"
