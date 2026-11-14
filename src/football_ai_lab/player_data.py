"""Muestreo verificable de datos individuales en partidos YA finalizados.

Fuente pública experimental ESPN summary; no predicciones individuales hasta
tener cobertura histórica, minutos, titularidad y validación temporal suficientes.
No supone licencia comercial ni disponibilidad garantizada de la API.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
import json
import os
from .core import normalize_team
from .sources import ESPN_URL,LEAGUES,http_read
from .context_xg import completed_events

VERSION="players-source-0.8"
STAT_NAMES={"shots","totalShots","shotsOnTarget","shotsOnGoal","goals",
            "assists","yellowCards","redCards","minutes","minutesPlayed",
            "totalPasses","keyPasses"}
def _number(value):
    try:
        if isinstance(value,bool) or value is None:return None
        v=float(value)
        if 0<=v<10000:return round(v,3)
    except (TypeError,ValueError):pass
    return None

def normalize_summary(payload:dict,match:dict)->list[dict]:
    header=payload.get("header") or {}
    comp=(header.get("competitions") or [{}])[0]
    competitors=comp.get("competitors") or []
    if not competitors:return []
    names=[normalize_team((c.get("team") or {}).get("displayName",""))
           for c in competitors]
    if {normalize_team(match["local"]),normalize_team(match["visitante"])}!=set(names):
        return []
    rows=[]
    for roster in payload.get("rosters") or []:
        team=(roster.get("team") or {}).get("displayName","")
        if normalize_team(team) not in names:continue
        for p in roster.get("roster") or []:
            athlete=p.get("athlete") or {}
            player_id=str(athlete.get("id","")).strip()
            player_name=str(athlete.get("displayName","")).strip()
            if not player_id or not player_name:continue
            stats={}
            for item in p.get("stats") or []:
                name=item.get("name","")
                if name in STAT_NAMES:
                    value=_number(item.get("value",item.get("displayValue")))
                    if value is not None:stats[name]=value
            rows.append({"event_id":match["event_id"],"liga":match["league"],
                         "fecha_utc":match["fecha_utc"],"local":match["local"],
                         "visitante":match["visitante"],"equipo":team,
                         "jugador_id":player_id,"jugador":player_name,
                         "titular":bool(p.get("starter")),
                         "entro_desde_banquillo":bool(p.get("subbedIn")),
                         "participacion_confirmada":bool(p.get("starter") or p.get("subbedIn")),
                         "estadisticas":stats,"fuente":"ESPN summary público no oficial"})
    return rows

def _fetch(url:str)->bytes:
    return http_read(url,timeout=8)

def collect(now:datetime,existing:dict|None=None,reader=_fetch)->dict:
    current=existing if isinstance(existing,dict) else {}
    known={(str(x.get("event_id")),str(x.get("jugador_id"))):x
           for x in current.get("registros",[])
           if x.get("event_id") and x.get("jugador_id")}
    result={"version":VERSION,"actualizado_utc":now.isoformat(),
            "estado":"DESACTIVADO","registros":list(known.values()),
            "eventos_consultados":0,"eventos_con_jugadores":0,"errores":[],
            "advertencia":"Datos individuales de encuentros ya finalizados; "
                          "no son pronósticos ni alineaciones confirmadas para partidos futuros."}
    if os.environ.get("ENABLE_PLAYER_SAMPLE")!="1":return result
    matches=[]
    for code in LEAGUES:
        for day_back in (2,5,8):
            day=(now-timedelta(days=day_back)).date()
            url=ESPN_URL.format(code=LEAGUES[code][1])+f'?dates={day:%Y%m%d}'
            try:
                found=completed_events(reader(url),code,now)
                matches.extend(found)
                if found:break
            except Exception as exc:
                result["errores"].append(code+" calendario "+type(exc).__name__)
    unique={m["event_id"]:m for m in matches}
    matchlist=sorted(unique.values(),key=lambda x:x["fecha_utc"],reverse=True)
    for m in matchlist:
        if result["eventos_consultados"]>=4:break
        if any(event_id==m["event_id"] and "participacion_confirmada" in p
               for (event_id,_),p in known.items()):continue
        url=ESPN_URL.format(code=LEAGUES[m["league"]][1]).replace("/scoreboard","/summary")+\
            "?event="+m["event_id"]
        result["eventos_consultados"]+=1
        try:
            rows=normalize_summary(json.loads(reader(url)),m)
            if rows:
                result["eventos_con_jugadores"]+=1
                for row in rows:
                    known[(row["event_id"],row["jugador_id"])]=row
            else:result["errores"].append(m["league"]+": sin plantillas identificadas")
        except Exception as exc:
            result["errores"].append(m["league"]+": summary "+type(exc).__name__)
    vals=sorted(known.values(),key=lambda x:(x["fecha_utc"],x["event_id"]),reverse=True)
    # Keep modest aggregate history; provider may return duplicate/upstream changes.
    result["registros"]=vals[:6000]
    matches=set(x["event_id"] for x in result["registros"])
    measured=sum(bool(x["estadisticas"]) for x in result["registros"])
    result["partidos_archivados"]=len(matches)
    result["jugadores_con_algun_dato"]=measured
    result["estado"]=("CON_HISTORICO_PARCIAL" if measured else
                       "SOLO_ALINEACIONES_HISTORICAS" if vals else "SIN_DATOS_VERIFICADOS")
    return result
