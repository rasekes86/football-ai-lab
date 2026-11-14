"""Pipeline diario reproducible. No incluye apuestas ni cuotas reales."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from .core import MODEL_VERSION, estimate_goals, normalize_team, probabilities
from .sources import LEAGUES, load_history, load_fixtures

LOG = logging.getLogger(__name__)
FIELDS = ["id","fecha_utc","liga","local","visitante","prob_local","prob_empate","prob_visitante",
          "prob_mas_2_5","goles_esperados_local","goles_esperados_visitante","cuota_justa_local",
          "cuota_justa_empate","cuota_justa_visitante","fecha_analisis_utc","modelo",
          "origen_estadisticas","origen_calendario","tipo"]
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
        lams = estimate_goals(histories.get(f["league"], []), f["home"], f["away"], f["kickoff"].date())
        if lams is None:
            rejected.append(f'{f["home"]} - {f["away"]}: historial insuficiente o nombre desconocido')
            continue
        p = probabilities(*lams)
        output.append({
            "id":make_id(f), "fecha_utc":f["kickoff"].isoformat(), "liga":LEAGUES[f["league"]][0],
            "local":f["home"], "visitante":f["away"],
            "prob_local":f'{p["home"]:.5f}', "prob_empate":f'{p["draw"]:.5f}',
            "prob_visitante":f'{p["away"]:.5f}', "prob_mas_2_5":f'{p["over25"]:.5f}',
            "goles_esperados_local":f"{lams[0]:.3f}", "goles_esperados_visitante":f"{lams[1]:.3f}",
            "cuota_justa_local":f'{1/p["home"]:.2f}', "cuota_justa_empate":f'{1/p["draw"]:.2f}',
            "cuota_justa_visitante":f'{1/p["away"]:.2f}',
            "fecha_analisis_utc":now.isoformat(), "modelo":MODEL_VERSION,
            "origen_estadisticas":"football-data.co.uk", "origen_calendario":"ESPN (no oficial)",
            "tipo":mode
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


def report(now: datetime, predictions: list[dict], rejected: list[str], tracked: list[dict], mode: str) -> str:
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
                  "- Este modelo aún no ha superado un backtest independiente."])
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--output", default="output")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    now = datetime.now(timezone.utc)
    target = Path("output_demo" if args.demo else args.output)
    if args.demo:
        histories, fixtures = demo_data(now)
    else:
        histories = {league: load_history(league, now.date()) for league in LEAGUES}
        fixtures = [f for league in LEAGUES for f in load_fixtures(league, now.date(), args.days)]
    LOG.info("Partidos encontrados %s; históricos %s", len(fixtures), sum(map(len,histories.values())))
    predicted, rejected = forecast(histories, fixtures, now, "DEMO" if args.demo else "REAL")
    write_csv(target / "predicciones.csv", FIELDS, predicted)
    past = audit_history(target / "historico_predicciones.csv", predicted)
    tracked = evaluate(past, histories)
    write_csv(target / "seguimiento.csv", TRACK_FIELDS, tracked)
    (target / "informe.md").write_text(report(now, predicted, rejected, tracked,
                                              "DEMO" if args.demo else "REAL"), encoding="utf-8")
    print("Pronósticos:", len(predicted), "Descartados:", len(rejected))
    if not args.demo and not any(histories.values()):
        raise SystemExit("Sin históricos disponibles; no se publica salida como válida")

if __name__ == "__main__":
    main()
