"""Auditoría walk-forward de mercados de córners, tiros y tarjetas.

Entradas: únicamente estadísticas completas del partido y datos anteriores.
El mismo algoritmo de conteos que se usa en el selector se evalúa contra la
frecuencia liguera previa para cada línea. La aprobación es retrospectiva,
NO validación prospectiva ni demostración de ventaja de mercado.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from math import log
from .selector import COUNT_METRICS, exploratory_counts

VERSION="count-markets-walkforward-0.7"
MIN_TEST=85
MIN_COVERAGE=.65
MIN_GAIN_BRIER=.003
MIN_GAIN_LOGLOSS=.005
MAX_ECE=.09

def _safe(p:float)->float:
    return max(.000001,min(.999999,float(p)))

def _score(y:list[int],model:list[float],base:list[float])->dict:
    n=len(y)
    if n==0:return {"n":0}
    bs=sum((p-t)**2 for p,t in zip(model,y))/n
    bb=sum((p-t)**2 for p,t in zip(base,y))/n
    ls=-sum(t*log(_safe(p))+(1-t)*log(_safe(1-p)) for p,t in zip(model,y))/n
    lb=-sum(t*log(_safe(p))+(1-t)*log(_safe(1-p)) for p,t in zip(base,y))/n
    groups=[[] for _ in range(5)]
    for t,p in zip(y,model):
        groups[min(4,int(p*5))].append((t,p))
    ece=sum(len(g)/n*abs(sum(p for _,p in g)/len(g)-sum(t for t,_ in g)/len(g))
            for g in groups if g)
    return {"n":n,"brier_modelo":round(bs,6),"brier_referencia":round(bb,6),
            "logloss_modelo":round(ls,6),"logloss_referencia":round(lb,6),
            "error_calibracion_ece":round(ece,6)}

def _baseline(prior:list[dict],metric:str,line:float)->float|None:
    hk,ak="home_"+metric,"away_"+metric
    sample=[g[hk]+g[ak] for g in prior
            if isinstance(g.get(hk),(int,float)) and isinstance(g.get(ak),(int,float))][-380:]
    if len(sample)<120:return None
    # Simple benchmark with Laplace smoothing and no results of current match.
    return (sum(v<line for v in sample)+2)/(len(sample)+4)

def market_key(league:str,metric:str,line:float)->str:
    return f"{league}|{metric}|{line:.1f}"

def validate(histories:dict[str,list[dict]],now:datetime,
             max_games:int=180)->dict:
    report={"version":VERSION,"calculado_utc":now.isoformat(),
            "criterios":{"min_partidos_prueba":MIN_TEST,
                         "cobertura_minima":MIN_COVERAGE,
                         "mejora_brier_minima":MIN_GAIN_BRIER,
                         "mejora_logloss_minima":MIN_GAIN_LOGLOSS,
                         "ece_maximo":MAX_ECE},
            "por_liga":{},"aprobados":[],
            "nota":"Backtest cronológico retrospectivo con comparación previa. "
                   "Los mercados aprobados siguen pendientes de confirmación prospectiva; "
                   "no se demuestra rentabilidad."}
    for code,games in histories.items():
        ordered=sorted((g for g in games if g["date"]<=now.date()),key=lambda x:x["date"])
        holdout=ordered[-max_games:] if max_games else []
        start_date=holdout[0]["date"] if holdout else None
        # Process by date to avoid predictions using other same-day final scores.
        stats=defaultdict(lambda:{"outcomes":[],"model":[],"reference":[]})
        coverage=defaultdict(int)
        dated=sorted(set(g["date"] for g in holdout))
        for day in dated:
            prior=[g for g in ordered if g["date"]<day]
            targets=[g for g in holdout if g["date"]==day]
            baseline_cache={(metric,line):_baseline(prior,metric,line)
                            for metric,(_,lines) in COUNT_METRICS.items() for line in lines}
            for game in targets:
                pretend={"local":game["home"],"visitante":game["away"]}
                candidates=exploratory_counts(pretend,prior,day)
                by_key={(c.get("metrica"),c.get("linea")):c for c in candidates
                        if c.get("direccion")=="menos"}
                for metric,(_,lines) in COUNT_METRICS.items():
                    hk,ak="home_"+metric,"away_"+metric
                    if not (isinstance(game.get(hk),(int,float))
                            and isinstance(game.get(ak),(int,float))):
                        continue
                    for line in lines:
                        key=market_key(code,metric,line)
                        coverage[key]+=1
                        candidate=by_key.get((metric,line))
                        baseline=baseline_cache.get((metric,line))
                        if candidate is None or baseline is None:continue
                        stat=stats[key]
                        stat["outcomes"].append(int(game[hk]+game[ak]<line))
                        stat["model"].append(candidate["probabilidad"])
                        stat["reference"].append(baseline)
        details={}
        for metric,(_,lines) in COUNT_METRICS.items():
            for line in lines:
                key=market_key(code,metric,line)
                s=stats[key]
                scored=_score(s["outcomes"],s["model"],s["reference"])
                n=scored["n"]
                total=coverage[key]
                fraction=n/total if total else 0
                eligible=(n>=MIN_TEST and fraction>=MIN_COVERAGE and
                    scored["brier_referencia"]-scored["brier_modelo"]>=MIN_GAIN_BRIER and
                    scored["logloss_referencia"]-scored["logloss_modelo"]>=MIN_GAIN_LOGLOSS and
                    scored["error_calibracion_ece"]<=MAX_ECE)
                entry={"metrica":metric,"linea":line,"partidos_con_resultado":total,
                       "cobertura_modelo":round(fraction,4),"apto_retro":bool(eligible),
                       **scored}
                details[key]=entry
                if eligible:report["aprobados"].append(key)
        report["por_liga"][code]={"holdout_desde":start_date.isoformat() if start_date else None,
                                 "hasta":dated[-1].isoformat() if dated else None,
                                 "partidos_holdout":len(holdout),"lineas":details}
    return report
