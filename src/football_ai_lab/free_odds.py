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
MAX_API_ODDS=6  # 4 fechas + 6 odds: máximo 10 consultas/minuto en plan Free
MAX_DAYS=5
MAX_DIFF=timedelta(hours=2)
MAX_FIVE_FIXTURE_CALLS=13  # max 10 day pages + catalog + 2 league fallbacks
FIVE_MAJOR_CODES=("SP1","E0","D1","I1","F1")
LEAGUE_LABEL={code:name for name,code in FIVE_CODES.items()}

# Only explicit verified-equivalent club spellings. Never fuzzy-match or
# reduce a B-team to its senior club. Core model IDs are left untouched.
PROVIDER_TEAM_ALIASES={
    "bayern munich":"bayern","bayern munchen":"bayern",
    "fc bayern munchen":"bayern","bayern munchen fc":"bayern",
    "fc cologne":"cologne","1 fc koln":"cologne","fc koln":"cologne",
    "1 fc cologne":"cologne","koln":"cologne",
    "borussia monchengladbach":"monchengladbach",
    "borussia m gladbach":"monchengladbach",
    "borussia gladbach":"monchengladbach",
    "borussia dortmund":"dortmund","bvb dortmund":"dortmund",
    "eintracht frankfurt":"frankfurt",
    "tsg hoffenheim":"hoffenheim","1899 hoffenheim":"hoffenheim",
    "rb leipzig":"leipzig","rasenballsport leipzig":"leipzig",
    "bayer leverkusen":"leverkusen","bayer 04 leverkusen":"leverkusen",
    "fc augsburg":"augsburg","sc freiburg":"freiburg",
    "sv werder bremen":"werder bremen","werder bremen":"werder bremen",
    "vfb stuttgart":"stuttgart","1 fsv mainz 05":"mainz",
    "fsv mainz":"mainz","schalke 04":"schalke",
    "fc schalke 04":"schalke","hsv hamburg":"hamburg",
    "hull city afc":"hull","coventry city fc":"coventry",
}
PROVIDER_LEAGUE_ALIASES={
    "english premier league":"E0","england premier league":"E0",
    "england premier league 2026 2027":"E0",
    "german bundesliga":"D1","germany bundesliga":"D1",
    "bundesliga 1":"D1","bundesliga 1 germany":"D1",
    "spanish la liga":"SP1","spain primera division":"SP1",
    "spain segunda":"SP2","spain segunda division":"SP2","spanish segunda division":"SP2",
    "segunda division spain":"SP2","la liga 2":"SP2",
    "italian serie a":"I1","italy serie a":"I1",
    "french ligue 1":"F1","france ligue 1":"F1"
}


def _team_key(name):
    key=normalize_team(name)
    return PROVIDER_TEAM_ALIASES.get(key,key)


def _same_team(a,b):
    return bool(_team_key(a) and _team_key(a)==_team_key(b))


