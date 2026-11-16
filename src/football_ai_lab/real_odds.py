"""Fase 8: comparación *informativa* con cuotas prepartido verificables.

The Odds API V4 es OPT-IN: sin clave + bandera activada no realiza peticiones.
Solo h2h 1X2 y goles totales con EXACTAMENTE la línea y dirección del modelo.
No deduce "cuotas reales" de estimaciones, históricos ni combinaciones 1X/X2.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from math import isfinite
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import os
import re
from collections import defaultdict

from .core import normalize_team
from .sources import LEAGUES
from .free_odds import collect_free_odds, FIVE_NAME, API_NAME

VERSION = "real-odds-comparator-1.0"
API_ROOT = "https://api.the-odds-api.com/v4/sports/"
SOURCE = "The Odds API V4"
LEAGUE_SPORTS = {
    "SP1": "soccer_spain_la_liga",
    "SP2": "soccer_spain_segunda_division",
    "E0": "soccer_epl",
    "D1": "soccer_germany_bundesliga",
    "I1": "soccer_italy_serie_a",
    "F1": "soccer_france_ligue_one",
}
LABEL_CODES = {label[0]: code for code, label in LEAGUES.items()}
MAX_REQUESTS = 6
MAX_MATCH_DIFF = timedelta(hours=2)
MAX_QUOTE_AGE = timedelta(hours=24)
MAX_ROWS = 5000
MAX_HISTORY = 12000


def _utc(value):
    try:
        dt = value if isinstance(value,datetime) else datetime.fromisoformat(
            str(value).replace("Z","+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (TypeError,ValueError,OverflowError):
        return None


def _price(value):
    try:
        if isinstance(value,bool):
            return None
        x = float(value)
        return x if isfinite(x) and 1.001 < x <= 1000 else None
    except (ValueError,TypeError):
        return None


def _prob(value):
    try:
        if isinstance(value,bool):
            return None
        x = float(value)
        return x if isfinite(x) and 0 < x < 1 else None
    except (TypeError,ValueError):
        return None


def _team_equal(a,b):
    return bool(normalize_team(a) and normalize_team(a)==normalize_team(b))


def _fetch_api(url):
    request=Request(url,headers={
        "Accept":"application/json",
        "User-Agent":"FootballAILab/1.0 (personal research)"
    })
    with urlopen(request,timeout=15) as response:
        return response.read(5_000_000)


def _allowed_leagues(raw):
    candidates=[x.strip().upper() for x in str(raw or "").split(",") if x.strip()]
    chosen=list(dict.fromkeys(x for x in candidates if x in LEAGUE_SPORTS))
    return chosen if candidates else list(LEAGUE_SPORTS)


def _find_fixture(event, fixtures, code, now):
    """Rechaza cruces inciertos, nombres iguales, horarios incompatibles y duplicados."""
    if event.get("sport_key") and event["sport_key"]!=LEAGUE_SPORTS[code]:
        return None
    start=_utc(event.get("commence_time"))
    if start is None or start <= now or not event.get("id"):
        return None
    h,a=event.get("home_team",""),event.get("away_team","")
    if not h or not a or _team_equal(h,a):
        return None
    found=[]
    for fixture in fixtures:
        if LABEL_CODES.get(fixture.get("liga"))!=code:
            continue
        kickoff=_utc(fixture.get("fecha_utc"))
        if kickoff is None or kickoff<=now or abs(kickoff-start)>MAX_MATCH_DIFF:
            continue
        if _team_equal(fixture.get("local",""),h) and _team_equal(fixture.get("visitante",""),a):
            found.append(fixture)
    return found[0] if len(found)==1 else None


def _unambiguous_points(market):
    """Cuotas con mercado completo para estimar el margen de UNA misma casa."""
    name=market.get("key")
    if name=="h2h":
        return [(None,market.get("outcomes") or [])]
    if name!="totals":
        return []
    groups=defaultdict(list)
    for o in market.get("outcomes") or []:
        try:
            pt=float(o.get("point"))
            if isfinite(pt) and 0.5<=pt<=10.5 and abs(pt%1-0.5)<1e-6:
                groups[pt].append(o)
        except (TypeError,ValueError,AttributeError):
            continue
    return sorted(groups.items())


def _book_quotes(event,fixture,now,code):
    event_start=_utc(event["commence_time"])
    output=[]
    for book in event.get("bookmakers") or []:
        if not isinstance(book,dict):
            continue
        bookmaker_key=str(book.get("key") or "").strip()
        title=str(book.get("title") or "").strip()[:80]
        if not bookmaker_key or not title:
            continue
        for market in book.get("markets") or []:
            if not isinstance(market,dict) or market.get("key") not in ("h2h","totals"):
                continue
            changed=_utc(market.get("last_update") or book.get("last_update"))
            if changed is None or changed>now+timedelta(minutes=5) or now-changed>MAX_QUOTE_AGE:
                continue
            if changed>=event_start:
                continue
            for point,outcomes in _unambiguous_points(market):
                named={}
                for o in outcomes:
                    if not isinstance(o,dict):
                        continue
                    label=str(o.get("name") or "").strip()
                    price=_price(o.get("price"))
                    if price is None:
                        continue
                    key=None
                    if market["key"]=="h2h":
                        if _team_equal(label,event["home_team"]):
                            key="1"
                        elif _team_equal(label,event["away_team"]):
                            key="2"
                        elif label.casefold() in ("draw","tie","empate"):
                            key="X"
                    elif market["key"]=="totals":
                        if label.casefold()=="over":
                            key="over"
                        elif label.casefold()=="under":
                            key="under"
                    if key is None:
                        continue
                    # Rechazar el mercado con resultados contradictorios duplicados.
                    if key in named and named[key]!=price:
                        named[key]=None
                    else:
                        named[key]=price
                required=("1","X","2") if market["key"]=="h2h" else ("over","under")
                if any(named.get(k) is None for k in required):
                    continue
                margin=sum(1/named[k] for k in required)-1
                if not (-0.02<=margin<=0.45):
                    continue
                sum_implied=1+margin
                for outcome in required:
                    price=named[outcome]
                    output.append({
                        "fixture_id":fixture["id"],"liga":fixture["liga"],
                        "local":fixture["local"],"visitante":fixture["visitante"],
                        "fecha_utc":fixture["fecha_utc"],
                        "evento_id":str(event["id"])[:100],
                        "bookmaker_id":bookmaker_key[:100],"bookmaker":title,
                        "mercado":market["key"],"resultado":outcome,
                        "linea":point,"cuota":round(price,4),
                        "probabilidad_implicita":round(1/price,7),
                        "probabilidad_sin_margen":round((1/price)/sum_implied,7),
                        "margen_casa":round(margin,7),
                        "actualizado_utc":changed.isoformat(),
                        "capturado_utc":now.isoformat(),
                        "proveedor":SOURCE,
                        "fuente":"https://the-odds-api.com/",
                    })
    return output


def retrieve_odds(fixtures,now,env=None,fetcher=None):
    """Obtiene 0–6 ligas con un máximo de 2 mercados y una región por liga.

    Captura ausente o error: devuelve vacío, NO conserva cuota antigua como actual.
    """
    env=env or {}
    now=_utc(now)
    if now is None:
        raise ValueError("now debe ser UTC aware")
    key=str(env.get("THE_ODDS_API_KEY") or "").strip()
    enabled=str(env.get("ENABLE_REAL_ODDS") or "").lower() in ("1","true","yes")
    report={
        "version":VERSION,"capturado_utc":now.isoformat(),
        "proveedor":SOURCE,"origen":"API V4, cuotas prepartido, región UE",
        "mercados_consultados":["h2h","totals"],"ligas_solicitadas":[],
        "ligas_respondidas":[],"errores_proveedor":0,"partidos_cruzados":0,
        "cuotas_validadas":0,"estimacion_creditos_maximos":0,
        "fuente":"https://the-odds-api.com/liveapi/guides/v4/",
        "estado":"DESACTIVADO" if not enabled else "SIN_CLAVE" if not key else "INICIADO",
        "advertencia":"Precios observados, no garantías de disponibilidad ni de ejecución.",
    }
    if not key or not enabled:
        return {"version":VERSION,"capturado_utc":now.isoformat(),
                "estado":report["estado"],"auditoria":report,"cuotas":[]}
    fetcher=fetcher or _fetch_api
    requested=_allowed_leagues(env.get("REAL_ODDS_LEAGUES",""))
    limit=min(MAX_REQUESTS,len(requested))
    requested=requested[:limit]
    report["ligas_solicitadas"]=requested
    report["estimacion_creditos_maximos"]=len(requested)*2
    all_quotes=[]
    matched=set()
    for code in requested:
        sport=LEAGUE_SPORTS[code]
        params=urlencode({"apiKey":key,"regions":"eu","markets":"h2h,totals",
                          "oddsFormat":"decimal","dateFormat":"iso"})
        # Nunca mostrar la URL completa en logs, errores, resultados o JSON.
        url=f"{API_ROOT}{sport}/odds/?{params}"
        try:
            raw=fetcher(url)
            events=json.loads(raw)
            if not isinstance(events,list):
                raise ValueError("Formato de cuotas inesperado")
            report["ligas_respondidas"].append(code)
            for event in events:
                if not isinstance(event,dict):
                    continue
                fixture=_find_fixture(event,fixtures,code,now)
                if fixture is None:
                    continue
                matched.add(fixture["id"])
                all_quotes.extend(_book_quotes(event,fixture,now,code))
        except Exception as exc:
            # No imprimir mensajes de excepción: podrían contener la URL con API key.
            report["errores_proveedor"]+=1
            report.setdefault("tipos_error",[]).append(type(exc).__name__)
    # Impedir que un evento ambiguo de proveedor aporte dos cuotas incompatibles.
    key_fields=("fixture_id","bookmaker_id","mercado","resultado","linea")
    dedup={}
    conflicts=set()
    for q in all_quotes:
        ident=tuple(q[k] for k in key_fields)
        if ident in dedup and dedup[ident]["evento_id"]!=q["evento_id"]:
            conflicts.add(ident)
        if ident not in dedup:
            dedup[ident]=q
    quotes=[q for ident,q in dedup.items() if ident not in conflicts][:MAX_ROWS]
    quotes.sort(key=lambda x:(x["fecha_utc"],x["fixture_id"],x["bookmaker"],x["mercado"],str(x["linea"]),x["resultado"]))
    report["partidos_cruzados"]=len(matched)
    report["cuotas_validadas"]=len(quotes)
    report["eventos_ambiguos"]=len(conflicts)
    report["estado"]="PARCIAL" if report["errores_proveedor"] else "CON_CUOTAS" if quotes else "SIN_COINCIDENCIAS"
    return {"version":VERSION,"capturado_utc":now.isoformat(),
            "estado":report["estado"],"auditoria":report,"cuotas":quotes}


def _model_outcome(market,selection,fixture):
    if market=="result":
        if selection==fixture.get("local","")+" gana":
            return ("h2h","1",None)
        if selection==fixture.get("visitante","")+" gana":
            return ("h2h","2",None)
        if selection=="Empate":
            return ("h2h","X",None)
        return None
    if market=="goals":
        match=re.fullmatch(r"(Más|Menos) de (\d+[,.]\d+) goles",selection)
        if not match:
            return None
        point=float(match.group(2).replace(",","."))
        if abs(point%1-.5)>1e-6 or not 0.5<=point<=10.5:
            return None
        return ("totals","over" if match.group(1)=="Más" else "under",point)
    if market in ("corners","yellow"):
        m=re.fullmatch(r"(Más|Menos) de (\d+[,.]\d+) (?:córners|tarjetas amarillas) totales",selection)
        if m is None:
            return None
        line=float(m.group(2).replace(",","."))
        if line<.5 or line>25.5 or abs(line%1-.5)>1e-6:
            return None
        return (market,"over" if m.group(1)=="Más" else "under",line)
    if market=="btts":
        if selection in ("Sí","Si"):return ("btts","yes",None)
        if selection=="No":return ("btts","no",None)
    # Sin cuotas verificadas para 1X/X2/12, tiros y combinados.
    return None


def compare_forecasts(fixtures,quotes_payload,now):
    now=_utc(now)
    if now is None:
        raise ValueError("now debe ser timezone aware")
    quotes=quotes_payload.get("cuotas") or []
    by_fixture=defaultdict(list)
    for quote in quotes:
        # Defensas también para JSONs manipulados por terceros.
        updated=_utc(quote.get("actualizado_utc"))
        kickoff=_utc(quote.get("fecha_utc"))
        price=_price(quote.get("cuota"))
        if not (updated and kickoff and price and
                updated<=now+timedelta(minutes=5) and now-updated<=MAX_QUOTE_AGE
                and kickoff>now and updated<kickoff and quote.get("proveedor") in (SOURCE,FIVE_NAME,API_NAME)):
            continue
        by_fixture[quote.get("fixture_id")].append(quote)
    output=[]
    fixtures_seen=0
    for match in fixtures:
        if not match.get("id") or _utc(match.get("fecha_utc")) is None:
            continue
        if _utc(match["fecha_utc"])<=now:
            continue
        candidates=by_fixture.get(match["id"],[])
        if not candidates:
            continue
        fixtures_seen+=1
        for cat in ("result","goals","corners","yellow","btts"):
            rows=(match.get("mercados") or {}).get(cat) or []
            for forecast in rows:
                if not isinstance(forecast,dict):
                    continue
                target=_model_outcome(cat,str(forecast.get("seleccion") or ""),match)
                p=_prob(forecast.get("probabilidad"))
                if target is None or p is None:
                    continue
                market,selection,line=target
                matches=[q for q in candidates if q.get("mercado")==market
                         and q.get("resultado")==selection and q.get("linea")==line]
                for q in matches:
                    # Estimaciones: diferencial y EV hipotético NO predicen beneficio.
                    price=q["cuota"]
                    output.append({
                        "fixture_id":match["id"],"liga":match["liga"],
                        "local":match["local"],"visitante":match["visitante"],
                        "fecha_utc":match["fecha_utc"],
                        "categoria":cat,
                        "seleccion":forecast["seleccion"],
                        "probabilidad_modelo":p,
                        "nivel":forecast.get("nivel",""),
                        "posicion_top3":forecast.get("posicion_top3"),
                        "cuota_justa_teorica":round(1/p,4),
                        "cuota_real":price,"bookmaker":q["bookmaker"],
                        "bookmaker_id":q["bookmaker_id"],
                        "mercado_proveedor":market,
                        "resultado_proveedor":selection,"linea":line,
                        "p_implicita":q["probabilidad_implicita"],
                        "p_mercado_sin_margen":q["probabilidad_sin_margen"],
                        "margen_casa":q["margen_casa"],
                        "diferencia_puntos_pct":round((p-q["probabilidad_sin_margen"])*100,2),
                        "ev_teorico_unidad":round(p*price-1,4),
                        "actualizado_utc":q["actualizado_utc"],
                        "capturado_utc":q["capturado_utc"],
                        "evento_id":q["evento_id"],
                        "fuente":q["fuente"],"proveedor":q["proveedor"],
                        "marca_tiempo_tipo":q.get("marca_tiempo_tipo","ACTUALIZACION_PROVEEDOR"),
                        "fase_cuota":q.get("fase_cuota","OBSERVADA_PREPARTIDO"),
                        "definicion_mercado":q.get("definicion_mercado",""),
                        "etiqueta":"COMPARACION_INFORMATIVA_NO_VALIDADA",
                    })
    output.sort(key=lambda x:(x["fecha_utc"],x["fixture_id"],x["categoria"],x["seleccion"],x["bookmaker"]))
    audit={
        "capturado_utc":now.isoformat(),"precios_comparados":len(output),
        "partidos_con_precios":len({x["fixture_id"] for x in output}),
        "partidos_candidatos":len(fixtures),
        "partidos_proveedor":fixtures_seen,
        "mercados_soportados":["1X2","Total goles","Córners totales","Amarillas explícitas","Ambos marcan"],
        "mercados_sin_cuota_verificada":["Doble oportunidad","Tiros","Faltas",
                                        "Tarjetas genéricas sin regla de amarillas"],
        "metodologia":"Cuota decimal de bookmaker y pronóstico para el mismo mercado, "
                      "línea, dirección, equipos y partido futuro. Margen retirado solo "
                      "dentro del mismo bookmaker y mercado completo.",
        "advertencia":"EV calculado con probabilidad no calibrada; NO demuestra ventaja "
                       "real, rentabilidad ni disponibilidad de la cuota.",
    }
    return {"version":VERSION,"capturado_utc":now.isoformat(),
            "estado":quotes_payload.get("estado","SIN_CUOTAS"),
            "auditoria":audit,"comparaciones":output}


def archive_snapshots(previous,quotes_payload,now):
    """Histórico acumulado solo con cuotas realmente observadas antes del inicio.

    Al fallar la API se conserva el histórico, pero la vista ACTUAL queda vacía.
    """
    now=_utc(now)
    if now is None:
        raise ValueError("now necesita timezone")
    unique={}
    for row in previous if isinstance(previous,list) else []:
        if not isinstance(row,dict):
            continue
        key=(row.get("capturado_utc","")[:10],row.get("proveedor"),row.get("fixture_id"),
             row.get("evento_id"),row.get("bookmaker_id"),row.get("mercado"),
             row.get("resultado"),str(row.get("linea")))
        if all(key[:6]):
            unique[key]=row
    before=len(unique)
    for row in quotes_payload.get("cuotas") or []:
        if _utc(row.get("fecha_utc")) is None or _utc(row["fecha_utc"])<=now:
            continue
        key=(row["capturado_utc"][:10],row["proveedor"],row["fixture_id"],row["evento_id"],
             row["bookmaker_id"],row["mercado"],row["resultado"],str(row["linea"]))
        # Conservar la primera observación del día, no sobrescribirla.
        unique.setdefault(key,dict(row))
    ordered=sorted(unique.values(),key=lambda x:(x.get("capturado_utc",""),x.get("fixture_id","")))
    return {
        "version":VERSION,"actualizado_utc":now.isoformat(),
        "cuotas":ordered[-MAX_HISTORY:],
        "observaciones_nuevas":max(0,len(unique)-before),
        "nota":"Archivo de primeras cuotas observadas por día, nunca un histórico "
               "reconstruido. Sin credenciales no se añaden observaciones ficticias.",
    }


def build_real_odds(fixtures,now,existing=None,env=None,fetcher=None,
                    five_fetcher=None,api_fetcher=None):
    """Unifica fuentes sin cambiar los pronósticos ni modificar el Top3.

    Sin claves o banderas no hay consultas HTTP. Cada fuente conserva
    proveedor, bookmaker, fecha y tipo de mercado en sus observaciones.
    """
    env=env or {}
    original=retrieve_odds(fixtures,now,env=env,fetcher=fetcher)
    free=collect_free_odds(fixtures,now,env=env,
                           five_fetcher=five_fetcher,api_fetcher=api_fetcher)
    quotes=[*original["cuotas"],*free["cuotas"]]
    audit=dict(original["auditoria"])
    audit["fuentes_gratuitas"]=free["auditoria"]["fuentes_gratuitas"]
    audit["proveedores_activos"]=sorted(set(q["proveedor"] for q in quotes))
    audit["cuotas_validadas"]=len(quotes)
    audit["partidos_cruzados"]=len(set(q["fixture_id"] for q in quotes))
    statuses=(original["estado"],free["estado"])
    if any(s=="PARCIAL" for s in statuses):
        status="PARCIAL"
    elif quotes:
        status="CON_CUOTAS"
    elif all(s=="DESACTIVADO" for s in statuses):
        status="DESACTIVADO"
    elif all(s in ("SIN_CLAVE","DESACTIVADO") for s in statuses):
        status="SIN_CLAVE" if any(s=="SIN_CLAVE" for s in statuses) else "DESACTIVADO"
    else:
        status="SIN_COINCIDENCIAS"
    quote_payload={"version":VERSION,"capturado_utc":_utc(now).isoformat(),
                   "estado":status,"auditoria":audit,"cuotas":quotes}
    comparison=compare_forecasts(fixtures,quote_payload,now)
    archive=archive_snapshots((existing or {}).get("cuotas") or [],quote_payload,now)
    return quote_payload,comparison,archive
