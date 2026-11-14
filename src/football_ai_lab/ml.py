"""XGBoost exploratorio: features temporales y evaluación cronológica no aleatoria.

Se entrena por separado del modelo de producción. Nunca se publican apuestas.
"""
from __future__ import annotations
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from itertools import groupby
from math import log
import argparse
import csv
import json
import logging
from pathlib import Path

from .core import normalize_team
from .ensemble import predict as poisson_elo_predict
from .sources import LEAGUES, load_history, load_fixtures

LOG=logging.getLogger(__name__)
VERSION="xgboost-temporal-0.5"
LEAGUE_KEYS=list(LEAGUES)
COLUMNS=["fecha_utc","liga","local","visitante","ml_prob_local","ml_prob_empate",
         "ml_prob_visitante","modelo","fecha_analisis_utc","estado"]

def outcome(game:dict)->int:
    if game["home_goals"]>game["away_goals"]:return 0
    if game["home_goals"]==game["away_goals"]:return 1
    return 2

def state():
    return {"all":defaultdict(lambda:deque(maxlen=12)),
            "home":defaultdict(lambda:deque(maxlen=12)),
            "away":defaultdict(lambda:deque(maxlen=12)),
            "league":deque(maxlen=380)}

def update(s:dict,game:dict)->None:
    h,a=normalize_team(game["home"]),normalize_team(game["away"])
    d=game["date"]
    hg,ag=game["home_goals"],game["away_goals"]
    # Optional recorded stats: absent values remain None rather than fake zeros.
    row_h=(d,hg,ag,3 if hg>ag else 1 if hg==ag else 0,
           game.get("home_shots"),game.get("home_on_target"),game.get("home_corners"))
    row_a=(d,ag,hg,3 if ag>hg else 1 if ag==hg else 0,
           game.get("away_shots"),game.get("away_on_target"),game.get("away_corners"))
    s["all"][h].append(row_h)
    s["all"][a].append(row_a)
    s["home"][h].append(row_h)
    s["away"][a].append(row_a)
    s["league"].append((hg,ag))

def _mean(seq:list[tuple],index:int,default:float)->float:
    return sum(x[index] for x in seq)/len(seq) if seq else default

def _available_stat(rows:list[tuple],index:int)->list[float]:
    last=rows[-5:]
    available=[float(row[index]) for row in last if row[index] is not None]
    # Return mean + availability fraction to distinguish missing from genuine 0.
    return [sum(available)/len(available) if available else 0.0,
            len(available)/len(last) if last else 0.0]


def _features(s:dict,code:str,home:str,away:str,when:date)->list[float]|None:
    h,a=normalize_team(home),normalize_team(away)
    ha=list(s["all"].get(h,()))
    aa=list(s["all"].get(a,()))
    if len(ha)<5 or len(aa)<5 or len(s["league"])<30:
        return None
    hh=list(s["home"].get(h,()))
    aw=list(s["away"].get(a,()))
    lg=list(s["league"])
    avg_h=sum(x[0] for x in lg)/len(lg)
    avg_a=sum(x[1] for x in lg)/len(lg)
    # Only observations prior to the fixture date are present in s.
    fh=[
       _mean(ha,1,avg_h),_mean(ha,2,avg_a),_mean(ha,3,1.3),
       _mean(aa,1,avg_a),_mean(aa,2,avg_h),_mean(aa,3,1.3),
       _mean(hh,1,avg_h),_mean(hh,2,avg_a),
       _mean(aw,1,avg_a),_mean(aw,2,avg_h),
       min(30,(when-ha[-1][0]).days) if ha else 30,
       min(30,(when-aa[-1][0]).days) if aa else 30,
       min(len(ha),12),min(len(aa),12),avg_h,avg_a,
    ]
    fh.extend(1.0 if code==key else 0.0 for key in LEAGUE_KEYS)
    # Data-provider measured stats, not xG estimates. Missingness is explicit.
    for team_games in (ha,aa):
        for idx in (4,5,6):
            fh.extend(_available_stat(team_games,idx))
    return [float(x) for x in fh]

def build_samples(histories:dict[str,list[dict]])->list[tuple]:
    rows=[]
    for code,games in histories.items():
        st=state()
        sorted_games=sorted(games,key=lambda m:m["date"])
        for day,iterator in groupby(sorted_games,key=lambda x:x["date"]):
            todays=list(iterator)
            # Freeze at the start of the day, preventing contamination from same-day results.
            for match in todays:
                f=_features(st,code,match["home"],match["away"],day)
                if f is not None:
                    rows.append((day,code,f,outcome(match),match["home"],match["away"]))
            for match in todays:
                update(st,match)
    return sorted(rows,key=lambda r:(r[0],r[1]))

