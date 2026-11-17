"""Fuentes gratuitas opcionales: 5DollarFootballAPI y API-Football.

Claves sólo en cabeceras HTTP. Consultas acotadas, sin scraping ni API pagada.
Cuotas prepartido capturadas; no interpretamos una línea de tarjetas
GENÉRICA como "amarillas" sin reglas de liquidación explícitas.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from collections import defaultdict
import json
import math
import os
import re

from .core import normalize_team
from .sources import LEAGUES

FIVE_NAME = "5DollarFootballAPI"
API_NAME = "API-Football"
FIVE_URL = "https://api.5dollarfootballapi.com/v1"
API_URL = "https://v3.football.api-sports.io"
FIVE_CODES = {"LaLiga":"SP1", "Premier League":"E0",
              "Bundesliga":"D1","Serie A":"I1","Ligue 1":"F1",
              "Segunda División":"SP2"}
LEAGUE_ALIASES = {
    "SP1":("la liga","laliga","primera division","spain la liga"),
    "SP2":("segunda division","laliga 2","laliga hypermotion","la liga 2"),
    "E0":("premier league","english premier league"),
    "D1":("bundesliga","germany bundesliga"),
    "I1":("serie a","italy serie a"),
    "F1":("ligue 1","france ligue 1"),
}
MAX_FIVE_ODDS=14
MAX_API_ODDS=8
MAX_DAYS=5
MAX_DIFF=timedelta(hours=2)


def _now(dt):
    if not isinstance(dt,datetime) or dt.tzinfo is None:
        raise ValueError("UTC-aware now obligatorio")
    return dt.astimezone(timezone.utc)


def _dt(value):
    try:
        result=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError,ValueError,OverflowError):
        return None


def _bounded(value,default,maximum):
    try:
        number=int(str(value))
        return number if 0<=number<=maximum else default
    except (TypeError,ValueError):
        return default


def _price(v):
    try:
        if isinstance(v,bool):return None
        n=float(v)
        return n if math.isfinite(n) and 1.001<n<1000 else None
    except (TypeError,ValueError):return None


def _num(v):
    try:
        if isinstance(v,bool):return None
        n=float(v)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None


def _league_code(name):
    clean=normalize_team(name)
    for code,aliases in LEAGUE_ALIASES.items():
        if clean in [normalize_team(alias) for alias in aliases]:
            return code
    return None


def _match(fixture, fixtures, now):
    """One unique future fixture, same league, teams, home/away and kickoff."""
    teams=fixture.get("teams") or {}
    home=(teams.get("home") or {}).get("name") if isinstance(teams,dict) else None
    away=(teams.get("away") or {}).get("name") if isinstance(teams,dict) else None
    code=_league_code((fixture.get("league") or {}).get("name",""))
    kick=_dt(fixture.get("kickoff_utc") or fixture.get("date"))
    if not home or not away or not code or kick is None or kick<=now:
        return None
    candidates=[
        row for row in fixtures
        if FIVE_CODES.get(row.get("liga"))==code
        and _dt(row.get("fecha_utc")) is not None
        and _dt(row["fecha_utc"])>now
        and abs(_dt(row["fecha_utc"])-kick)<=MAX_DIFF
        and normalize_team(row.get("local"))==normalize_team(home)
        and normalize_team(row.get("visitante"))==normalize_team(away)
        and normalize_team(home)!=normalize_team(away)
    ]
    return candidates[0] if len(candidates)==1 else None


def _http(url, headers):
    request=Request(url,headers={**headers,"Accept":"application/json",
                                  "User-Agent":"FootballAILab/1.0"})
    with urlopen(request, timeout=13) as response:
        return json.loads(response.read(3_000_000))


def _group(odds, names):
    """Only complete markets, identical bookmaker, line and stage."""
    prices={name:_price(odds.get(name)) for name in names}
    if any(p is None for p in prices.values()):
        return None
    overround=sum(1/p for p in prices.values())-1
    if not -0.02<=overround<=.45:
        return None
    return prices,overround


def _emit(match,event_id,bookmaker,book_id,provider,market,outcome,line,prices,
          overround,now,provider_timestamp=None,definition=None,stage=None):
    price=prices[outcome]
    source=("https://5dollarfootballapi.com/" if provider==FIVE_NAME
            else "https://www.api-football.com/")
    return {
        "fixture_id":match["id"],"liga":match["liga"],
        "local":match["local"],"visitante":match["visitante"],
        "fecha_utc":match["fecha_utc"],"evento_id":str(event_id)[:90],
        "bookmaker":str(bookmaker)[:90],"bookmaker_id":str(book_id)[:90],
        "mercado":market,"resultado":outcome,"linea":line,
        "cuota":round(price,4),
        "probabilidad_implicita":round(1/price,7),
        "probabilidad_sin_margen":round((1/price)/(1+overround),7),
        "margen_casa":round(overround,7),
        # Si no se facilita marca de actualización real, no la inventamos:
        "actualizado_utc":provider_timestamp.isoformat() if provider_timestamp else now.isoformat(),
        "marca_tiempo_tipo":"ACTUALIZACION_PROVEEDOR" if provider_timestamp else "CAPTURA_NO_ACTUALIZACION",
        "capturado_utc":now.isoformat(),"proveedor":provider,"fuente":source,
        "fase_cuota":stage or "ULTIMO_PRECIO_PREPARTIDO_OBSERVADO",
        "definicion_mercado":definition or "Mercado y línea exactos",
    }


def _five_fixture_rows(match, event_id, odds_payload, now):
    output=[]
    for bk in odds_payload.get("bookmakers") or []:
        if not isinstance(bk,dict):continue
        book_id=str(bk.get("slug") or "").strip()
        if book_id!="bet365":continue # Plan Free: único bookmaker autorizado.
        markets=bk.get("odds") or {}
        if not isinstance(markets,dict):continue
        for api_key,market,choices in (
            ("1x2","h2h",("1","X","2")),
            ("goal_line","totals",("over","under")),
            ("corner_line","corners",("over","under")),
            ("btts","btts",("yes","no")),
        ):
            data=markets.get(api_key) or {}
            if not isinstance(data,dict):continue
            # closing es la última cuota PREPARTIDO disponible hasta ahora,
            # NO una cuota de cierre final con la que ya se haya jugado.
            stage=data.get("closing")
            if not isinstance(stage,dict):
                continue
            if api_key=="1x2":
                pts={"1":stage.get("home"),"X":stage.get("draw"),"2":stage.get("away")}
                line=None
            else:
                pts={name:stage.get(name) for name in choices}
                line=_num(stage.get("line")) if api_key!="btts" else None
                if api_key in ("goal_line","corner_line") and (
                    line is None or line<.5 or line>25.5
                    or abs(line%1-.5)>1e-6):
                    # Excluye enteros y cuartos asiáticos con devolución.
                    continue
            checked=_group(pts,choices)
            if not checked:continue
            prices,margin=checked
            for outcome in choices:
                output.append(_emit(match,event_id,bk.get("name") or "Bet365",
                    book_id,FIVE_NAME,market,outcome,line,prices,margin,now,
                    stage="ULTIMA_CUOTA_PREPARTIDO",definition=(
                        "Córners totales FT (línea media)" if market=="corners"
                        else "1X2 FT" if market=="h2h"
                        else "Total goles FT" if market=="totals"
                        else "Ambos marcan FT")))
        ladder=markets.get("goal_line_fixed") or []
        for entry in ladder if isinstance(ladder,list) else []:
            if not isinstance(entry,dict):continue
            line=_num(entry.get("line"))
            if line is None or not .5<=line<=9.5 or abs(line%1-.5)>1e-6:
                continue
            stage=entry.get("closing")
            if not isinstance(stage,dict):continue
            checked=_group(stage,("over","under"))
            if not checked:continue
            prices,margin=checked
            # No duplicar la principal y la escalera para la misma línea.
            existing={(o["mercado"],o["linea"],o["resultado"]) for o in output
                      if o["bookmaker_id"]==book_id}
            for outcome in ("over","under"):
                if ("totals",line,outcome) in existing:continue
                output.append(_emit(match,event_id,bk.get("name") or "Bet365",
                    book_id,FIVE_NAME,"totals",outcome,line,prices,margin,now,
                    stage="ULTIMA_CUOTA_PREPARTIDO",definition="Goles totales FT / línea fija"))
        # Los mercados card_line son TARJETAS GENÉRICAS y NO se pueden
        # confundir con amarillas del modelo: quedan deliberadamente excluidos.
    return output


def get_five_odds(fixtures,now,env=None,fetcher=None):
    now=_now(now);env=env or {};fetcher=fetcher or _http
    enabled=str(env.get("ENABLE_FREE_ODDS","")).lower() in ("1","true","yes")
    key=str(env.get("FIVEDOLLAR_API_KEY","")).strip()
    status="DESACTIVADO" if not enabled else "SIN_CLAVE" if not key else "CONSULTANDO"
    audit={"proveedor":FIVE_NAME,"estado":status,"consultas":0,"partidos":0,
           "eventos_emparejados":0,"errores":0,"cuotas":0,
           "no_equivalente":["Tarjetas genéricas ≠ amarillas verificadas"],
           "limite_gratuito":"60 solicitudes/hora en plan Free; no se garantiza la cobertura"}
    if not enabled or not key:return {"estado":status,"cuotas":[],"auditoria":audit}
    limit=_bounded(env.get("FREE_ODDS_MAX_FIXTURES") or MAX_FIVE_ODDS,MAX_FIVE_ODDS,MAX_FIVE_ODDS)
    headers={"Authorization":f"Bearer {key}"}
    selected=[f for f in fixtures if _dt(f.get("fecha_utc")) and _dt(f["fecha_utc"])>now]
    # Ventanas de días UTC completos (el proveedor limita a 24h).
    days=sorted({ _dt(f["fecha_utc"]).date() for f in selected
                  if _dt(f["fecha_utc"])<=now+timedelta(days=MAX_DAYS)})
    # Recoger primero todos los encuentros compatibles de la ventana.
    # Sin esta fase, los primeros 14 de un fin de semana consumen el cupo
    # y pueden excluir por completo a Premier League y Bundesliga.
    candidates={}
    ambiguous=set()
    provider_rows=defaultdict(int)
    unmatched_rows=defaultdict(int)
    unrecognized_leagues=0
    for day in days:
        begin=datetime.combine(day,datetime.min.time(),tzinfo=timezone.utc)
        url=f"{FIVE_URL}/fixtures?"+urlencode({
            "start_time":int(begin.timestamp()),"end_time":int((begin+timedelta(days=1)).timestamp()),
            "status":"scheduled","per_page":100,
        })
        try:
            obj=fetcher(url,headers);audit["consultas"]+=1
            if not isinstance(obj,dict) or obj.get("success") not in (1,True):
                raise ValueError("Respuesta sin éxito")
            entries=obj.get("data") or []
            if not isinstance(entries,list):raise ValueError("Formato de calendario inválido")
            for event in entries:
                if not isinstance(event,dict) or not event.get("id"):continue
                raw_league=(event.get("league") or {}).get("name","")
                code=_league_code(raw_league)
                if code:
                    provider_rows[code]+=1
                else:
                    unrecognized_leagues+=1
                match=_match(event,selected,now)
                if not match:
                    if code:unmatched_rows[code]+=1
                    continue
                ident=match["id"]
                if ident in candidates and str(candidates[ident][1]["id"])!=str(event["id"]):
                    ambiguous.add(ident) # Nunca elegir un evento de API ambiguo.
                else:
                    candidates.setdefault(ident,(match,event))
        except Exception:
            audit["errores"]+=1
    for ident in ambiguous:
        candidates.pop(ident,None)

    # Repartir las consultas de /odds por rondas de ligas. Se mantiene
    # exactamente el máximo anterior (14): no aumenta el consumo del plan Free.
    by_league=defaultdict(list)
    for match,event in candidates.values():
        by_league[match["liga"]].append((match,event))
    for games in by_league.values():
        games.sort(key=lambda pair:(_dt(pair[0]["fecha_utc"]),str(pair[0]["id"])))
    league_order=("LaLiga","Premier League","Bundesliga","Serie A",
                  "Ligue 1","Segunda División")
    balanced=[]
    while len(balanced)<limit:
        advanced=False
        for league in league_order:
            if by_league.get(league):
                balanced.append(by_league[league].pop(0))
                advanced=True
                if len(balanced)>=limit:break
        if not advanced:break

    # Conteos anónimos, nunca nombres de eventos de terceros ni credenciales.
    audit["eventos_api_por_liga"]=dict(sorted(provider_rows.items()))
    audit["sin_emparejar_por_liga"]=dict(sorted(unmatched_rows.items()))
    audit["ligas_no_reconocidas_total"]=unrecognized_leagues
    audit["eventos_emparejados"]=len(candidates)
    audit["ligas_emparejadas"]=sorted({m["liga"] for m,_ in candidates.values()})
    audit["ligas_seleccionadas"]=sorted({m["liga"] for m,_ in balanced})
    audit["partidos_por_liga"]={
        league:sum(m["liga"]==league for m,_ in balanced)
        for league in league_order if any(m["liga"]==league for m,_ in balanced)
    }
    quotes=[]
    for match,event in balanced:
        try:
            obj=fetcher(f"{FIVE_URL}/fixtures/{event['id']}/odds",headers)
            audit["consultas"]+=1
            if not isinstance(obj,dict) or obj.get("success") not in (1,True):
                raise ValueError("Respuesta de cuotas inválida")
            payload=obj.get("data") or {}
            if str(payload.get("fixture_id"))!=str(event["id"]):continue
            quotes.extend(_five_fixture_rows(match,event["id"],payload,now))
        except Exception:
            audit["errores"]+=1
    audit["partidos"]=len(balanced)
    audit["cuotas"]=len(quotes)
    audit["ligas_con_cuotas"]=sorted({q["liga"] for q in quotes})
    audit["estado"]="PARCIAL" if audit["errores"] else "CON_CUOTAS" if quotes else "SIN_COINCIDENCIAS"
    return {"estado":audit["estado"],"cuotas":quotes,"auditoria":audit}

def _api_values(bet):
    """No se infieren bet IDs. Identificamos nombres explícitos de mercado."""
    name=str(bet.get("name") or "").strip().lower()
    if name in ("match winner","1x2","fulltime result"):
        market="h2h"
    elif name in ("goals over/under","total goals","over/under goals"):
        market="totals"
    elif name in ("total corners","corners over/under","total corners over/under"):
        market="corners"
    elif name in ("total yellow cards","yellow cards over/under","total yellow cards over/under"):
        market="yellow"
    elif name in ("both teams score","both teams to score","both teams score (yes/no)"):
        market="btts"
    else:
        return []
    groups=defaultdict(dict)
    for item in bet.get("values") or []:
        if not isinstance(item,dict):continue
        price=_price(item.get("odd"))
        if price is None:continue
        v=str(item.get("value") or "").strip().lower()
        p=None;out=None
        if market=="h2h":
            out={"home":"1","draw":"X","away":"2"}.get(v)
        elif market=="btts":
            out={"yes":"yes","no":"no"}.get(v)
        else:
            m=re.fullmatch(r"(over|under)\s+(\d+(?:[.,]\d+)?)",v)
            if m:
                out=m.group(1);p=_num(m.group(2).replace(",","."))
                if p is None or not .5<=p<=25.5 or abs(p%1-.5)>1e-6:
                    continue
        if out is not None:
            if out in groups[p]:
                groups[p][out]=None # ambiguo: no usar duplicados distintos
            else:groups[p][out]=price
    result=[]
    for point,prices in groups.items():
        choices=("1","X","2") if market=="h2h" else (
            ("yes","no") if market=="btts" else ("over","under"))
        checked=_group(prices,choices)
        if checked:result.append((market,point,checked[0],checked[1],choices))
    return result


def get_api_football_odds(fixtures,now,env=None,fetcher=None,exclude_ids=None):
    now=_now(now);env=env or {};fetcher=fetcher or _http
    enabled=str(env.get("ENABLE_API_FOOTBALL_ODDS","")).lower() in ("1","true","yes")
    key=str(env.get("API_FOOTBALL_KEY","")).strip()
    status="DESACTIVADO" if not enabled else "SIN_CLAVE" if not key else "CONSULTANDO"
    audit={"proveedor":API_NAME,"estado":status,"consultas":0,"errores":0,
           "partidos":0,"cuotas":0,"limite_gratuito":"100 peticiones por día; máximo acotado"}
    if not enabled or not key:return {"estado":status,"cuotas":[],"auditoria":audit}
    headers={"x-apisports-key":key}
    excluded=set(exclude_ids or [])
    max_events=_bounded(env.get("API_FOOTBALL_MAX_FIXTURES") or MAX_API_ODDS,MAX_API_ODDS,MAX_API_ODDS)
    # Una fecha de calendario por llamada, máximo 4 fechas dentro de 5 días.
    dates=sorted({ _dt(f["fecha_utc"]).date().isoformat()
                   for f in fixtures if f.get("fecha_utc") and _dt(f.get("fecha_utc"))
                   and now<_dt(f["fecha_utc"])<=now+timedelta(days=MAX_DAYS)
                   and f.get("id") not in excluded})[:4]
    candidates=[]
    for date in dates:
        try:
            res=fetcher(f"{API_URL}/fixtures?"+urlencode({"date":date}),headers)
            audit["consultas"]+=1
            if not isinstance(res,dict) or not isinstance(res.get("response"),list):
                raise ValueError("Fixture response not list")
            for item in res["response"]:
                if not isinstance(item,dict):continue
                f=item.get("fixture") or {}
                league=item.get("league") or {}
                teams=item.get("teams") or {}
                if not isinstance(f,dict) or not isinstance(league,dict):continue
                standard={"league":{"name":league.get("name")},"teams":teams,
                          "kickoff_utc":f.get("date"),"id":f.get("id")}
                match=_match(standard,fixtures,now)
                if match and match.get("id") not in excluded and f.get("id"):
                    if not any(c[0]["id"]==match["id"] for c in candidates):
                        candidates.append((match,f["id"],league.get("id")))
        except Exception:
            audit["errores"]+=1
    quotes=[]
    for match,api_id,league_id in candidates[:max_events]:
        try:
            response=fetcher(f"{API_URL}/odds?"+urlencode({"fixture":api_id,"page":1}),headers)
            audit["consultas"]+=1
            if not isinstance(response,dict) or not isinstance(response.get("response"),list):
                raise ValueError("Odds response not list")
            for block in response["response"]:
                if not isinstance(block,dict):continue
                block_fixture=block.get("fixture") or {}
                if str(block_fixture.get("id"))!=str(api_id):continue
                block_league=block.get("league") or {}
                if league_id and str(block_league.get("id"))!=str(league_id):continue
                stamp=_dt(block.get("update"))
                if stamp and (stamp>now+timedelta(minutes=5)
                              or now-stamp>timedelta(hours=24)):continue
                for bk in block.get("bookmakers") or []:
                    if not isinstance(bk,dict) or not bk.get("id"):continue
                    for bet in bk.get("bets") or []:
                        if not isinstance(bet,dict):continue
                        for market,point,prices,margin,choices in _api_values(bet):
                            for outcome in choices:
                                quotes.append(_emit(match,api_id,bk.get("name"),bk["id"],
                                    API_NAME,market,outcome,point,prices,margin,now,
                                    provider_timestamp=stamp,definition=(
                                        "Solo amarillas FT" if market=="yellow"
                                        else "Mercado FT de nombre explícito")))
        except Exception:
            audit["errores"]+=1
    audit["partidos"]=len(candidates[:max_events]);audit["cuotas"]=len(quotes)
    audit["estado"]="PARCIAL" if audit["errores"] else "CON_CUOTAS" if quotes else "SIN_COINCIDENCIAS"
    return {"estado":audit["estado"],"cuotas":quotes,"auditoria":audit}


def collect_free_odds(fixtures,now,env=None,five_fetcher=None,api_fetcher=None):
    env=env or {}
    primary=get_five_odds(fixtures,now,env=env,fetcher=five_fetcher)
    # El respaldo puede aportar mercados distintos, como amarillas explícitas,
    # aun cuando la fuente principal tenga córners del mismo partido.
    fallback=get_api_football_odds(fixtures,now,env=env,fetcher=api_fetcher)
    quotes=[*primary["cuotas"],*fallback["cuotas"]]
    statuses=(primary["estado"],fallback["estado"])
    if any(x=="PARCIAL" for x in statuses):
        status="PARCIAL"
    elif quotes:status="CON_CUOTAS"
    elif all(x=="DESACTIVADO" for x in statuses):status="DESACTIVADO"
    elif all(x in ("DESACTIVADO","SIN_CLAVE") for x in statuses):status="SIN_CLAVE"
    else:status="SIN_COINCIDENCIAS"
    return {
        "estado":status,"cuotas":quotes,
        "auditoria":{"fuentes_gratuitas":[primary["auditoria"],fallback["auditoria"]],
                    "creditos_mensuales":0,
                    "nota":"Sin scraping; Free 5Dollar y API-Football opt-in. "
                           "Solo mercados semánticamente equiparables."}
    }
