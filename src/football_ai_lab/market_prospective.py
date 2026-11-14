"""Seguimiento prospectivo por selección de mercado, sin apuesta económica.

Los tres primeros mercados seleccionados por encuentro se congelan antes del
inicio. Nada posterior puede reescribir esa selección. Los resultados sólo se
puntúan contra marcadores finales del histórico y estadísticas realmente
proporcionadas por el CSV; las ausencias nunca cuentan como pérdidas.
"""
from __future__ import annotations
import json
import re
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from math import log
from zoneinfo import ZoneInfo
from .sources import LEAGUES
from .core import normalize_team

VERSION="market-prospective-0.8"
MADRID=ZoneInfo("Europe/Madrid")
FIELDS=["clave","id","liga","local","visitante","fecha_utc","archivado_utc",
        "mercado","seleccion","familia","origen","nivel","probabilidad",
        "cuota_justa","contrato","estado","resultado","valor_real",
        "brier","logloss","partidos_fuente"]

def utc(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("Falta zona horaria")
    return d.astimezone(timezone.utc)

def contract(p:dict,c:dict)->dict|None:
    """Contrato verificable, basado en etiquetas construidas por nuestro motor."""
    market=c.get("mercado","")
    label=c.get("seleccion","")
    home,away=p["local"],p["visitante"]
    if market=="1X2":
        winner=("H" if label==home+" gana" else
                "A" if label==away+" gana" else
                "D" if label=="Empate" else None)
        return {"tipo":"resultado","pick":winner} if winner else None
    if market=="Doble oportunidad":
        pick=label.split(":")[0].strip()
        return {"tipo":"doble","pick":pick} if pick in {"1X","X2","12"} else None
    if market=="Ambos marcan":
        return {"tipo":"ambos","pick":label} if label in {"Sí","No"} else None
    if market=="Total goles":
        m=re.fullmatch(r"(Más|Menos) de (\d+,\d+) goles",label)
        if m:
            return {"tipo":"total","direccion":m[1],"linea":float(m[2].replace(",","."))}
    if market=="Goles equipo":
        for side,team in (("H",home),("A",away)):
            m=re.fullmatch(re.escape(team)+r": (más|menos) de (\d+,\d+) goles",label)
            if m:
                return {"tipo":"goles_equipo","lado":side,
                        "direccion":m[1],"linea":float(m[2].replace(",","."))}
    if market=="Hándicap 2 vías (medio gol)":
        for side,team in (("H",home),("A",away)):
            m=re.fullmatch(re.escape(team)+r" ([+-]?\d+,\d+)",label)
            if m:
                return {"tipo":"handicap","lado":side,"linea":float(m[1].replace(",","."))}
    mapping={"Córners totales":"corners","Tiros totales":"shots",
             "Tiros a puerta totales":"on_target","Tarjetas amarillas totales":"yellow"}
    if market in mapping and c.get("metrica")==mapping[market]:
        try:
            line=float(c["linea"])
            if line<=0 or abs(line*2-round(line*2))>1e-8 or int(line*2)%2!=1:return None
            direction=c["direccion"]
        except (ValueError,TypeError,KeyError):
            return None
        if direction not in ("menos","mas"):return None
        return {"tipo":"conteo","metrica":mapping[market],"linea":line,
                "direccion":direction}
    return None

def archive(rows:list[dict],matches:list[dict],now:datetime)->list[dict]:
    """Primer Top 3 por encuentro antes del comienzo; no se amplía después."""
    old=list(rows)
    covered={r["id"] for r in old}
    for m in matches:
        if m.get("id") in covered:continue
        try:
            start=utc(m["fecha_utc"])
            saved=utc(m["calculado_utc"])
            if start<=now or saved>=start or saved>now+timedelta(minutes=1):continue
        except (KeyError,TypeError,ValueError):continue
        fresh=[]
        for c in m.get("top_probabilidad",[])[:3]:
            spec=contract(m,c)
            if spec is None:continue
            try:
                prob=float(c["probabilidad"])
                if not (0<prob<1):continue
            except (TypeError,KeyError,ValueError):continue
            sel=str(c.get("seleccion",""))
            fresh.append({"clave":m["id"]+"|"+c["mercado"]+"|"+sel,
                          "id":m["id"],"liga":m["liga"],"local":m["local"],
                          "visitante":m["visitante"],"fecha_utc":m["fecha_utc"],
                          "archivado_utc":saved.isoformat(),"mercado":c["mercado"],
                          "seleccion":sel,"familia":c["familia"],
                          "origen":c.get("origen",""),"nivel":c.get("nivel",""),
                          "probabilidad":f"{prob:.6f}",
                          "cuota_justa":str(c.get("cuota_justa","")),
                          "contrato":json.dumps(spec,ensure_ascii=False,sort_keys=True),
                          "estado":"PENDIENTE","resultado":"","valor_real":"",
                          "brier":"","logloss":"","partidos_fuente":""})
        if fresh:
            old.extend(fresh)
            covered.add(m["id"])
    return old

def _observed(spec:dict,game:dict)->tuple[bool|None,str]:
    hg,ag=game["home_goals"],game["away_goals"]
    typ=spec["tipo"]
    if typ=="resultado":
        actual="H" if hg>ag else "D" if hg==ag else "A"
        return actual==spec["pick"],actual
    if typ=="doble":
        actual="H" if hg>ag else "D" if hg==ag else "A"
        return actual in {"1X":"HD","X2":"DA","12":"HA"}[spec["pick"]],actual
    if typ=="ambos":
        actual=(hg>0 and ag>0)
        return actual==(spec["pick"]=="Sí"),str(actual)
    if typ=="total":
        total=hg+ag
        return (total>spec["linea"] if spec["direccion"]=="Más" else total<spec["linea"]),str(total)
    if typ=="goles_equipo":
        goals=hg if spec["lado"]=="H" else ag
        return (goals>spec["linea"] if spec["direccion"]=="más" else goals<spec["linea"]),str(goals)
    if typ=="handicap":
        diff=hg-ag if spec["lado"]=="H" else ag-hg
        return diff+spec["linea"]>0,str(diff)
    if typ=="conteo":
        met=spec["metrica"]
        home=game.get("home_"+met);away=game.get("away_"+met)
        if not isinstance(home,(int,float)) or not isinstance(away,(int,float)):
            return None,""
        value=home+away
        return (value<spec["linea"] if spec["direccion"]=="menos" else value>spec["linea"]),str(value)
    return None,""

def settle(rows:list[dict],histories:dict,now:datetime)->list[dict]:
    labels={v[0]:k for k,v in LEAGUES.items()}
    index={}
    for league,games in histories.items():
        for g in games:
            key=(league,g["date"],normalize_team(g["home"]),normalize_team(g["away"]))
            index[key]=g
    out=[]
    for source in rows:
        r=dict(source);r.update({"resultado":"","valor_real":"","brier":"","logloss":"",
                                 "partidos_fuente":""})
        try:
            start=utc(r["fecha_utc"])
            saved=utc(r["archivado_utc"])
            p=float(r["probabilidad"])
            if not 0<p<1 or saved>=start or saved>now:
                r["estado"]="EXCLUIDO_FECHA_O_PROBABILIDAD"
                out.append(r);continue
            league=labels[r["liga"]]
            spec=json.loads(r["contrato"])
            if not isinstance(spec,dict) or spec.get("tipo") not in (
                    "resultado","doble","ambos","total","goles_equipo","handicap","conteo"):
                raise ValueError("Contrato no reconocido")
        except (TypeError,KeyError,ValueError,AttributeError):
            r["estado"]="EXCLUIDO_DATOS_INVALIDOS"
            out.append(r);continue
        if now<start+timedelta(hours=2):
            r["estado"]="PENDIENTE";out.append(r);continue
        match=index.get((league,start.astimezone(MADRID).date(),
                         normalize_team(r["local"]),normalize_team(r["visitante"])))
        if not match:
            r["estado"]="RESULTADO_NO_DISPONIBLE";out.append(r);continue
        outcome,value=_observed(spec,match)
        if outcome is None:
            r["estado"]="ESTADISTICA_NO_DISPONIBLE";out.append(r);continue
        y=int(outcome)
        r.update({"estado":"FINALIZADO","resultado":str(y),"valor_real":value,
                  "brier":f"{(p-y)**2:.6f}",
                  "logloss":f"{-log(max(1e-9,p if y else 1-p)):.6f}",
                  "partidos_fuente":f'{match["home_goals"]}-{match["away_goals"]}'})
        out.append(r)
    return out

def _aggregate(rows:list[dict])->dict:
    if not rows:return {"muestra":0,"acierto_pct":None,"brier":None,
                         "logloss":None,"ece":None,"advertencia":"Muestra inexistente"}
    n=len(rows);hits=sum(int(r["resultado"]) for r in rows)
    brier=sum(float(r["brier"]) for r in rows)/n
    loss=sum(float(r["logloss"]) for r in rows)/n
    buckets=[[] for _ in range(5)]
    for r in rows:
        p=float(r["probabilidad"])
        buckets[min(4,int(p*5))].append((p,int(r["resultado"])))
    ece=sum(len(b)/n*abs(sum(p for p,_ in b)/len(b)-sum(y for _,y in b)/len(b))
            for b in buckets if b)
    return {"muestra":n,"acierto_pct":round(100*hits/n,2),
            "brier":round(brier,6),"logloss":round(loss,6),
            "ece":round(ece,6),
            "advertencia":"Muestra pequeña: no permite inferir ventaja rentable" if n<100
                           else "Resultados prospectivos descriptivos, no ganancia económica"}

def summary(rows:list[dict],now:datetime)->dict:
    good=[x for x in rows if x.get("estado")=="FINALIZADO"]
    by_market=defaultdict(list);by_league=defaultdict(list);by_origin=defaultdict(list)
    for r in good:
        by_market[r["mercado"]].append(r)
        by_league[r["liga"]].append(r)
        by_origin[r["origen"]].append(r)
    return {"version":VERSION,"calculado_utc":now.isoformat(),"registradas":len(rows),
            "finalizadas":len(good),
            "pendientes":sum(x["estado"]=="PENDIENTE" for x in rows),
            "sin_resultado":sum(x["estado"]=="RESULTADO_NO_DISPONIBLE" for x in rows),
            "sin_estadistica":sum(x["estado"]=="ESTADISTICA_NO_DISPONIBLE" for x in rows),
            "excluidas":sum(x["estado"].startswith("EXCLUIDO") for x in rows),
            "global":_aggregate(good),
            "por_mercado":{k:_aggregate(v) for k,v in by_market.items()},
            "por_liga":{k:_aggregate(v) for k,v in by_league.items()},
            "por_origen":{k:_aggregate(v) for k,v in by_origin.items()},
            "advertencia":"Solo las primeras selecciones guardadas ANTES del partido. "
                         "Sin usar resultados retrospectivos como pronósticos reales."}