def feature_for_fixture(histories:dict[str,list[dict]],f:dict)->list[float]|None:
    code=f["league"]
    cutoff=f["kickoff"].date()
    st=state()
    for m in sorted(histories.get(code,[]),key=lambda m:m["date"]):
        if m["date"]>=cutoff:break
        update(st,m)
    return _features(st,code,f["home"],f["away"],cutoff)

def split_by_date(records:list[tuple],portion:float=.8):
    dates=sorted(set(r[0] for r in records))
    if len(dates)<50:return [],[],None
    boundary=dates[int(len(dates)*portion)]
    train=[r for r in records if r[0]<boundary]
    test=[r for r in records if r[0]>=boundary]
    return train,test,boundary

def score(actual:list[int],p:list[list[float]])->dict:
    n=len(actual)
    if n==0:raise ValueError("No observations")
    brier=sum(sum((q-(1. if i==y else 0.))**2 for i,q in enumerate(row))/3
              for y,row in zip(actual,p))/n
    logloss=sum(-log(max(1e-9,row[y])) for y,row in zip(actual,p))/n
    return {"brier":round(brier,6),"logloss":round(logloss,6)}

def calibration_by_outcome(y:list[int],p:list[list[float]],bins:int=5)->dict:
    """Diagnóstico de fiabilidad por clases sin afirmar calibración causal."""
    table={}
    for k,label in enumerate(("local","empate","visitante")):
        rows=[]
        for bin_id in range(bins):
            subset=[(yt,row[k]) for yt,row in zip(y,p)
                    if min(bins-1,int(min(1.0,row[k])*bins))==bin_id]
            if not subset:continue
            rows.append({"rango":f"{bin_id/bins:.1f}-{(bin_id+1)/bins:.1f}",
                         "n":len(subset),
                         "estimado":round(sum(x[1] for x in subset)/len(subset),4),
                         "observado":round(sum(yt==k for yt,_ in subset)/len(subset),4)})
        table[label]=rows
    return table


def train_and_evaluate(histories:dict,fixtures:list,now:datetime)->tuple[list[dict],dict]:
    data=build_samples(histories)
    train,valid,boundary=split_by_date(data)
    report={"version":VERSION,"as_of_utc":now.isoformat(),"status":"INSUFFICIENT_DATA",
            "historic_rows":len(data),"train_rows":len(train),"validation_rows":len(valid),
            "split_date":boundary.isoformat() if boundary else None,
            "warnings":["Evaluación retrospectiva; el modelo NO está habilitado para sugerir apuestas."]}
    if len(train)<400 or len(valid)<90:return [],report
    # Import lazy: dependencies are installed only in the separate weekly workflow.
    import xgboost as xgb
    xs=[r[2] for r in train]; ys=[r[3] for r in train]
    vx=[r[2] for r in valid]; vy=[r[3] for r in valid]
    settings=dict(n_estimators=100,max_depth=3,learning_rate=.06,
                  subsample=.85,colsample_bytree=.90,objective="multi:softprob",
                  num_class=3,eval_metric="mlogloss",random_state=2026,n_jobs=2)
    model=xgb.XGBClassifier(**settings)
    model.fit(xs,ys,verbose=False)
    yp=model.predict_proba(vx).tolist()
    freq=[(ys.count(k)+1)/(len(ys)+3) for k in range(3)]
    baseline=[freq for _ in valid]
    real=score(vy,yp)
    reference=score(vy,baseline)
    # Same held-out fixtures for a fair comparison with the production model.
    paired=[]
    for idx,record in enumerate(valid):
        day,league,features,outcome_num,home,away=record
        existing=poisson_elo_predict(histories[league],home,away,day)
        if existing is None:continue
        paired.append((outcome_num,yp[idx],
                       [existing[key] for key in ("home","draw","away")],
                       baseline[idx]))
    comparison={"muestra":len(paired),
                "nota":"Solo partidos comunes del mismo holdout posterior al entrenamiento."}
    if paired:
        yy=[x[0] for x in paired]
        comparison.update({"xgboost":score(yy,[x[1] for x in paired]),
                           "poisson_elo":score(yy,[x[2] for x in paired]),
                           "frecuencia_historica":score(yy,[x[3] for x in paired])})

    report.update({"status":"VALIDADO_RETROSPECTIVAMENTE",
                   "holdout_start":min(r[0] for r in valid).isoformat(),
                   "holdout_end":max(r[0] for r in valid).isoformat(),
                   "xgboost_holdout":real,"frecuencia_historica":reference,
                   "beats_frequency_brier":real["brier"]<reference["brier"],
                   "comparacion_misma_muestra":comparison,
                   "calibracion_diagnostica":calibration_by_outcome(vy,yp),
                   "warnings":["Estas métricas no son pruebas prospectivas ni rentabilidad.",
                               "El modelo NO participa en el consenso Poisson/Elo hasta una revisión independiente."]})
    # Training full history only after finishing the held-out validation.
    final=xgb.XGBClassifier(**settings)
    final.fit([r[2] for r in data],[r[3] for r in data],verbose=False)
    results=[]
    for f in fixtures:
        if f["kickoff"]<=now:continue
        features=feature_for_fixture(histories,f)
        if features is None:continue
        p=final.predict_proba([features])[0]
        if abs(sum(p)-1)>1e-5:continue
        results.append({"fecha_utc":f["kickoff"].isoformat(),
                        "liga":LEAGUES[f["league"]][0],
                        "local":f["home"],"visitante":f["away"],
                        "ml_prob_local":f"{p[0]:.5f}","ml_prob_empate":f"{p[1]:.5f}",
                        "ml_prob_visitante":f"{p[2]:.5f}",
                        "modelo":VERSION,"fecha_analisis_utc":now.isoformat(),
                        "estado":"EXPERIMENTAL_NO_PRODUCCION"})
    report["predictions"]=len(results)
    return results,report

