"""Datos complementarios mediante Machina Sports (sports-skills), acceso gratuito.

Se presentan como contexto de investigación. No modifican las probabilidades.
"""
from __future__ import annotations
from datetime import datetime,timezone
import logging
import os

LOG=logging.getLogger(__name__)
COMPETITIONS={"E0":"premier-league","SP1":"la-liga","D1":"bundesliga",
              "I1":"serie-a","F1":"ligue-1"}

def _payload(result):
    if not isinstance(result,dict) or not result.get("status"):
        return None
    return result.get("data") if isinstance(result.get("data"),dict) else None

def summarize_standings(result):
    p=_payload(result)
    if p is None:return []
    out=[]
    for division in p.get("standings",[]):
        if not isinstance(division,dict):continue
        for entry in division.get("entries",[]):
            if not isinstance(entry,dict):continue
            team=entry.get("team") or {}
            if not isinstance(team,dict):continue
            name=team.get("name")
            if not name:continue
            out.append({"nombre":name,"posicion":entry.get("position"),
                        "puntos":entry.get("points"),"jugados":entry.get("played")})
    return sorted(out,key=lambda x:x["posicion"] if isinstance(x["posicion"],int) else 999)[:10]

def summarize_missing(result):
    p=_payload(result)
    if p is None:return []
    out=[]
    for record in p.get("teams",[]):
        if not isinstance(record,dict):continue
        team=record.get("team") or {}
        if not isinstance(team,dict):team={}
        players=record.get("players") or []
        categories={}
        for person in players:
            if not isinstance(person,dict):continue
            status=str(person.get("status") or person.get("availability") or "sin_clasificar").lower()
            categories[status]=categories.get(status,0)+1
        if players:
            out.append({"equipo":team.get("name","sin nombre"),"bajas_reportadas":len(players),
                        "estados":categories})
    return out

def collect(now:datetime|None=None,football=None)->dict:
    now=now or datetime.now(timezone.utc)
    result={"timestamp_utc":now.isoformat(),"fuente":"sports-skills / Machina Sports",
            "estado":"DESACTIVADO","clasificaciones":{},"bajas_premier":[],"errores":[],
            "advertencia":"No se usan automáticamente para modificar probabilidades."}
    if os.getenv("ENABLE_MACHINA")!="1" and football is None:
        return result
    try:
        if football is None:
            from sports_skills import football as football
    except (ImportError,Exception) as exc:
        result["estado"]="NO_DISPONIBLE"
        result["errores"].append("Dependencia sports-skills no disponible: "+type(exc).__name__)
        return result
    successful=0
    for code,comp in COMPETITIONS.items():
        try:
            season=_payload(football.get_current_season(competition_id=comp))
            season_id=(season or {}).get("season",{}).get("id")
            if not season_id:
                result["errores"].append(comp+": temporada no resuelta")
                continue
            standings=summarize_standings(football.get_season_standings(season_id=str(season_id)))
            if not standings:
                result["errores"].append(comp+": sin clasificación verificable")
                continue
            result["clasificaciones"][code]={"temporada":season_id,"top10":standings}
            successful+=1
            if code=="E0":
                try:
                    result["bajas_premier"]=summarize_missing(football.get_missing_players(season_id=str(season_id)))
                except Exception as exc:
                    result["errores"].append("Bajas Premier: "+type(exc).__name__)
        except Exception as exc:
            result["errores"].append(comp+": "+type(exc).__name__)
    result["estado"]="PARCIAL" if successful else "SIN_DATOS"
    return result
