"""Snapshot de fútbol en directo: fuente InferSports, no modelo entrenado in-play."""
from __future__ import annotations
from datetime import datetime,timezone,date
import json
import logging
import os
from pathlib import Path
import re
import subprocess
from .core import normalize_team

LOG=logging.getLogger(__name__)
SCRIPT=Path(__file__).resolve().parents[2]/".agents"/"skills"/"infersports"/"scripts"/"match.sh"
PATTERN=re.compile(r"^\[DIRECTO\]\s*(.+?)\s+vs\.?\s+(.+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*$",re.I)

def parse_live_request(title:str):
    match=PATTERN.match(title.strip())
    if not match:return None
    h,a,d=match.groups()
    if not h or not a or len(h)>100 or len(a)>100:return None
    try:return h.strip(),a.strip(),date.fromisoformat(d)
    except ValueError:return None

def validate_snapshot(data:dict,home:str,away:str,day:date,now:datetime,max_age_seconds:int=300):
    if data.get("status")!="ok" or data.get("stale"):
        return None,"Proveedor sin datos válidos o referencia marcada como obsoleta"
    match=data.get("match") or {}
    source_home=match.get("home_team","")
    source_away=match.get("away_team","")
    if isinstance(source_home,dict):source_home=source_home.get("name","")
    if isinstance(source_away,dict):source_away=source_away.get("name","")
    if normalize_team(source_home)!=normalize_team(home) or normalize_team(source_away)!=normalize_team(away):
        return None,"No coinciden exactamente los equipos devueltos"
    scheduled=match.get("scheduled_at") or ""
    try:
        kickoff=datetime.fromisoformat(scheduled.replace("Z","+00:00"))
        if kickoff.date()!=day:return None,"Fecha del encuentro diferente"
        sampled=datetime.fromisoformat(str(data.get("as_of","")).replace("Z","+00:00"))
        age=(now-sampled).total_seconds()
    except (ValueError,TypeError):
        return None,"Faltan fechas verificables"
    if age < -300 or age > max_age_seconds:
        return None,"Instantánea demasiado antigua o futura para considerarla actual"
    if match.get("status")!="live":
        return {"status":match.get("status","unknown"),"as_of":sampled.isoformat(),
                "home":source_home,"away":source_away},None
    score=match.get("score") or {}
    if not isinstance(score.get("home"),(int,float)) or not isinstance(score.get("away"),(int,float)):
        return None,"Marcador incompleto"
    probability=data.get("implied_probabilities") or {}
    implied=None
    if all(isinstance(probability.get(k),(int,float)) for k in ("home","draw","away")):
        vals=[float(probability[k]) for k in ("home","draw","away")]
        if all(0<=v<=1 for v in vals) and 0.97<sum(vals)<1.03:
            implied=vals
    return {"status":"live","as_of":sampled.isoformat(),"home":source_home,"away":source_away,
            "score":score,"clock":match.get("clock"),"cards":match.get("red_cards"),
            "implied":implied},None

def live_reply(title:str,now:datetime|None=None,raw:dict|None=None)->str:
    now=now or datetime.now(timezone.utc)
    req=parse_live_request(title)
    if req is None:
        return "Formato inválido. Ejemplo: [DIRECTO] Manchester City vs Fulham | 2026-11-21"
    home,away,day=req
    if abs((now.date()-day).days)>1:
        return "Solo se consultan partidos del día indicado (máximo ±1 día UTC)."
    if raw is None:
        if not SCRIPT.is_file():
            return "El proveedor InferSports no está disponible en este entorno."
        command=["bash",str(SCRIPT),f"{home} vs {away}","--date",day.isoformat(),
                 "--sport","football","--detailed"]
        try:
            p=subprocess.run(command,capture_output=True,text=True,timeout=25,env=dict(os.environ))
            if p.returncode:
                return "El proveedor no devolvió información verificable: "+p.stderr[-300:]
            raw=json.loads(p.stdout)
        except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:
            return "Error de conexión/lectura de datos del proveedor: "+type(exc).__name__
    snap,err=validate_snapshot(raw,home,away,day,now)
    if err:return "Análisis de directo no disponible: "+err
    if snap["status"]!="live":
        return f'**{home} – {away}**: el proveedor indica **{snap["status"]}** a {snap["as_of"]}. No se calculan probabilidades de directo.'
    score=snap["score"]
    report=[f'### En directo: {snap["home"]} {score["home"]}–{score["away"]} {snap["away"]}',
            f'**Minuto:** {snap["clock"] or "desconocido"}',
            f'**Consulta UTC:** {snap["as_of"]}']
    if snap["implied"] is not None:
        x=snap["implied"]
        report.append(f'**Probabilidades implícitas del mercado (1X2):** {x[0]*100:.1f}% local, {x[1]*100:.1f}% empate, {x[2]*100:.1f}% visitante.')
    else:
        report.append("Sin probabilidades de mercado verificables.")
    report.append("Datos proporcionados por InferSports, no por un modelo propio in-play. "
                  "Instantánea puntual, no monitorización continua. Ninguna apuesta recomendada.")
    return "\n\n".join(report)+"\n"
