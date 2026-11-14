"""Muestra de xG históricos reales (Understat vía Machina), con cobertura limitada.

Nunca inventa xG, nunca lo utiliza como feature para un encuentro futuro
sin validación retrospectiva de la disponibilidad por fecha.
"""
from __future__ import annotations
from datetime import datetime,date,timedelta,timezone
import json
import logging
import os
from urllib.parse import urlencode
from .core import normalize_team
from .sources import LEAGUES, ESPN_URL, http_read

LOG=logging.getLogger(__name__)

def completed_events(blob:bytes,league:str,now:datetime)->list[dict]:
    events=[]
    raw=json.loads(blob)
    for event in raw.get("events",[]):
        status=(event.get("status") or {}).get("type") or {}
        if status.get("name") not in ("STATUS_FINAL","STATUS_FULL_TIME") and not status.get("completed"):
            continue
        try:
            kickoff=datetime.fromisoformat(event["date"].replace("Z","+00:00"))
            if kickoff>=now:continue
            teams=event["competitions"][0]["competitors"]
            home=next(c for c in teams if c["homeAway"]=="home")["team"]["displayName"]
            away=next(c for c in teams if c["homeAway"]=="away")["team"]["displayName"]
            event_id=str(event["id"])
            if not event_id.isdecimal():continue
            events.append({"league":league,"event_id":event_id,"fecha_utc":kickoff.isoformat(),
                           "local":home,"visitante":away})
        except (KeyError,TypeError,ValueError,IndexError,StopIteration):
            continue
    return events

def extract_xg(envelope:dict,fixture:dict)->dict|None:
    if not isinstance(envelope,dict) or envelope.get("status") is not True:return None
    data=envelope.get("data")
    if not isinstance(data,dict) or data.get("source")!="understat":return None
    found={}
    for side in data.get("teams",[]):
        if not isinstance(side,dict):continue
        qualifier=side.get("qualifier")
        if qualifier not in ("home","away"):continue
        team=side.get("team") or {}
        expected=fixture["local"] if qualifier=="home" else fixture["visitante"]
        if normalize_team(team.get("name",""))!=normalize_team(expected):
            return None
        try:xg=float(side["xg"])
        except (TypeError,KeyError,ValueError):return None
        if not 0<=xg<=12:return None
        found[qualifier]=round(xg,3)
    if set(found)!={"home","away"}:return None
    return dict(fixture,xg_local=found["home"],xg_visitante=found["away"],
                fuente="Understat vía sports-skills",
                tipo="HISTORICO_FINALIZADO_NO_PRONOSTICO")

def _short_http(url:str)->bytes:
    # Bound public-provider latency so the daily workflow stays within quota.
    return http_read(url,timeout=8)

def collect(now:datetime,football=None,reader=_short_http)->dict:
    result={"calculado_utc":now.isoformat(),"estado":"DESACTIVADO","partidos":[],
            "consultas_xg":0,"errores":[],
            "nota":"Sólo una muestra de partidos finalizados por liga. No representa xG de todos los equipos."}
    if os.getenv("ENABLE_HISTORIC_XG")!="1" and football is None:
        return result
    if football is None:
        try:from sports_skills import football as football
        except ImportError:
            result["estado"]="DEPENDENCIA_NO_DISPONIBLE"
            return result
    # A deliberately small bounded set; high-traffic API calls remain capped.
    for lg,(title,code) in LEAGUES.items():
        chosen=None
        for days_ago in (2,5,8,12):
            d=(now-timedelta(days=days_ago)).date()
            url=ESPN_URL.format(code=code)+"?"+urlencode({"dates":d.strftime("%Y%m%d")})
            try:
                matches=completed_events(reader(url),lg,now)
                if matches:
                    chosen=sorted(matches,key=lambda x:x["fecha_utc"],reverse=True)[0]
                    break
            except Exception as exc:
                result["errores"].append(lg+": calendario "+type(exc).__name__)
        if chosen is None:
            continue
        result["consultas_xg"]+=1
        try:
            response=football.get_event_xg(event_id=chosen["event_id"])
            xg=extract_xg(response,chosen)
            if xg:
                result["partidos"].append(xg)
            else:
                d=response.get("data") if isinstance(response,dict) else {}
                d=d if isinstance(d,dict) else {}
                reason=(d.get("message") or response.get("message") or "Identidad/valores no verificables")
                result["errores"].append(lg+": "+str(reason)[:160])
                result.setdefault("diagnosticos",[]).append({
                    "liga":lg,"evento":chosen["event_id"],"local":chosen["local"],
                    "visitante":chosen["visitante"],"motivo":str(reason)[:160],
                    "fuente_declarada":d.get("source",""),
                    "n_equipos_xg":len(d.get("teams") or [])})
        except Exception as exc:
            result["errores"].append(lg+": xG "+type(exc).__name__)
    result["estado"]="CON_DATOS" if result["partidos"] else "SIN_XG_VERIFICADO"
    return result
