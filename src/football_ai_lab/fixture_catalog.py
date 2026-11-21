"""Archive the full public fixture calendar separately from model eligibility.

A newly promoted team may lack enough Bundesliga home/away matches for a
forecast. The fixture must remain visible, and no retrospective pick is made.
"""
from __future__ import annotations
from datetime import datetime
from .core import normalize_team
from .sources import LEAGUES

FIELDS=["id","fecha_utc","liga","local","visitante","origen_calendario",
        "primera_captura_utc","pronostico_disponible_al_registrar"]

def fixture_id(event:dict)->str:
    return "|".join([
        event["league"],event["kickoff"].strftime("%Y%m%d%H%M"),
        normalize_team(event["home"]),normalize_team(event["away"])
    ])

def archive(previous:list[dict],fixtures:list[dict],now:datetime,
            forecast_ids:set[str]|None=None)->list[dict]:
    rows={r["id"]:dict(r) for r in previous if r.get("id")}
    known=forecast_ids or set()
    for f in fixtures:
        if f.get("league") not in LEAGUES or not isinstance(f.get("kickoff"),datetime):
            continue
        kick=f["kickoff"]
        if kick.tzinfo is None:continue
        key=fixture_id(f)
        if key in rows:continue  # first record immutable
        rows[key]={
            "id":key,"fecha_utc":kick.isoformat(),
            "liga":LEAGUES[f["league"]][0],
            "local":f["home"],"visitante":f["away"],
            "origen_calendario":"ESPN (no oficial)",
            "primera_captura_utc":now.isoformat(),
            "pronostico_disponible_al_registrar":"SI" if key in known else "NO"
        }
    return sorted(rows.values(),key=lambda x:(x["fecha_utc"],x["id"]))
