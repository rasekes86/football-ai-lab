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
    "retorno_simulado_unidad","retorno_precio_api_unidad"
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

def freeze(previous:list[dict],manual:dict,matches:list[dict],now:datetime)->list[dict]:
    """El primer registro prepartido gana; posteriores recálculos no lo reescriben."""
    old=[dict(x) for x in previous]
    known={x["clave"] for x in old if x.get("clave")}
    for c in _manual_candidates(manual,matches,now)+_api_candidates(matches,now):
        if c["clave"] in known:continue
        old.append(c);known.add(c["clave"])
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
