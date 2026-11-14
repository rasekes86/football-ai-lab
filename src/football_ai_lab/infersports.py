"""Puente read-only a la skill oficial InferSports, sin clave de API.

NO interpreta los precios fair de InferSports como cuotas ofrecidas.
Sólo compara probabilidades, sujeto a frescura, cobertura y límites.
"""
from __future__ import annotations
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import subprocess
from .core import normalize_team

LOG=logging.getLogger(__name__)
SCRIPT=Path(__file__).resolve().parents[2] / ".agents" / "skills" / "infersports" / "scripts" / "fair.sh"

def parse_fair(data: dict, p: dict, now: datetime) -> dict | None:
    if data.get("status")!="ok" or data.get("stale"):
        return None
    match=data.get("match") or {}
    if normalize_team(match.get("home_team",""))!=normalize_team(p["local"]):
        return None
    if normalize_team(match.get("away_team",""))!=normalize_team(p["visitante"]):
        return None
    comp=data.get("comparison") or {}
    if comp.get("market_type")!="1x2" or comp.get("stale"):
        return None
    stamp=comp.get("as_of") or data.get("as_of")
    if not stamp:return None
    try:
        at=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        age=(now-at).total_seconds()
        if age < -300 or age > 24*3600:
            return None
    except (TypeError,ValueError):
        return None
    fair=comp.get("fair_odds") or {}
    try:
        vals=[1.0/float(fair[k]) for k in ("home","draw","away")]
    except (ValueError,TypeError,KeyError,ZeroDivisionError):
        return None
    total=sum(vals)
    if not 0.97<=total<=1.03:
        LOG.info("InferSports descartado: fair probabilities suman %.3f",total)
        return None
    vals=[v/total for v in vals]
    return {"fair":vals,"source":"InferSports","book":str(comp.get("fair_from","")),
            "timestamp":at.isoformat()}

def get_infer_fair(predictions: list[dict], now: datetime) -> dict[str,dict]:
    if os.getenv("ENABLE_INFERSPORTS")!="1":
        return {}
    if not SCRIPT.is_file():
        LOG.warning("Skill InferSports no disponible en %s",SCRIPT)
        return {}
    candidates=[]
    for p in predictions:
        try: kickoff=datetime.fromisoformat(p["fecha_utc"])
        except (ValueError,KeyError): continue
        # Limitar consumo de la capa gratuita: como máximo tres partidos por día.
        if now < kickoff <= now.replace(tzinfo=kickoff.tzinfo) + __import__("datetime").timedelta(days=7):
            candidates.append((kickoff,p))
    candidates.sort(key=lambda x:x[0])
    out={}
    for _,p in candidates[:3]:
        args=["bash",str(SCRIPT),f'{p["local"]} vs {p["visitante"]}',
              "--market","1x2","--date",p["fecha_utc"][:10],"--detailed"]
        try:
            proc=subprocess.run(args,capture_output=True,text=True,timeout=22,check=False,
                                env=dict(os.environ))
            if proc.returncode!=0:
                LOG.warning("InferSports fallo: %s",proc.stderr[:140])
                continue
            fair=parse_fair(json.loads(proc.stdout),p,now)
            if fair:out[p["id"]]=fair
        except (subprocess.TimeoutExpired, json.JSONDecodeError,OSError) as exc:
            LOG.warning("InferSports no disponible: %s",type(exc).__name__)
    return out

def merge_infer_prices(market_rows: list[dict], source: dict[str,dict],
                       predictions: list[dict]) -> list[dict]:
    mapping={p["id"]:p for p in predictions}
    for row in market_rows:
        if row.get("estado")=="COMPARACIÓN_SIN_VALIDAR":continue
        fair=source.get(row["id"])
        if not fair:continue
        p=mapping[row["id"]]
        row.update({"estado":"REFERENCIA_INFERSPORTS_SIN_VALIDAR",
                    "proveedor":"InferSports (keyless)",
                    "casa":fair["book"],"fecha_cuota_utc":fair["timestamp"],
                    "aviso":"Fair odds = referencia teórica sin margen; NO son cuotas ofrecidas ni una apuesta recomendada."})
        for label,pred_key,fval in zip(("local","empate","visitante"),
                                      ("prob_local","prob_empate","prob_visitante"),fair["fair"]):
            row["prob_mercado_"+label]=f"{fval:.5f}"
            row["diferencia_"+label+"_pp"]=f"{100*(float(p[pred_key])-fval):+.2f}"
    return market_rows
