"""Backtesting walk-forward (retrospectivo, jamás confundir con pronóstico archivado)."""
from __future__ import annotations
from collections import defaultdict
from math import log
from .ensemble import predict

FIELDS=["liga","fecha","local","visitante","resultado","prob_local","prob_empate",
        "prob_visitante","brier_modelo","logloss_modelo","brier_base","logloss_base","tipo"]
CLASSES = ("H","D","A")
KEYS = ("home","draw","away")

def actual(match: dict) -> str:
    return "H" if match["home_goals"]>match["away_goals"] else "D" if match["home_goals"]==match["away_goals"] else "A"

def brier(probs: list[float], outcome: str) -> float:
    return sum((p - (1 if cls==outcome else 0))**2 for p,cls in zip(probs,CLASSES))/3

def logloss(probs: list[float], outcome: str) -> float:
    return -log(max(1e-9,probs[CLASSES.index(outcome)]))

def baseline(prior: list[dict]) -> list[float]:
    # Media móvil previa; suavizado Laplace. No utiliza el resultado a predecir.
    sample=prior[-380:]
    counts={k:1 for k in CLASSES}
    for g in sample:
        counts[actual(g)]+=1
    denom=len(sample)+len(CLASSES)
    return [counts[k]/denom for k in CLASSES]

def run_backtest(histories: dict[str,list[dict]], leagues: dict[str,tuple], max_games: int=120) -> tuple[list[dict],dict]:
    records=[]
    for code,rows in histories.items():
        games=sorted(rows,key=lambda g:g["date"])
        # Solo evaluar después de tener al menos una temporada previa.
        eval_set=games[380:][-max_games:]
        for match in eval_set:
            prior=[g for g in games if g["date"] < match["date"]]
            if len(prior)<380: continue
            result=predict(games, match["home"], match["away"], match["date"])
            if result is None: continue
            p=[result[k] for k in KEYS]
            base=baseline(prior)
            outcome=actual(match)
            records.append({"liga":leagues[code][0],"fecha":match["date"].isoformat(),
                            "local":match["home"],"visitante":match["away"],"resultado":outcome,
                            "prob_local":f"{p[0]:.5f}","prob_empate":f"{p[1]:.5f}",
                            "prob_visitante":f"{p[2]:.5f}","brier_modelo":f"{brier(p,outcome):.6f}",
                            "logloss_modelo":f"{logloss(p,outcome):.6f}",
                            "brier_base":f"{brier(base,outcome):.6f}",
                            "logloss_base":f"{logloss(base,outcome):.6f}",
                            "tipo":"BACKTEST_RETROSPECTIVO"})
    groups=defaultdict(list)
    for row in records:
        groups[row["liga"]].append(row)
    summary={}
    for league,items in groups.items():
        summary[league]={"muestra":len(items)}
        for key in ("brier_modelo","logloss_modelo","brier_base","logloss_base"):
            summary[league][key]=round(sum(float(r[key]) for r in items)/len(items),5)
        summary[league]["modelo_mejor_brier"]=summary[league]["brier_modelo"]<summary[league]["brier_base"]
    summary["_aviso"]="Evaluación retrospectiva, no prueba prospectiva de rentabilidad. No usa cuotas."
    return records,summary
