"""Seguimiento prospectivo y calibración de pronósticos archivados.

Sólo puntúa pronósticos REAL con timestamp anterior al inicio. Un backtest jamás
puede aparecer en esta evaluación, aunque el resultado final ya se conozca.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from math import log
from zoneinfo import ZoneInfo
from .core import normalize_team
from .sources import LEAGUES

MADRID=ZoneInfo("Europe/Madrid")
VERSION="prospectivo-0.5"
KEYS=("prob_local","prob_empate","prob_visitante")
CLASSES=("H","D","A")
TRACK_FIELDS=["id","fecha_utc","liga","local","visitante","prob_local","prob_empate","prob_visitante",
              "resultado_local","resultado_visitante","resultado_real","brier_1x2","estado",
              "fecha_pronostico_utc","modelo","logloss_1x2","acierto_favorito"]

def _utc(value:str)->datetime:
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("Timestamp sin zona horaria")
    return d.astimezone(timezone.utc)

def _history_lookup(histories:dict)->dict:
    lookup={}
    for code,rows in histories.items():
        for g in rows:
            # Historical data is dated in the provider's local league calendar.
            key=(code,g["date"],normalize_team(g["home"]),normalize_team(g["away"]))
            lookup[key]=g
    return lookup

def _valid_prob(p:dict)->list[float]:
    try:values=[float(p[k]) for k in KEYS]
    except (KeyError,TypeError,ValueError):raise ValueError("Probabilidades ausentes")
    if any(v<=0 or v>=1 for v in values) or abs(sum(values)-1)>0.001:
        raise ValueError("Probabilidades 1X2 inválidas")
    return values

def result_label(match:dict)->str:
    return "H" if match["home_goals"]>match["away_goals"] else "D" if match["home_goals"]==match["away_goals"] else "A"

def completed_score(prob:list[float],result:str)->tuple[float,float,int]:
    brier=sum((prob[i]-(1 if result==CLASSES[i] else 0))**2 for i in range(3))/3
    loss=-log(max(1e-9,prob[CLASSES.index(result)]))
    best=max(range(3),key=lambda i:prob[i])
    return brier,loss,int(CLASSES[best]==result)

def evaluate(predictions:list[dict],histories:dict,now:datetime)->list[dict]:
    lookup=_history_lookup(histories)
    rows=[]
    league_by_name={value[0]:key for key,value in LEAGUES.items()}
    for p in predictions:
        row={f:p.get(f,"") for f in TRACK_FIELDS}
        row.update({"fecha_pronostico_utc":p.get("fecha_analisis_utc",""),
                    "modelo":p.get("modelo",""),"logloss_1x2":"","acierto_favorito":"",
                    "resultado_local":"","resultado_visitante":"","resultado_real":"","brier_1x2":""})
        try:
            kickoff=_utc(p["fecha_utc"])
            created=_utc(p.get("fecha_analisis_utc",""))
            prob=_valid_prob(p)
            if p.get("tipo")!="REAL" or created>=kickoff:
                row["estado"]="EXCLUIDO_NO_PREPARTIDO"
                rows.append(row);continue
            if created>now+timedelta(minutes=1):
                row["estado"]="EXCLUIDO_FECHA_FUTURA"
                rows.append(row);continue
            code=league_by_name[p["liga"]]
        except (KeyError,ValueError,TypeError):
            row["estado"]="EXCLUIDO_DATOS_INVALIDOS"
            rows.append(row);continue
        if now<kickoff+timedelta(hours=2):
            row["estado"]="PENDIENTE"
            rows.append(row);continue
        match=lookup.get((code,kickoff.astimezone(MADRID).date(),
                          normalize_team(p["local"]),normalize_team(p["visitante"])))
        if match is None:
            row["estado"]="RESULTADO_NO_DISPONIBLE"
            rows.append(row);continue
        real=result_label(match)
        brier,loss,hit=completed_score(prob,real)
        row.update({"resultado_local":str(match["home_goals"]),
                    "resultado_visitante":str(match["away_goals"]),
                    "resultado_real":real,"brier_1x2":f"{brier:.6f}",
                    "logloss_1x2":f"{loss:.6f}",
                    "acierto_favorito":str(hit),"estado":"FINALIZADO"})
        rows.append(row)
    return rows

def _summarize(rows:list[dict])->dict:
    n=len(rows)
    if not n:return {"muestra":0,"brier_medio":None,"logloss_medio":None,"acierto_favorito_pct":None,
                    "ece":None,"calibracion":[]}
    bins=[{"suma":0.0,"aciertos":0,"n":0} for _ in range(5)]
    total_brier=total_loss=hits=0
    for r in rows:
        total_brier+=float(r["brier_1x2"])
        total_loss+=float(r["logloss_1x2"])
        hits+=int(r["acierto_favorito"])
        for i,key in enumerate(KEYS):
            p=float(r[key])
            cls=CLASSES[i]
            index=min(4,int(p*5))
            b=bins[index]
            b["suma"]+=p
            b["aciertos"]+=int(r["resultado_real"]==cls)
            b["n"]+=1
    calibration=[]
    ece=0.0
    for idx,b in enumerate(bins):
        if not b["n"]:continue
        prediction=b["suma"]/b["n"]
        observed=b["aciertos"]/b["n"]
        ece+=(b["n"]/(3*n))*abs(prediction-observed)
        calibration.append({"intervalo":f"{idx*20}-{(idx+1)*20}%",
                            "observaciones":b["n"],"probabilidad_media":round(prediction,4),
                            "frecuencia_observada":round(observed,4)})
    return {"muestra":n,"brier_medio":round(total_brier/n,5),
            "logloss_medio":round(total_loss/n,5),
            "acierto_favorito_pct":round(100*hits/n,1),
            "ece":round(ece,5),"calibracion":calibration}

def summarize(tracking:list[dict],now:datetime)->dict:
    good=[x for x in tracking if x["estado"]=="FINALIZADO"]
    by_league=defaultdict(list);by_model=defaultdict(list)
    for row in good:
        by_league[row["liga"]].append(row)
        by_model[row["modelo"]].append(row)
    return {"version":VERSION,"calculado_utc":now.isoformat(),
            "proporcion":"1X2 prepartido archivado; Brier dividido entre 3",
            "registrados":len(tracking),"finalizados_validos":len(good),
            "pendientes":sum(x["estado"]=="PENDIENTE" for x in tracking),
            "sin_resultado":sum(x["estado"]=="RESULTADO_NO_DISPONIBLE" for x in tracking),
            "excluidos":sum(x["estado"].startswith("EXCLUIDO") for x in tracking),
            "global":_summarize(good),
            "por_liga":{k:_summarize(v) for k,v in by_league.items()},
            "por_modelo":{k:_summarize(v) for k,v in by_model.items()},
            "aviso":"La muestra prospectiva será cero hasta finalizar los encuentros; no confundir con backtest retrospectivo."}
