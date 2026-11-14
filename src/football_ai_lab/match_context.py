"""Dossier prepartido causal: resultados, forma, descanso y métricas del histórico.

No introduce xG sintético; si no hay xG auténtico se declara ausente.
"""
from __future__ import annotations
from datetime import date
from .core import normalize_team

STATS=("shots","on_target","corners","yellow","red")
VERSION="prepartido-history-0.5"

def _summary(games:list[dict], name:str, target:date, limit:int=5)->dict:
    ident=normalize_team(name)
    prior=sorted((x for x in games if x["date"]<target and
           ident in (normalize_team(x["home"]),normalize_team(x["away"]))),
                 key=lambda x:x["date"],reverse=True)
    sample=prior[:limit]
    result={"partidos":len(sample),"v":0,"e":0,"d":0,"goles_favor":0,"goles_contra":0,
            "puntos":0,"dias_descanso":(target-prior[0]["date"]).days if prior else None,
            "ultimos":[],
            "medias":{"tiros":None,"tiros_puerta":None,"corners":None,"amarillas":None,"rojas":None}}
    metrics={"tiros":"shots","tiros_puerta":"on_target","corners":"corners",
             "amarillas":"yellow","rojas":"red"}
    totals={key:[] for key in metrics}
    for m in sample:
        own_home=normalize_team(m["home"])==ident
        gf=m["home_goals"] if own_home else m["away_goals"]
        ga=m["away_goals"] if own_home else m["home_goals"]
        outcome="V" if gf>ga else "E" if gf==ga else "D"
        result[outcome.lower()]+=1
        result["puntos"]+=3 if outcome=="V" else 1 if outcome=="E" else 0
        result["goles_favor"]+=gf;result["goles_contra"]+=ga
        result["ultimos"].append({"fecha":m["date"].isoformat(),"local":m["home"],
             "visitante":m["away"],"marcador":f'{m["home_goals"]}-{m["away_goals"]}',
             "resultado":outcome})
        for key,source in metrics.items():
            val=m.get(("home_" if own_home else "away_")+source)
            if isinstance(val,(int,float)):
                totals[key].append(val)
    for key,values in totals.items():
        if values:result["medias"][key]=round(sum(values)/len(values),2)
    return result

def _h2h(games:list[dict],home:str,away:str,cutoff:date)->list[dict]:
    h,a=normalize_team(home),normalize_team(away)
    encounters=[]
    for m in sorted(games,key=lambda x:x["date"],reverse=True):
        if m["date"]>=cutoff:continue
        if {normalize_team(m["home"]),normalize_team(m["away"])}=={h,a}:
            encounters.append({"fecha":m["date"].isoformat(),
                               "local":m["home"],"visitante":m["away"],
                               "marcador":f'{m["home_goals"]}-{m["away_goals"]}'})
        if len(encounters)==5:break
    return encounters

def quality(games:list[dict],home:str,away:str,cutoff:date)->dict:
    before=[x for x in games if x["date"]<cutoff]
    counts={}
    for side,name in (("local",home),("visitante",away)):
        norm=normalize_team(name)
        all_matches=sum(norm in (normalize_team(x["home"]),normalize_team(x["away"])) for x in before)
        at_venue=sum(normalize_team(x["home" if side=="local" else "away"])==norm for x in before)
        counts[side]={"todos":all_matches,"recinto":at_venue,"identificado":all_matches>0}
    missing=[]
    for side,x in counts.items():
        if not x["identificado"]:missing.append(f"{side}: nombre o club sin histórico de primera división")
        elif x["recinto"]<5:missing.append(f"{side}: menos de 5 encuentros en su condición")
    return {"equipos":counts,"motivos":missing,
            "suficiente_modelo_actual":not missing and len(before)>=20}

def dossier(games:list[dict],f:dict)->dict:
    cutoff=f["kickoff"].date()
    return {"id":f.get("event_id",""),"liga":f["league"],
            "fecha_utc":f["kickoff"].isoformat(),"local":f["home"],"visitante":f["away"],
            "version":VERSION,"fecha_corte":cutoff.isoformat(),
            "local_datos":_summary(games,f["home"],cutoff),
            "visitante_datos":_summary(games,f["away"],cutoff),
            "enfrentamientos":_h2h(games,f["home"],f["away"],cutoff),
            "calidad":quality(games,f["home"],f["away"],cutoff),
            "xg":{"estado":"NO_DISPONIBLE_EN_CSV","nota":"No se inventa xG. Una fuente dedicada puede aportarlo con fecha y partido verificados."},
            "lesiones":{"estado":"CONTEXTO_EXTERNO_NO_CONFIRMADO","nota":"Las bajas y alineaciones nunca se infieren de los marcadores históricos."}}
