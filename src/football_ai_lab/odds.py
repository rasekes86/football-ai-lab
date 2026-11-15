"""Comparación exploratoria del mercado; la API opcional nunca realiza apuestas."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import logging
import os
from urllib.parse import urlencode
from .core import normalize_team
from .sources import http_read, LEAGUES

LOG = logging.getLogger(__name__)
ODDS_API={"SP1":"soccer_spain_la_liga","E0":"soccer_epl",
          "D1":"soccer_germany_bundesliga","I1":"soccer_italy_serie_a",
          "F1":"soccer_france_ligue_one"}
MARKET_FIELDS=["id","fecha_utc","liga","local","visitante","estado","proveedor","casa",
               "fecha_cuota_utc","cuota_local","cuota_empate","cuota_visitante",
               "prob_mercado_local","prob_mercado_empate","prob_mercado_visitante",
               "diferencia_local_pp","diferencia_empate_pp","diferencia_visitante_pp","aviso"]

def fair_from_decimals(odds: tuple[float,float,float]) -> tuple[list[float],float]:
    if len(odds)!=3 or any(x<=1.0 for x in odds):
        raise ValueError("Cuotas 1X2 decimales inválidas")
    implied=[1/x for x in odds]
    margin=sum(implied)-1.
    total=sum(implied)
    return [x/total for x in implied],margin

def get_optional_quotes(leagues: list[str]) -> dict:
    # Sin clave + habilitación explícita, cero consultas externas y cero créditos consumidos.
    api_key=os.environ.get("THE_ODDS_API_KEY","").strip()
    if not api_key or os.environ.get("ENABLE_ODDS")!="1":
        return {}
    result={}
    for code in leagues:
        if code not in ODDS_API: continue
        url="https://api.the-odds-api.com/v4/sports/"+ODDS_API[code]+"/odds/?"+urlencode(
            {"apiKey":api_key,"regions":"eu","markets":"h2h","oddsFormat":"decimal"})
        try:
            payload=json.loads(http_read(url))
            if not isinstance(payload,list): raise ValueError("API devuelve formato inesperado")
            result[code]=payload
            LOG.info("Cuotas: %s eventos recuperados para %s",len(payload),code)
        except Exception as e:
            LOG.warning("Cuotas no disponibles para %s: %s",code,type(e).__name__)
    return result

def find_quote(prediction: dict, events: list[dict], now: datetime) -> dict | None:
    for event in events:
        if normalize_team(event.get("home_team","")) != normalize_team(prediction["local"]):
            continue
        if normalize_team(event.get("away_team","")) != normalize_team(prediction["visitante"]):
            continue
        try:
            kickoff=datetime.fromisoformat(event["commence_time"].replace("Z","+00:00"))
            target=datetime.fromisoformat(prediction["fecha_utc"])
            if abs((kickoff-target).total_seconds())>5400: continue
        except (KeyError,ValueError): continue
        for book in event.get("bookmakers",[]):
            for market in book.get("markets",[]):
                if market.get("key")!="h2h": continue
                values={normalize_team(x["name"]):float(x["price"])
                        for x in market.get("outcomes",[]) if "name" in x and "price" in x}
                keys=[normalize_team(prediction["local"]),"draw",normalize_team(prediction["visitante"])]
                if any(x not in values for x in keys): continue
                when=market.get("last_update") or book.get("last_update")
                if not when: continue
                try: at=datetime.fromisoformat(when.replace("Z","+00:00"))
                except ValueError: continue
                if at>now or (now-at).total_seconds()>6*3600: continue
                odds=tuple(values[key] for key in keys)
                try:fair,margin=fair_from_decimals(odds)
                except ValueError:continue
                return {"odds":odds,"fair":fair,"margin":margin,"book":book.get("title",""),
                        "time":at.isoformat()}
    return None

def build_market_rows(predictions: list[dict], events_by_league: dict, now: datetime) -> list[dict]:
    codes={name:code for code,(name,_) in LEAGUES.items()}
    out=[]
    for p in predictions:
        code=codes.get(p["liga"],"")
        row={k:"" for k in MARKET_FIELDS}
        row.update({"id":p["id"],"fecha_utc":p["fecha_utc"],"liga":p["liga"],
                    "local":p["local"],"visitante":p["visitante"],
                    "estado":"SIN_CUOTAS" if code in events_by_league else "PROVEEDOR_DESACTIVADO",
                    "aviso":"Diferencia estadística: NO es una recomendación ni un rendimiento validado"})
        quote=find_quote(p,events_by_league.get(code,[]),now)
        if quote:
            row.update({"estado":"COMPARACIÓN_SIN_VALIDAR","proveedor":"The Odds API",
                        "casa":quote["book"],"fecha_cuota_utc":quote["time"]})
            for name,odd,fair,key in zip(("local","empate","visitante"),quote["odds"],
                                         quote["fair"],("prob_local","prob_empate","prob_visitante")):
                row["cuota_"+name]=f"{odd:.3f}"
                row["prob_mercado_"+name]=f"{fair:.5f}"
                row["diferencia_"+name+"_pp"]=f"{100*(float(p[key])-fair):+.2f}"
        out.append(row)
    return out
