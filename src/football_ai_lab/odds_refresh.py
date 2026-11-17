"""Refresco de cuotas independiente del análisis diario y del Top 3."""
import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from .pipeline import read_csv, write_csv
from .real_odds import build_real_odds
from .value_watchlist import FIELDS, freeze, summary, selection_audit, markdown


def load(path,default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (ValueError,OSError):
        return default


def save(path,payload):
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")


def merge_followup(rows,archived):
    """No convertir un acierto/error ya verificado en pendiente."""
    merged={r["clave"]:dict(r) for r in rows if r.get("clave")}
    for r in archived:
        merged.setdefault(r.get("clave"),dict(r))
    return list(merged.values())


def run(target=Path("output"),now=None,env=None):
    now=now or datetime.now(timezone.utc)
    env=os.environ if env is None else env
    if str(env.get("ENABLE_FREE_ODDS","")).lower() not in ("true","1","yes") or not env.get("FIVEDOLLAR_API_KEY"):
        return {"estado":"DESACTIVADO","modificado":False}
    future=load(target/"pronosticos_mercados_futuros.json",{}).get("partidos") or []
    selections=load(target/"selecciones.json",{}).get("partidos") or []
    if not future or not selections:
        raise RuntimeError("Faltan datos de pronósticos: no se sobrescriben salidas")
    previous=load(target/"cuotas_reales_verificadas.json",{})
    state=load(target/"estado_consultas_cuotas.json",{})
    archive=load(target/"historico_cuotas_reales.json",{})
    previous_offers=read_csv(target/"historico_oportunidades_150.csv")
    excluded={r["id"] for r in previous_offers if r.get("id")}
    quotes,compared,historical=build_real_odds(
        future,now,existing=archive,env=env,state=state,prior_quotes=previous,
        excluded_ids=excluded)
    state=quotes.pop("estado_consultas",state)
    frozen_top=read_csv(target/"historico_selecciones.csv")
    frozen=freeze(previous_offers,{"selecciones":[]},selections,now,
                  comparisons=compared,top3=frozen_top)
    tracked=merge_followup(read_csv(target/"seguimiento_oportunidades_150.csv"),frozen)
    evaluated=summary(tracked,now)
    evaluated["seleccion_automatica"]=selection_audit(
        previous_offers,frozen,selections,compared,now,frozen_top)
    save(target/"cuotas_reales_verificadas.json",quotes)
    save(target/"comparacion_cuotas_reales.json",compared)
    save(target/"historico_cuotas_reales.json",historical)
    save(target/"estado_consultas_cuotas.json",state)
    write_csv(target/"historico_oportunidades_150.csv",FIELDS,frozen)
    write_csv(target/"seguimiento_oportunidades_150.csv",FIELDS,tracked)
    save(target/"evaluacion_oportunidades_150.json",evaluated)
    (target/"oportunidades_150.md").write_text(markdown(tracked,evaluated),encoding="utf-8")
    return {"estado":quotes["estado"],"modificado":True,
            "cuotas":len(quotes.get("cuotas",[])),"adicionales":len(frozen)}


if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    print(run())