def _fixture_league_counts(fixtures,now):
    counts={code:0 for code in FIVE_CODES.values()}
    for row in fixtures:
        code=FIVE_CODES.get(row.get("liga"))
        kick=_dt(row.get("fecha_utc"))
        if code and kick and now<kick<=now+timedelta(days=MAX_DAYS):
            counts[code]+=1
    return counts


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
    if clean in PROVIDER_LEAGUE_ALIASES:
        return PROVIDER_LEAGUE_ALIASES[clean]
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
        and _same_team(row.get("local"),home)
        and _same_team(row.get("visitante"),away)
        and not _same_team(home,away)
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
    """Small, bounded free-tier discovery; only verified identical fixtures get prices.

    1. Date-window fixture pages (up to two pages per day).
    2. If EPL/Bundesliga missing, lookup league ids and request their fixtures.
    3. Optional Segunda discovery, only when Community Access was authorized.
    4. Round-robin odds budget: <=14 fixture odds requests, never speculative prices.
    """
    now=_now(now);env=env or {};fetcher=fetcher or _http
    enabled=str(env.get("ENABLE_FREE_ODDS","")).lower() in ("1","true","yes")
    key=str(env.get("FIVEDOLLAR_API_KEY","")).strip()
    community=str(env.get("ENABLE_FIVE_SEGUNDA","")).lower() in ("1","true","yes")
    status="DESACTIVADO" if not enabled else "SIN_CLAVE" if not key else "CONSULTANDO"
    audit={"proveedor":FIVE_NAME,"estado":status,"consultas":0,"partidos":0,
           "eventos_emparejados":0,"errores":0,"cuotas":0,
           "no_equivalente":["Tarjetas genéricas ≠ amarillas verificadas"],
           "limite_gratuito":"60 solicitudes/hora en plan Free; no se garantiza la cobertura",
           "maximo_consultas_por_ejecucion":MAX_FIVE_FIXTURE_CALLS+MAX_FIVE_ODDS,
           "community_segunda_activada":community,
           "limite_partidos_con_cuota":MAX_FIVE_ODDS}
    if not enabled or not key:return {"estado":status,"cuotas":[],"auditoria":audit}

    limit=_bounded(env.get("FREE_ODDS_MAX_FIXTURES") or MAX_FIVE_ODDS,
                   MAX_FIVE_ODDS,MAX_FIVE_ODDS)
    headers={"Authorization":f"Bearer {key}"}
    selected=[f for f in fixtures if _dt(f.get("fecha_utc"))
              and now<_dt(f["fecha_utc"])<=now+timedelta(days=MAX_DAYS)]
    days=sorted({_dt(f["fecha_utc"]).date() for f in selected})
    audit["dias_consultados"]=[d.isoformat() for d in days]

    # All diagnostic fields contain only league-level counts, never raw match
    # identity or private headers. Duplicate page rows are not counted twice.
    candidates={}
    ambiguous=set()
    provider_rows=defaultdict(int)
    unmatched_rows=defaultdict(int)
    mismatch_reasons=defaultdict(lambda:defaultdict(int))
    unknown_leagues=0
    seen_provider_ids=set()
    request_budget=MAX_FIVE_FIXTURE_CALLS
    request_errors=defaultdict(int)
    catalog_codes=set()
    targeted_codes=[]

    def call(url):
        nonlocal request_budget
        if request_budget<=0:
            raise RuntimeError("BUDGET_EXHAUSTED")
        request_budget-=1
        audit["consultas"]+=1
        return fetcher(url,headers)

    def register(event):
        nonlocal unknown_leagues
        if not isinstance(event,dict) or not event.get("id"):return
        eid=str(event["id"])
        if eid in seen_provider_ids:return
        seen_provider_ids.add(eid)
        rawleague=event.get("league") or {}
        code=_league_code(rawleague.get("name","") if isinstance(rawleague,dict) else "")
        if code is None:
            unknown_leagues+=1
            return
        provider_rows[code]+=1
        match=_match(event,selected,now)
        if match is None:
            unmatched_rows[code]+=1
            kick=_dt(event.get("kickoff_utc") or event.get("date"))
            teams=event.get("teams") or {}
            if not isinstance(teams,dict):teams={}
            home=(teams.get("home") or {}).get("name") or ""
            away=(teams.get("away") or {}).get("name") or ""
            same_clock=[row for row in selected
                        if FIVE_CODES.get(row.get("liga"))==code and kick
                        and abs(_dt(row["fecha_utc"])-kick)<=MAX_DIFF]
            if any(_same_team(row.get("local"),away) and
                   _same_team(row.get("visitante"),home) for row in same_clock):
                mismatch_reasons[code]["orden_local_visitante"]+=1
            elif same_clock:
                mismatch_reasons[code]["equipos"]+=1
            else:
                mismatch_reasons[code]["horario_o_calendario"]+=1
            return
        ident=match["id"]
        if ident in candidates and str(candidates[ident][1]["id"])!=eid:
            ambiguous.add(ident)
        else:
            candidates.setdefault(ident,(match,event))

    # Documented pagination: limit date windows to 24h and <=2 pages.
    # Free does not permit include=odds in fixture lists.
    for day in days:
        begin=datetime.combine(day,datetime.min.time(),tzinfo=timezone.utc)
        for page in (1,2):
            params=urlencode({
                "start_time":int(begin.timestamp()),
                "end_time":int((begin+timedelta(days=1)).timestamp()),
                "status":"scheduled","per_page":100,"page":page,
            })
            try:
                obj=call(f"{FIVE_URL}/fixtures?{params}")
                if not isinstance(obj,dict) or obj.get("success") not in (1,True):
                    raise ValueError("Respuesta de calendario inválida")
                rows=obj.get("data") or []
                if not isinstance(rows,list):raise ValueError("Calendario no es lista")
                for event in rows:register(event)
                paging=obj.get("pagination") or {}
                # Never guess another page without explicit pagination metadata.
                if not isinstance(paging,dict) or paging.get("has_more") is not True:
                    break
            except Exception:
                audit["errores"]+=1
                request_errors["calendario"]+=1
                break

    for ident in ambiguous:candidates.pop(ident,None)
    current_codes={FIVE_CODES[match["liga"]] for match,_ in candidates.values()}
    expected=_fixture_league_counts(selected,now)
    needed=[code for code in ("E0","D1") if expected[code]>0 and code not in current_codes]
    if community and expected["SP2"]>0 and "SP2" not in current_codes:
        needed.append("SP2")

    if needed and request_budget:
        # Do not hardcode temporary or retired provider league ids.
        # Ask the provider for its current league catalogue; on merged ids
        # its published documentation explains the 301 canonical-id handling.
        lookup=defaultdict(set)
        searches=["popular=1&per_page=100"]
        if "SP2" in needed:searches.append("country=ES&per_page=100")
        for query in searches:
            try:
                obj=call(f"{FIVE_URL}/leagues?{query}")
                if not isinstance(obj,dict) or obj.get("success") not in (1,True):
                    raise ValueError("Catálogo de ligas inválido")
                for entry in obj.get("data") or []:
                    if not isinstance(entry,dict) or not entry.get("id"):continue
                    code=_league_code(entry.get("name",""))
                    if code:
                        catalog_codes.add(code)
                        lookup[code].add(str(entry["id"]))
            except Exception:
                audit["errores"]+=1
                request_errors["catalogo"]+=1

        begin=now
        until=now+timedelta(days=MAX_DAYS)
        for code in needed:
            if not request_budget:break
            ids=lookup.get(code,set())
            if len(ids)!=1:
                # Two different provider league ids are ambiguous: never pick one.
                request_errors["id_liga_ausente_o_ambiguo"]+=1
                continue
            league_id=next(iter(ids))
            params=urlencode({
                "start_time":int(begin.timestamp()),
                "end_time":int(until.timestamp()),
                "status":"scheduled","order":"asc","page":1,"per_page":100,
            })
            targeted_codes.append(code)
            try:
                obj=call(f"{FIVE_URL}/leagues/{league_id}/fixtures?{params}")
                if not isinstance(obj,dict) or obj.get("success") not in (1,True):
                    raise ValueError("Respuesta de liga inválida")
                rows=obj.get("data") or []
                if not isinstance(rows,list):raise ValueError("Liga no es lista")
                for event in rows:register(event)
            except Exception:
                audit["errores"]+=1
                request_errors["liga_especifica"]+=1

    for ident in ambiguous:candidates.pop(ident,None)
    by_league=defaultdict(list)
    for match,event in candidates.values():
        by_league[match["liga"]].append((match,event))
    for games in by_league.values():
        games.sort(key=lambda item:(_dt(item[0]["fecha_utc"]),str(item[0]["id"])))
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

    quotes=[]
    no_price=0
    for match,event in balanced:
        # At most 14 bookmaker-odds requests, independent of list pagination.
        audit["consultas"]+=1
        try:
            obj=fetcher(f"{FIVE_URL}/fixtures/{event['id']}/odds",headers)
            if not isinstance(obj,dict) or obj.get("success") not in (1,True):
                raise ValueError("Respuesta de cuotas inválida")
            payload=obj.get("data") or {}
            if str(payload.get("fixture_id"))!=str(event["id"]):
                no_price+=1
                continue
            rows=_five_fixture_rows(match,event["id"],payload,now)
            if not rows:no_price+=1
            quotes.extend(rows)
        except Exception:
            audit["errores"]+=1
            request_errors["cuotas"]+=1

    by_fixture=defaultdict(list)
    for q in quotes:by_fixture[q["fixture_id"]].append(q)
    match_counts=defaultdict(int)
    booked_counts=defaultdict(int)
    for match,_ in candidates.values():match_counts[match["liga"]]+=1
    for match,_ in balanced:booked_counts[match["liga"]]+=1

    coverage={}
    for name in league_order:
        code=FIVE_CODES[name]
        n_model=expected[code]
        n_api=provider_rows[code]
        n_match=match_counts[name]
        n_requested=booked_counts[name]
        n_priced=sum(bool(by_fixture.get(match["id"])) for match,_ in balanced
                     if match["liga"]==name)
        n_quotes=sum(len(by_fixture.get(match["id"],[])) for match,_ in balanced
                     if match["liga"]==name)
        if n_priced:
            state="CON_CUOTAS"
        elif not n_model:
            state="SIN_PARTIDOS_MODELO"
        elif name=="Segunda División" and not community and not n_api:
            state="NO_INCLUIDA_EN_FREE"
        elif not n_api:
            state="SIN_EVENTOS_PROVEEDOR"
        elif not n_match:
            state="SIN_COINCIDENCIA_VERIFICADA"
        elif not n_requested:
            state="FUERA_DEL_CUPO_DE_CONSULTAS"
        else:
            state="SIN_PRECIOS_VALIDOS"
        coverage[name]={
            "estado":state,"partidos_modelo":n_model,
            "eventos_proveedor":n_api,"partidos_emparejados":n_match,
            "partidos_consultados":n_requested,"partidos_con_cuotas":n_priced,
            "cuotas":n_quotes,
            "motivos_descartados":dict(sorted(mismatch_reasons[code].items())),
        }
    audit["cobertura_ligas"]=coverage
    audit["eventos_api_por_liga"]=dict(sorted(provider_rows.items()))
    audit["sin_emparejar_por_liga"]=dict(sorted(unmatched_rows.items()))
    audit["ligas_no_reconocidas_total"]=unknown_leagues
    audit["eventos_emparejados"]=len(candidates)
    audit["ligas_emparejadas"]=sorted({m["liga"] for m,_ in candidates.values()})
    audit["ligas_seleccionadas"]=sorted({m["liga"] for m,_ in balanced})
    audit["partidos_por_liga"]=dict(sorted(booked_counts.items()))
    audit["ligas_catalogo_detectadas"]=sorted(catalog_codes)
    audit["consultas_especificas_liga"]=sorted(targeted_codes)
    audit["errores_por_fase"]=dict(sorted(request_errors.items()))
    audit["respuestas_sin_cuotas"]=no_price
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


