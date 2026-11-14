"""Selector de mercados prepartido: probabilidades, cobertura y abstención.

Calcula mercados de goles con Poisson y mercados de resultado desde el consenso
Poisson/Elo. Los conteos de tiros/córners/tarjetas se publican EXPLORATORIOS,
NO se incluyen en el Top 3 principal sin validación temporal específica.
Sin automatizar apuestas ni inventar cuotas de casas.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from math import exp, isfinite
from .core import normalize_team, pmf

VERSION = "market-selector-0.6"
MAX_GOALS = 18
# Evita mercados casi triviales que carecerían de precio significativo.
MIN_PROBABILITY = .55
MIN_FAIR_DECIMAL = 1.15
MAX_TOP = 3
FIELDS = ["id","fecha_utc","liga","local","visitante","posicion","mercado",
          "seleccion","familia","probabilidad","cuota_justa","origen",
          "nivel","cuota_real","casa","fecha_cuota_utc","ev_teorico",
          "motivo","advertencia"]
COUNT_METRICS = {
    "corners": ("Córners totales", (6.5,7.5,8.5,9.5,10.5,11.5)),
    "shots": ("Tiros totales", (17.5,19.5,21.5,23.5,25.5)),
    "on_target": ("Tiros a puerta totales", (4.5,5.5,6.5,7.5,8.5,9.5)),
    "yellow": ("Tarjetas amarillas totales", (2.5,3.5,4.5,5.5))
}
DISCLAIMER = ("Estimación estadística, NO apuesta recomendada. Sin ventaja "
              "económica probada; las selecciones pueden estar correlacionadas.")

def _distribution(home_lambda: float, away_lambda: float) -> list[tuple[int,int,float]]:
    if not all(isfinite(x) and .05<x<=7 for x in (home_lambda,away_lambda)):
        raise ValueError("Medias de goles inválidas")
    matrix=[(h,a,pmf(h,home_lambda)*pmf(a,away_lambda))
            for h in range(MAX_GOALS+1) for a in range(MAX_GOALS+1)]
    total=sum(x[2] for x in matrix)
    if not .999 < total <= 1.0000001:
        raise ValueError("Cola de goles no controlada")
    return [(h,a,p/total) for h,a,p in matrix]

def _candidate(market: str, selection: str, family: str, probability: float,
               origin: str, reason: str, level: str = "MODELO_NO_CALIBRADO") -> dict:
    if not isfinite(probability) or not 0<probability<1:
        raise ValueError("Probabilidad inválida")
    return {"mercado":market,"seleccion":selection,"familia":family,
            "probabilidad":round(probability,6),"cuota_justa":round(1/probability,3),
            "origen":origin,"nivel":level,"motivo":reason}

def goal_candidates(p: dict) -> list[dict]:
    lh,la=float(p["goles_esperados_local"]),float(p["goles_esperados_visitante"])
    matrix=_distribution(lh,la)
    home,away=p["local"],p["visitante"]
    ph,pd,pa=(float(p[k]) for k in ("prob_local","prob_empate","prob_visitante"))
    if abs(ph+pd+pa-1)>.001:raise ValueError("1X2 incoherente")
    entries=[
        _candidate("1X2",home+" gana","resultado",ph,"Consenso Poisson/Elo","Resultado 1X2 del modelo principal"),
        _candidate("1X2","Empate","resultado",pd,"Consenso Poisson/Elo","Resultado 1X2 del modelo principal"),
        _candidate("1X2",away+" gana","resultado",pa,"Consenso Poisson/Elo","Resultado 1X2 del modelo principal"),
        _candidate("Doble oportunidad","1X: "+home+" o empate","resultado",ph+pd,"Consenso Poisson/Elo","Suma de probabilidades de local y empate"),
        _candidate("Doble oportunidad","X2: empate o "+away,"resultado",pd+pa,"Consenso Poisson/Elo","Suma de empate y visitante"),
        _candidate("Doble oportunidad","12: gana uno de los dos","resultado",ph+pa,"Consenso Poisson/Elo","Complemento del empate"),
    ]
    def q(pred):
        return sum(prob for h,a,prob in matrix if pred(h,a))
    for threshold in (0.5,1.5,2.5,3.5,4.5):
        entries.append(_candidate("Total goles",f"Más de {str(threshold).replace('.',',')} goles","total_goles",
                                  q(lambda h,a,t=threshold:h+a>t),"Poisson de goles",
                                  "Distribución conjunta de goles del modelo"))
        entries.append(_candidate("Total goles",f"Menos de {str(threshold).replace('.',',')} goles","total_goles",
                                  q(lambda h,a,t=threshold:h+a<t),"Poisson de goles",
                                  "Distribución conjunta de goles del modelo"))
    for team,label in ((True,home),(False,away)):
        for t in (.5,1.5,2.5):
            entries.append(_candidate("Goles equipo",f"{label}: más de {str(t).replace('.',',')} goles",
                                     "goles_local" if team else "goles_visitante",
                                     q(lambda h,a,t=t,team=team:(h if team else a)>t),
                                     "Poisson de goles","Goles esperados del equipo"))
            entries.append(_candidate("Goles equipo",f"{label}: menos de {str(t).replace('.',',')} goles",
                                     "goles_local" if team else "goles_visitante",
                                     q(lambda h,a,t=t,team=team:(h if team else a)<t),
                                     "Poisson de goles","Goles esperados del equipo"))
    for team,label in ((True,home),(False,away)):
        for line in (-1.5,1.5,2.5):
            probability=q(lambda h,a,l=line,team=team:(h-a+l if team else a-h+l)>0)
            entries.append(_candidate("Hándicap europeo (medio gol)",
                           label+" "+("+" if line>0 else "")+str(line).replace(".",","),
                           "resultado",probability,"Poisson de goles",
                           "Hándicap de medio gol: sin posibilidad de devolución"))
    entries.append(_candidate("Ambos marcan","Sí","ambos_marcan",
                              q(lambda h,a:h>0 and a>0),"Poisson de goles",
                              "Ambos equipos marcan al menos un gol"))
    entries.append(_candidate("Ambos marcan","No","ambos_marcan",
                              q(lambda h,a:h==0 or a==0),"Poisson de goles",
                              "Uno o ambos equipos terminan sin marcar"))
    return entries

def _prior(games:list[dict],attr:str,side:str,default:float,limit:int=25)->float:
    samples=[g[attr] for g in games if isinstance(g.get(attr),(int,float)) and g[attr]>=0][:limit]
    return (sum(samples)+8*default)/(len(samples)+8)

def _count_cdf(k:int,mu:float,variance:float)->float:
    """Convolución simplificada: NB si hay sobredispersión, Poisson en otro caso."""
    if k<0:return 0.
    if mu<=0 or variance<0:raise ValueError("Momentos inválidos")
    if variance>mu*1.10 and mu>0:
        r=max(.25,mu**2/(variance-mu))
        prob=(r/(r+mu))**r
        ratio=mu/(r+mu)
        total=prob
        for i in range(1,k+1):
            prob*=((i-1+r)/i)*ratio
            total+=prob
        return min(1.,max(0.,total))
    prob=exp(-mu);total=prob
    for i in range(1,k+1):
        prob*=mu/i
        total+=prob
    return min(1.,max(0.,total))

def exploratory_counts(p:dict,games:list[dict],kickoff_date:date)->list[dict]:
    """Solo medias de conteos observados; NO son predicciones validadas."""
    h,a=normalize_team(p["local"]),normalize_team(p["visitante"])
    past=sorted((g for g in games if g["date"]<kickoff_date),
                key=lambda g:g["date"],reverse=True)
    home=[g for g in past if normalize_team(g["home"])==h]
    away=[g for g in past if normalize_team(g["away"])==a]
    results=[]
    for metric,(title,thresholds) in COUNT_METRICS.items():
        hk,ak="home_"+metric,"away_"+metric
        league=[(g[hk],g[ak]) for g in past[:500] if isinstance(g.get(hk),(int,float))
                and isinstance(g.get(ak),(int,float))]
        hg=[g for g in home if isinstance(g.get(hk),(int,float)) and isinstance(g.get(ak),(int,float))][:25]
        ag=[g for g in away if isinstance(g.get(hk),(int,float)) and isinstance(g.get(ak),(int,float))][:25]
        if len(league)<120 or len(hg)<12 or len(ag)<12:continue
        mean_h=sum(v[0] for v in league)/len(league)
        mean_a=sum(v[1] for v in league)/len(league)
        ph=_prior(hg,hk,"home",mean_h)
        pah=_prior(ag,hk,"away",mean_h)
        pa=_prior(ag,ak,"away",mean_a)
        pha=_prior(hg,ak,"home",mean_a)
        mu=(ph+pah+pa+pha)/2
        totals=[u+v for u,v in league]
        avg=sum(totals)/len(totals)
        v=sum((t-avg)**2 for t in totals)/len(totals)
        # Estimate dispersion from league observations; never claim validated model.
        estimated_var=max(mu,mu*(v/avg)) if avg>0 else mu
        for line in thresholds:
            under=_count_cdf(int(line),mu,estimated_var)
            for selection,prob in ((f"Menos de {str(line).replace('.',',')} {title.lower()}",under),
                                   (f"Más de {str(line).replace('.',',')} {title.lower()}",1-under)):
                if not 0<prob<1:continue
                c=_candidate(title,selection,"exp_"+metric,prob,
                             "Histórico de conteos con dispersión",
                             f"Exploratorio: {len(hg)} partidos local, {len(ag)} visitante y {len(league)} ligueros",
                             "EXPLORATORIO_NO_VALIDADO")
                c["muestra_local"]=len(hg);c["muestra_visitante"]=len(ag)
                results.append(c)
    return results

def offered_prices(prediction:dict,market_rows:list[dict],now:datetime)->dict[str,dict]:
    """Sólo cuotas realmente ofrecidas en 1X2; nunca fair odds de InferSports."""
    found={}
    for m in market_rows:
        if m.get("id")!=prediction.get("id") or m.get("estado")!="COMPARACIÓN_SIN_VALIDAR":
            continue
        if m.get("proveedor")!="The Odds API" or not m.get("casa"):continue
        try:
            at=datetime.fromisoformat(m["fecha_cuota_utc"].replace("Z","+00:00"))
            if at.tzinfo is None or not 0 <= (now-at).total_seconds() <= 6*3600:
                continue
            for outcome,key in ((prediction["local"],"cuota_local"),
                                ("Empate","cuota_empate"),(prediction["visitante"],"cuota_visitante")):
                odd=float(m[key])
                if isfinite(odd) and odd>1:
                    found[outcome]={"precio":odd,"casa":m["casa"],"fecha":at.isoformat()}
        except (ValueError,TypeError,KeyError):continue
    return found

def select_match(prediction:dict,history:list[dict],market_rows:list[dict],
                 now:datetime,limit:int=MAX_TOP)->dict:
    """Devuelve top probabilístico diversificado y top valor sólo con precios reales."""
    if prediction.get("tipo") not in ("REAL","DEMO"):raise ValueError("Modo no autorizado")
    cutoff=datetime.fromisoformat(prediction["fecha_utc"].replace("Z","+00:00"))
    if cutoff.tzinfo is None or cutoff<=now:raise ValueError("El encuentro ya ha empezado")
    candidates=goal_candidates(prediction)
    experimental=exploratory_counts(prediction,history,cutoff.date())
    eligible=[c for c in candidates if c["probabilidad"]>=MIN_PROBABILITY
              and c["cuota_justa"]>=MIN_FAIR_DECIMAL]
    eligible.sort(key=lambda c:(-c["probabilidad"],c["seleccion"]))
    selected=[];families=set()
    for c in eligible:
        if c["familia"] in families:continue
        selected.append(dict(c,posicion=len(selected)+1))
        families.add(c["familia"])
        if len(selected)==limit:break
    prices=offered_prices(prediction,market_rows,now)
    value=[]
    for c in candidates:
        # Etiqueta 1X2 de usuario frente al nombre puro del equipo en la API.
        if c["mercado"]!="1X2":
            continue
        quote_name=(prediction["local"] if c["seleccion"]==prediction["local"]+" gana"
                    else prediction["visitante"] if c["seleccion"]==prediction["visitante"]+" gana"
                    else "Empate")
        quote=prices.get(quote_name)
        if not quote:continue
        ev=c["probabilidad"]*quote["precio"]-1
        if ev<=.03:continue
        value.append(dict(c,cuota_real=quote["precio"],casa=quote["casa"],
                          fecha_cuota_utc=quote["fecha"],ev_teorico=round(ev,4)))
    value.sort(key=lambda x:-x["ev_teorico"])
    value=value[:limit]
    warning=("Las estimaciones son experimentales: no hay garantía de acierto ni "
             "evidencia suficiente de ventaja sobre casas de apuestas.")
    return {"id":prediction["id"],"fecha_utc":prediction["fecha_utc"],
            "liga":prediction["liga"],"local":prediction["local"],
            "visitante":prediction["visitante"],"calculado_utc":now.isoformat(),
            "version":VERSION,"filtros":{"probabilidad_minima":MIN_PROBABILITY,
                                       "cuota_justa_minima":MIN_FAIR_DECIMAL,
                                       "una_por_familia":True},
            "top_probabilidad":selected,"top_valor_exploratorio":value,
            "mercados_goles_evaluados":len(candidates),
            "mercados_conteos_exploratorios":len(experimental),
            "exploratorios":sorted(experimental,key=lambda x:-x["probabilidad"])[:10],
            "no_disponible":["Tiros individuales de jugadores",
                             "Goleadores individuales",
                             "Hándicaps asiáticos con devolución y liquidación fraccionada",
                             "Cuotas ofrecidas de mercados de goles y córners sin fuente real"],
            "estado_valor":("CON_CUOTAS_1X2" if prices else "SIN_CUOTAS_REALES_VERIFICADAS"),
            "advertencia":warning}

def global_top(matches:list[dict],limit:int=3)->list[dict]:
    """Una selección por partido para evitar duplicados muy correlacionados."""
    first=[]
    for m in matches:
        if m["top_probabilidad"]:
            c=dict(m["top_probabilidad"][0])
            c.update({"id":m["id"],"liga":m["liga"],"local":m["local"],
                      "visitante":m["visitante"],"fecha_utc":m["fecha_utc"]})
            first.append(c)
    first.sort(key=lambda c:-c["probabilidad"])
    return first[:limit]

def flat_rows(matches:list[dict])->list[dict]:
    rows=[]
    for m in matches:
        for c in m["top_probabilidad"]:
            row={field:"" for field in FIELDS}
            row.update({k:m[k] for k in ("id","fecha_utc","liga","local","visitante")})
            row.update({k:v for k,v in c.items() if k in row})
            row["advertencia"]=DISCLAIMER
            rows.append(row)
    return rows
