"""Control de cobertura real para poder diseñar futuros modelos individuales.

No predice disparos/goles/tarjetas de jugadores. Separa titularidad confirmada
de simple convocatoria, minutos ausentes y muestras insuficientes.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime,timezone

VERSION="players-readiness-0.8"
def report(data:dict,now:datetime)->dict:
    samples=data.get("registros") or []
    groups=defaultdict(list)
    for p in samples:
        # Exclude bench players if their actual appearance was not confirmed.
        if p.get("participacion_confirmada") is not True:continue
        key=(str(p.get("jugador_id","")),str(p.get("equipo","")))
        if not all(key):continue
        groups[key].append(p)
    details=[]
    for (pid,team),rows in groups.items():
        distinct={r["event_id"]:r for r in rows if r.get("event_id")}
        rows=list(distinct.values())
        if not rows:continue
        latest=max(r["fecha_utc"] for r in rows)
        with_minutes=sum(any(k in r.get("estadisticas",{}) for k in
                           ("minutes","minutesPlayed")) for r in rows)
        with_shots=sum(any(k in r.get("estadisticas",{}) for k in
                           ("shots","totalShots")) for r in rows)
        with_target=sum(any(k in r.get("estadisticas",{}) for k in
                           ("shotsOnTarget","shotsOnGoal")) for r in rows)
        n=len(rows)
        coverage=with_shots/n
        mins=with_minutes/n
        details.append({"jugador_id":pid,"jugador":rows[0].get("jugador",""),
                        "equipo":team,"apariciones_confirmadas":n,
                        "partidos_con_tiros":with_shots,"partidos_con_tiros_puerta":with_target,
                        "partidos_con_minutos":with_minutes,
                        "cobertura_tiros":round(coverage,3),
                        "cobertura_minutos":round(mins,3),
                        "ultimo_partido":latest,
                        "muestra_minima_para_investigar":n>=12 and coverage>=.8 and mins>=.7})
    details.sort(key=lambda x:(-x["apariciones_confirmadas"],x["equipo"],x["jugador"]))
    enough=[x for x in details if x["muestra_minima_para_investigar"]]
    return {"version":VERSION,"fecha_utc":now.isoformat(),
            "eventos_distintos":len({p.get("event_id") for p in samples if p.get("event_id")}),
            "registros_totales":len(samples),
            "participaciones_confirmadas":sum(x["apariciones_confirmadas"] for x in details),
            "jugadores_diferentes":len(details),
            "jugadores_con_muestra_inicial":len(enough),
            "jugadores":details[:100],
            "estado":"COBERTURA_INICIAL" if samples else "SIN_HISTORICO",
            "advertencia":"La muestra suficiente permite investigar, NO activar un predictor de jugadores. "
                           "Faltan modelos causales, minutos previstos, contexto de alineaciones "
                           "y validación retrospectiva y prospectiva de cada mercado."}
