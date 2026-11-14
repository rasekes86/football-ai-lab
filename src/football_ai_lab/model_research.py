"""Auditoría de pesos Poisson/Elo sobre un corte cronológico independiente.

Los pesos se eligen en observaciones antiguas y se comparan en fechas posteriores.
No modifica nunca el modelo de producción.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import log
import argparse
import json
from pathlib import Path
from .core import estimate_goals,probabilities
from .elo import elo_predict
from .sources import LEAGUES, load_history

WEIGHTS=(0.0,.15,.30,.45,.60)
BASE_WEIGHT=.30
VERSION="weight-audit-0.5"

def blend(poisson:dict,elo:dict,weight:float)->list[float]:
    assert 0<=weight<=1
    return [(1-weight)*poisson[k]+weight*elo[k] for k in ("home","draw","away")]

def score(rows:list[tuple],weight:float)->dict:
    if not rows:return {"muestra":0,"brier":None,"logloss":None}
    brier=loss=0.
    for _,y,poisson,elo in rows:
        p=blend(poisson,elo,weight)
        brier+=sum((v-int(i==y))**2 for i,v in enumerate(p))/3
        loss-=log(max(p[y],1e-9))
    return {"muestra":len(rows),"brier":round(brier/len(rows),6),
            "logloss":round(loss/len(rows),6)}

def observations(histories:dict, max_games_per_league:int=150)->list[tuple]:
    out=[]
    for league,games in histories.items():
        complete=sorted(games,key=lambda x:x["date"])
        recent=complete[380:][-max_games_per_league:]
        for match in recent:
            cutoff=match["date"]
            prior=[x for x in complete if x["date"]<cutoff]
            if len(prior)<380:continue
            lambdas=estimate_goals(prior,match["home"],match["away"],cutoff)
            elo=elo_predict(prior,match["home"],match["away"],cutoff)
            if not lambdas or not elo:continue
            poisson=probabilities(*lambdas)
            y=0 if match["home_goals"]>match["away_goals"] else 1 if match["home_goals"]==match["away_goals"] else 2
            out.append((cutoff,y,poisson,elo))
    return sorted(out,key=lambda t:t[0])

def validate(rows:list[tuple],min_train:int=80,min_holdout:int=40)->dict:
    unique=sorted(set(r[0] for r in rows))
    result={"version":VERSION,"estado":"MUESTRA_INSUFICIENTE","peso_produccion":BASE_WEIGHT,
            "se_aplica_automaticamente":False,"observaciones":len(rows)}
    if len(unique)<20:return result
    split=unique[int(len(unique)*.65)]
    train=[r for r in rows if r[0]<split]
    holdout=[r for r in rows if r[0]>=split]
    result.update({"entrenamiento":len(train),"prueba_posterior":len(holdout),
                   "fecha_corte":split.isoformat()})
    if len(train)<min_train or len(holdout)<min_holdout:return result
    train_scores={str(w):score(train,w) for w in WEIGHTS}
    chosen=min(WEIGHTS,key=lambda w:(train_scores[str(w)]["brier"],
                                   train_scores[str(w)]["logloss"]))
    production=score(holdout,BASE_WEIGHT)
    alt=score(holdout,chosen)
    improves=(alt["brier"]<production["brier"]-.002 and alt["logloss"]<production["logloss"]-.005)
    result.update({"estado":"COMPARACION_COMPLETADA",
                   "pesos_candidatos":list(WEIGHTS),
                   "entrenamiento_por_peso":train_scores,
                   "peso_seleccionado_con_pasado":chosen,
                   "prueba_posterior_peso_base":production,
                   "prueba_posterior_peso_elegido":alt,
                   "mejora_both_metrics_threshold":improves,
                   "recomendacion":"ESTUDIAR_CAMBIO_EN_EVALUACION_ADICIONAL" if improves else "MANTENER_0_30",
                   "aviso":"El holdout está usado para contrastar, no entrenar el peso. No introducir pesos sin prueba prospectiva."})
    return result

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="output_ml/auditoria_pesos.json")
    p.add_argument("--max-games",type=int,default=150)
    args=p.parse_args(argv)
    if not 20<=args.max_games<=300:p.error("max-games entre 20 y 300")
    now=datetime.now(timezone.utc)
    histories={code:load_history(code,now.date()) for code in LEAGUES}
    if not any(histories.values()):
        raise SystemExit("Sin históricos; no se publica auditoría nueva")
    data=validate(observations(histories,args.max_games))
    data["calculado_utc"]=now.isoformat()
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    print("Auditoría pesos:",data["estado"],"observaciones:",data["observaciones"])
if __name__=="__main__":
    main()
