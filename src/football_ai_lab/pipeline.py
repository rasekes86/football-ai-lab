"""Pipeline diario reproducible. No incluye apuestas ni cuotas reales."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timedelta, timezone
import logging
import json
from pathlib import Path
from .core import normalize_team
from .ensemble import predict as ensemble_predict, VERSION as MODEL_VERSION
from .backtest import FIELDS as BACKTEST_FIELDS, run_backtest
from .odds import MARKET_FIELDS, get_optional_quotes, build_market_rows
from .agents import AgentLog
from .sources import LEAGUES, load_history, load_fixtures

LOG = logging.getLogger(__name__)
FIELDS = ["id","fecha_utc","liga","local","visitante","prob_local","prob_empate","prob_visitante",
          "prob_mas_2_5","goles_esperados_local","goles_esperados_visitante","cuota_justa_local",
          "cuota_justa_empate","cuota_justa_visitante","fecha_analisis_utc","modelo",
          "origen_estadisticas","origen_calendario","tipo","prob_elo_local","prob_elo_empate",
          "prob_elo_visitante","peso_elo","diferencia_elo"]
TRACK_FIELDS = ["id","fecha_utc","liga","local","visitante","prob_local","prob_empate","prob_visitante",
                "resultado_local","resultado_visitante","resultado_real","brier_1x2","estado"]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def make_id(f: dict) -> str:
    return "|".join([f["league"], f["kickoff"].strftime("%Y%m%d%H%M"),
                     normalize_team(f["home"]), normalize_team(f["away"])])


def forecast(histories: dict, fixtures: list[dict], now: datetime, mode: str = "REAL") -> tuple[list[dict], list[str]]:
    output, rejected = [], []
    for f in fixtures:
        if f["kickoff"] <= now:
            continue
        p = ensemble_predict(histories.get(f["league"], []), f["home"], f["away"], f["kickoff"].date())
        if p is None:
            rejected.append(f'{f["home"]} - {f["away"]}: historial insuficiente o nombre desconocido')
            continue
        total = sum(p[k] for k in ("home","draw","away"))
        if not 0.999999 < total < 1.000001:
            rejected.append(f'{f["home"]} - {f["away"]}: probabilidades mal normalizadas')
            continue
        output.append({
            "id":make_id(f), "fecha_utc":f["kickoff"].isoformat(), "liga":LEAGUES[f["league"]][0],
            "local":f["home"], "visitante":f["away"],
            "prob_local":f'{p["home"]:.5f}', "prob_empate":f'{p["draw"]:.5f}',
            "prob_visitante":f'{p["away"]:.5f}', "prob_mas_2_5":f'{p["over25"]:.5f}',
            "goles_esperados_local":f'{p["home_lambda"]:.3f}',
            "goles_esperados_visitante":f'{p["away_lambda"]:.3f}',
            "cuota_justa_local":f'{1/p["home"]:.2f}', "cuota_justa_empate":f'{1/p["draw"]:.2f}',
            "cuota_justa_visitante":f'{1/p["away"]:.2f}',
            "fecha_analisis_utc":now.isoformat(), "modelo":MODEL_VERSION,
            "origen_estadisticas":"football-data.co.uk", "origen_calendario":"ESPN (no oficial)",
            "tipo":mode,
            "prob_elo_local":f'{p["elo_home"]:.5f}' if p["elo_home"] is not None else "",
            "prob_elo_empate":f'{p["elo_draw"]:.5f}' if p["elo_draw"] is not None else "",
            "prob_elo_visitante":f'{p["elo_away"]:.5f}' if p["elo_away"] is not None else "",
            "peso_elo":f'{p["weight_elo"]:.2f}',
            "diferencia_elo":f'{p["rating_gap"]:.2f}' if p["rating_gap"] is not None else "",
        })
    return output, rejected


def audit_history(path: Path, predictions: list[dict]) -> list[dict]:
    old = read_csv(path)
    existing = {x["id"] for x in old}
    for p in predictions:
        if p["id"] not in existing:
            old.append(p)
            existing.add(p["id"])
    write_csv(path, FIELDS, old)
    return old


def evaluate(predictions: list[dict], histories: dict) -> list[dict]:
    lookup = {}
    for league, games in histories.items():
        for g in games:
            lookup[(league, g["date"], normalize_team(g["home"]), normalize_team(g["away"]))] = g
    results = []
    for p in predictions:
        league = next((key for key, value in LEAGUES.items() if value[0] == p["liga"]), None)
        if league is None:
            continue
        kickoff = datetime.fromisoformat(p["fecha_utc"]).date()
        match = lookup.get((league, kickoff, normalize_team(p["local"]), normalize_team(p["visitante"])))
        item = {key: p.get(key, "") for key in TRACK_FIELDS}
        if match:
            real = "H" if match["home_goals"] > match["away_goals"] else "D" if match["home_goals"] == match["away_goals"] else "A"
            outcomes = {"H":(1,0,0), "D":(0,1,0), "A":(0,0,1)}
            predicted = [float(p[x]) for x in ("prob_local","prob_empate","prob_visitante")]
            brier = sum((x-y)**2 for x,y in zip(predicted, outcomes[real])) / 3
            item.update({"resultado_local":match["home_goals"],"resultado_visitante":match["away_goals"],
                         "resultado_real":real,"brier_1x2":f"{brier:.5f}","estado":"FINALIZADO"})
        else:
            item.update({"estado":"PENDIENTE"})
        results.append(item)
    return results


def report(now: datetime, predictions: list[dict], rejected: list[str], tracked: list[dict], mode: str,
           metrics: dict | None = None, markets: list[dict] | None = None) -> str:
    completed = [x for x in tracked if x["estado"] == "FINALIZADO"]
    mean_brier = sum(float(x["brier_1x2"]) for x in completed) / len(completed) if completed else None
    lines = ["# Football AI Lab — Informe diario", "",f"**UTC:** {now.isoformat()}",
             f"**Modo:** {mode} — análisis experimental, sin apuesta real",
             f"**Próximos partidos con pronóstico:** {len(predictions)}",
             f"**Descartados por insuficiencia de datos:** {len(rejected)}",
             f"**Históricos evaluados:** {len(completed)}",
             f'**Brier 1X2 medio:** {mean_brier:.4f}' if mean_brier is not None else "**Brier 1X2 medio:** pendiente",
             "", "| Liga | Fecha UTC | Partido | Local | Empate | Visitante |",
             "|---|---|---|---:|---:|---:|"]
    for p in predictions:
        lines.append(f'| {p["liga"]} | {p["fecha_utc"][:16]} | {p["local"]} - {p["visitante"]} | '
                     f'{100*float(p["prob_local"]):.1f}% | {100*float(p["prob_empate"]):.1f}% | '
                     f'{100*float(p["prob_visitante"]):.1f}% |')
    if not predictions:
        lines.append("| — | — | Sin pronósticos: comprobar calendario y nombres | — | — | — |")
    lines.extend(["","## Avisos","",
                  "- No hay cuotas actuales; las cuotas justas son cálculos matemáticos y no precios de mercado.",
                  "- No hay datos de lesiones, xG de eventos o alineaciones.",
                  "- ESPN no garantiza acceso a su endpoint público.",
                  "- El backtest retrospectivo no sustituye una validación prospectiva ni comparaciones con cuotas reales."])
    if metrics is not None:
        lines.extend(["","## Backtesting walk-forward (retrospectivo)","",
                      "Las cifras siguientes son simulaciones históricas. No son pronósticos que existieran antes de aquellos partidos.",
                      "Comparación contra frecuencia histórica móvil de resultados 1X2. Menor Brier y log loss es mejor.","",
                      "| Liga | Muestra | Brier modelo | Brier base | Log loss modelo | Log loss base |",
                      "|---|---:|---:|---:|---:|---:|"])
        for league, m in metrics.items():
            if league.startswith("_"): continue
            lines.append(f'| {league} | {m["muestra"]} | {m["brier_modelo"]} | {m["brier_base"]} | '
                         f'{m["logloss_modelo"]} | {m["logloss_base"]} |')
        if not any(not k.startswith("_") for k in metrics):
            lines.append("| — | 0 | — | — | — | — |")
    if markets is not None:
        live=sum(x["estado"]=="COMPARACIÓN_SIN_VALIDAR" for x in markets)
        lines.extend(["", "## Cuotas externas", "",
                      f"Mercados comparados: **{live}** / {len(markets)}. Las diferencias NO son apuestas recomendadas.",
                      "Sin clave ni autorización explícita, The Odds API queda desactivada (0 peticiones)."])
    if rejected:
        lines.extend(["","## Encuentros descartados",""] + [f"- {x}" for x in rejected[:35]])
    return "\n".join(lines) + "\n"


def demo_data(now: datetime) -> tuple[dict, list[dict]]:
    histories, fixtures = {}, []
    for league in LEAGUES:
        teams = ("Equipo Alfa","Equipo Beta","Equipo Gamma","Equipo Delta") if league == "SP1" else ("Club Uno","Club Dos","Club Tres","Club Cuatro")
        rows = []
        for i in range(80):
            h, a = teams[i%4], teams[(i+1+(i//4)%3)%4]
            if h == a:
                a = teams[(i+1)%4]
            rows.append({"date":now.date()-timedelta(days=180-i*2),
                         "home":h,"away":a,"home_goals":(i*7)%4,"away_goals":(i*5)%3})
        histories[league] = rows
        fixtures.append({"league":league,"kickoff":now+timedelta(days=2),"home":teams[0],"away":teams[1]})
    return histories, fixtures


def main(argv=None) -> None:
    parser=argparse.ArgumentParser(description="Análisis experimental prepartido")
    parser.add_argument("--demo",action="store_true")
    parser.add_argument("--days",type=int,default=14)
    parser.add_argument("--backtest-games",type=int,default=120)
    parser.add_argument("--output",default="output")
    args=parser.parse_args(argv)
    if not 1<=args.days<=31: parser.error("--days entre 1 y 31")
    if not 0<=args.backtest_games<=300: parser.error("--backtest-games entre 0 y 300")
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    now=datetime.now(timezone.utc)
    target=Path("output_demo" if args.demo else args.output)
    book=AgentLog(now)
    if args.demo:
        histories,fixtures=demo_data(now)
    else:
        histories={league:load_history(league,now.date()) for league in LEAGUES}
        if not any(histories.values()):
            raise SystemExit("Sin históricos disponibles; no se sobrescribe el último informe válido")
        fixtures=[f for league in LEAGUES for f in load_fixtures(league,now.date(),args.days)]
    book.mark("datos","OK",f"{len(histories)} ligas; {len(fixtures)} encuentros en {args.days} días",count=sum(map(len,histories.values())))
    book.mark("contexto","NO_CONFIGURADO","No se han consultado alineaciones/lesiones; no se inventan.")
    LOG.info("Partidos encontrados %s; históricos %s",len(fixtures),sum(map(len,histories.values())))
    predicted,rejected=forecast(histories,fixtures,now,"DEMO" if args.demo else "REAL")
    book.mark("predictor","OK",f"Ensemble Poisson 70% / Elo 30%. Descartados: {len(rejected)}",len(predicted))
    # El módulo de cuotas no ejecuta peticiones sin consentimiento expreso y clave.
    events={} if args.demo else get_optional_quotes(list(LEAGUES))
    markets=build_market_rows(predicted,events,now)
    book.mark("mercado","ACTIVO" if events else "DESACTIVADO",
              "Cuotas verificadas (si se activó API)" if events else "Sin API key/ENABLE_ODDS; sin consumo de créditos",
              sum(x["estado"]=="COMPARACIÓN_SIN_VALIDAR" for x in markets))
    back_rows,metrics=run_backtest(histories,LEAGUES,args.backtest_games) if args.backtest_games else ([],{})
    book.mark("auditor","OK" if back_rows else "SIN_MUESTRA",
              "Walk-forward: solo resultados anteriores a cada partido, comparación con baseline",
              len(back_rows))
    write_csv(target/"predicciones.csv",FIELDS,predicted)
    write_csv(target/"mercados.csv",MARKET_FIELDS,markets)
    write_csv(target/"backtest.csv",BACKTEST_FIELDS,back_rows)
    (target/"backtest_resumen.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    past=audit_history(target/"historico_predicciones.csv",predicted)
    tracked=evaluate(past,histories)
    write_csv(target/"seguimiento.csv",TRACK_FIELDS,tracked)
    book.mark("evaluador","OK","Seguimiento prospectivo de predicciones guardadas",len(tracked))
    (target/"informe.md").write_text(report(now,predicted,rejected,tracked,
        "DEMO" if args.demo else "REAL",metrics,markets),encoding="utf-8")
    book.mark("publicador","OK",f"Archivos de salida escritos en {target}")
    (target/"estado_agentes.json").write_text(json.dumps(book.export(),ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Pronósticos: {len(predicted)}, descartados: {len(rejected)}, backtest: {len(back_rows)}")

if __name__ == "__main__":
    main()