def compare_to_production(ml_rows:list[dict],production_rows:list[dict])->list[dict]:
    def key(row):
        return (row.get("fecha_utc"),row.get("liga"),
                normalize_team(row.get("local","")),normalize_team(row.get("visitante","")))
    indexed={key(p):p for p in production_rows}
    result=[]
    for ml in ml_rows:
        base=indexed.get(key(ml))
        if base is None:continue
        try:
            real=[float(base[x]) for x in ("prob_local","prob_empate","prob_visitante")]
            experimental=[float(ml[x]) for x in ("ml_prob_local","ml_prob_empate","ml_prob_visitante")]
        except (ValueError,KeyError):continue
        discrepancy=max(abs(a-b) for a,b in zip(real,experimental))
        flag="REVISAR" if discrepancy>=.15 else "VIGILAR" if discrepancy>=.08 else "COINCIDEN"
        result.append({"fecha_utc":ml["fecha_utc"],"liga":ml["liga"],
                       "local":ml["local"],"visitante":ml["visitante"],
                       "modelo_principal_local":f"{real[0]:.5f}",
                       "modelo_experimental_local":f"{experimental[0]:.5f}",
                       "max_diferencia_pp":f"{100*discrepancy:.2f}",
                       "alerta":flag,
                       "nota":"Discrepancia informativa; NO combinar modelos ni realizar apuestas"})
    return sorted(result,key=lambda x:float(x["max_diferencia_pp"]),reverse=True)


def main(argv=None):
    pa=argparse.ArgumentParser()
    pa.add_argument("--days",type=int,default=14)
    pa.add_argument("--output",default="output_ml")
    args=pa.parse_args(argv)
    if not 1<=args.days<=31:pa.error("days 1..31")
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    now=datetime.now(timezone.utc)
    histories={code:load_history(code,now.date()) for code in LEAGUES}
    if not any(histories.values()):raise SystemExit("Históricos indisponibles")
    fixtures=[f for code in LEAGUES for f in load_fixtures(code,now.date(),args.days)]
    rows,report=train_and_evaluate(histories,fixtures,now)
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    (out/"validacion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/"predicciones_ml.csv").open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=COLUMNS)
        w.writeheader();w.writerows(rows)
    # Compare only predictions for the exact same scheduled match and kickoff.
    prod_path=Path("output/predicciones.csv")
    prod=[]
    if prod_path.exists():
        with prod_path.open(newline="",encoding="utf-8") as f:
            prod=list(csv.DictReader(f))
    comparison=compare_to_production(rows,prod)
    fields=["fecha_utc","liga","local","visitante","modelo_principal_local",
            "modelo_experimental_local","max_diferencia_pp","alerta","nota"]
    with (out/"discrepancias.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader();writer.writerows(comparison)
    high=sum(x["alerta"]=="REVISAR" for x in comparison)
    report["comparacion_futuros"]={"partidos_comunes":len(comparison),
                                    "discrepancias_15pp_o_mas":high}
    (out/"validacion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"ML: {report['status']} | training: {report['train_rows']} | validation: {report['validation_rows']} | forecasts: {len(rows)}")

if __name__=="__main__":
    main()
