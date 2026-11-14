"""On-demand analysis using a GitHub Issue title as a validated query."""
from __future__ import annotations
import argparse
from datetime import date,datetime,timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .core import normalize_team
from .sources import LEAGUES,load_history,parse_espn_events,http_read,ESPN_URL
from .pipeline import forecast
from .infersports import get_infer_fair
from .live import live_reply

MADRID=ZoneInfo("Europe/Madrid")
PATTERN=re.compile(r"^\[ANALISIS\]\s*(.+?)\s+vs\.?\s+(.+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*$",re.I)

def parse_request(title:str):
    m=PATTERN.match(title.strip())
    if not m:return None
    home,away,day=m.groups()
    if len(home)>100 or len(away)>100:return None
    try: return home.strip(),away.strip(),date.fromisoformat(day)
    except ValueError:return None

def select_match(fixtures,home,away,day):
    return [f for f in fixtures if normalize_team(f["home"])==normalize_team(home)
        and normalize_team(f["away"])==normalize_team(away)
        and f["kickoff"].astimezone(MADRID).date()==day]

def fixtures_on_day(day):
    items=[]
    for league,(_,code) in LEAGUES.items():
        url=ESPN_URL.format(code=code)+"?"+urlencode({"dates":day.strftime("%Y%m%d")})
        try:
            items+=parse_espn_events(http_read(url),league,day)
        except Exception as exc:
            print("Calendario no disponible:",league,type(exc).__name__)
    return items

def reply(title,now=None,fixtures=None,histories=None):
    now=now or datetime.now(timezone.utc)
    request=parse_request(title)
    if request is None:
        return "Formato no reconocido. Usa [ANALISIS] Athletic Club vs Espanyol | 2026-11-20\n"
    home,away,day=request
    diff=(day-now.astimezone(MADRID).date()).days
    if diff<0:return "La fecha ya ha pasado. Solo se hacen análisis prepartido.\n"
    if diff>30:return "Se admiten partidos dentro de los próximos 30 días.\n"
    fixtures=fixtures if fixtures is not None else fixtures_on_day(day)
    chosen=select_match(fixtures,home,away,day)
    if len(chosen)!=1:
        near=[f for f in fixtures if normalize_team(home) in
              (normalize_team(f["home"]),normalize_team(f["away"]))
              or normalize_team(away) in
              (normalize_team(f["home"]),normalize_team(f["away"]))]
        related="\n".join("- "+f["home"]+" vs "+f["away"]+" ("+LEAGUES[f["league"]][0]+")"
                          for f in near[:10])
        return ("No hay una coincidencia única de calendario para ese encuentro. "
                "No se generó ningún pronóstico.\n"+related+"\n")
    f=chosen[0]
    hist=histories if histories is not None else {f["league"]:load_history(f["league"],now.date())}
    predictions,rejected=forecast(hist,[f],now)
    if not predictions:
        return "Partido encontrado, pero sin historial suficiente. "+", ".join(rejected)+"\n"
    p=predictions[0]
    lines=[
        "## Football AI Lab · Análisis bajo demanda",
        f'**{p["local"]} – {p["visitante"]}** · {p["liga"]}',
        f'**Inicio:** {f["kickoff"].astimezone(MADRID).strftime("%d/%m/%Y %H:%M")} (Madrid)',
        f'**Generado:** {now.isoformat()} · modelo {p["modelo"]}',
        "| Resultado | Modelo | Cuota justa matemática |",
        "|---|---:|---:|",
        f'| Local | {float(p["prob_local"])*100:.1f}% | {p["cuota_justa_local"]} |',
        f'| Empate | {float(p["prob_empate"])*100:.1f}% | {p["cuota_justa_empate"]} |',
        f'| Visitante | {float(p["prob_visitante"])*100:.1f}% | {p["cuota_justa_visitante"]} |',
        f'Más de 2,5 goles: {float(p["prob_mas_2_5"])*100:.1f}%.',
        f'Goles estimados: {p["goles_esperados_local"]} y {p["goles_esperados_visitante"]}.',
    ]
    infer=get_infer_fair([p],now).get(p["id"])
    if infer:
        q=infer["fair"]
        lines.extend(["", "### Comparación informativa InferSports",
                      f'Referencia sin margen: {q[0]*100:.1f}% / {q[1]*100:.1f}% / {q[2]*100:.1f}%.',
                      "Fecha de referencia: "+infer["timestamp"]+"."])
    else:
        lines.append("InferSports: sin referencia reciente y verificable.")
    lines.append("**No es una recomendación de apuesta.** No incluye lesiones o alineaciones confirmadas. "
                 "Las probabilidades del modelo no demuestran rentabilidad.")
    return "\n\n".join(lines)+"\n"

def main(argv=None):
    pa=argparse.ArgumentParser()
    pa.add_argument("--event-path",required=True)
    pa.add_argument("--out",required=True)
    a=pa.parse_args(argv)
    issue=json.loads(Path(a.event_path).read_text(encoding="utf-8")).get("issue") or {}
    title=str(issue.get("title",""))
    result=live_reply(title) if title.startswith("[DIRECTO]") else reply(title)
    Path(a.out).write_text(result,encoding="utf-8")
    print(result[:500])

if __name__=="__main__":
    main()