def get_api_football_odds(fixtures,now,env=None,fetcher=None,exclude_ids=None,prefer_ids=None):
    now=_now(now);env=env or {};fetcher=fetcher or _http
    enabled=str(env.get("ENABLE_API_FOOTBALL_ODDS","")).lower() in ("1","true","yes")
    key=str(env.get("API_FOOTBALL_KEY","")).strip()
    status="DESACTIVADO" if not enabled else "SIN_CLAVE" if not key else "CONSULTANDO"
    audit={"proveedor":API_NAME,"estado":status,"consultas":0,"errores":0,
           "partidos":0,"cuotas":0,"limite_gratuito":"100 peticiones por día, 10/minuto",
           "maximo_consultas_por_ejecucion":10}
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
    # Prioridad: ligas sin cobertura de 5Dollar, no consumir el plan Free
    # en cotejar otra vez partidos ya cubiertos mientras falten cuotas.
    preferred=set(prefer_ids or [])
    priority={"Segunda División":0,"Premier League":1,"Bundesliga":2,
              "LaLiga":3,"Serie A":4,"Ligue 1":5}
    candidates.sort(key=lambda x:(x[0]["id"] not in preferred,
               priority.get(x[0]["liga"],9),x[0]["fecha_utc"],x[0]["id"]))
    chosen=candidates[:max_events]
    audit["partidos_candidatos"]=len(candidates)
    audit["cobertura_ligas"]={
        name:{"candidatos":sum(c[0]["liga"]==name for c in candidates),
              "consultados":sum(c[0]["liga"]==name for c in chosen)}
        for name in FIVE_CODES if any(c[0]["liga"]==name for c in candidates)
    }
    quotes=[]
    for match,api_id,league_id in chosen:
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
    audit["partidos"]=len(chosen);audit["cuotas"]=len(quotes)
    audit["estado"]="PARCIAL" if audit["errores"] else "CON_CUOTAS" if quotes else "SIN_COINCIDENCIAS"
    return {"estado":audit["estado"],"cuotas":quotes,"auditoria":audit}


def collect_free_odds(fixtures,now,env=None,five_fetcher=None,api_fetcher=None):
    env=env or {}
    primary=get_five_odds(fixtures,now,env=env,fetcher=five_fetcher)
    # El respaldo puede aportar mercados distintos, como amarillas explícitas,
    # aun cuando la fuente principal tenga córners del mismo partido.
    # API-Football is secondary: prefer fixtures with no observed 5Dollar
    # odds, especially Segunda, then complement other markets if budget remains.
    priced={q["fixture_id"] for q in primary["cuotas"]}
    preferred={m.get("id") for m in fixtures if m.get("id") and
               (m["id"] not in priced or m.get("liga")=="Segunda División")}
    fallback=get_api_football_odds(fixtures,now,env=env,fetcher=api_fetcher,
                                   prefer_ids=preferred)
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
