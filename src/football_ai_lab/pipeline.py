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
from .infersports import get_infer_fair, merge_infer_prices
from .agents import AgentLog
from .context_machina import collect as machina_context
from .context_xg import collect as historic_xg
from .match_context import dossier as match_dossier
from .prospective import evaluate as prospective_evaluate
from .prospective import summarize as prospective_summary
from .prospective import TRACK_FIELDS as PROSPECTIVE_FIELDS
from .selector import select_match as select_markets, global_top as global_market_top
from .selector import flat_rows as market_flat_rows, FIELDS as SELECTOR_FIELDS
from .count_validation import validate as validate_counts, VERSION as COUNT_VALIDATION_VERSION
from .market_prospective import archive as archive_selections, settle as settle_selections
from .market_prospective import summary as selections_summary, FIELDS as MARKET_PROSPECTIVE_FIELDS
from .full_report import build_all as all_dossiers, markdown as dossier_markdown
from .player_data import collect as collect_players
from .player_readiness import report as player_coverage
from .value_watchlist import freeze as freeze_offers, evaluate as evaluate_offers
from .value_watchlist import selection_audit as audit_offer_selection
from .value_watchlist import markdown as offers_markdown, FIELDS as OFFER_FIELDS
from .sources import LEAGUES, load_history, load_fixtures
from .verified_results import augment_results
from .postmatch_stats import enrich_statistics
from .postmatch_breakdown import build_breakdown
from .market_history import build_market_history
from .radar_context import build_radar_context
from .real_odds import build_real_odds
import os
from .future_market_audit import (
    FIELDS as FUTURE_AUDIT_FIELDS, archive_future_markets,
    settle_future_markets, audit_future_markets,
)

LOG = logging.getLogger(__name__)
FIELDS = ["id","fecha_utc","liga","local","visitante","prob_local","prob_empate","prob_visitante",
          "prob_mas_2_5","goles_esperados_local","goles_esperados_visitante","cuota_justa_local",
          "cuota_justa_empate","cuota_justa_visitante","fecha_analisis_utc","modelo",
          "origen_estadisticas","origen_calendario","tipo","prob_elo_local","prob_elo_empate",
          "prob_elo_visitante","peso_elo","diferencia_elo"]
TRACK_FIELDS = PROSPECTIVE_FIELDS


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


def evaluate(predictions: list[dict], histories: dict, now: datetime | None = None) -> list[dict]:
    """Compatibilidad con versiones anteriores: mismo auditor prospectivo."""
    return prospective_evaluate(predictions,histories,now or datetime.now(timezone.utc))


def report(now: datetime, predictions: list[dict], rejected: list[str], tracked: list[dict], mode: str,
           metrics: dict | None = None, markets: list[dict] | None = None,
           prospective: dict | None = None) -> str:
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
        live=sum(x["estado"] in ("COMPARACIÓN_SIN_VALIDAR","REFERENCIA_INFERSPORTS_SIN_VALIDAR") for x in markets)
        lines.extend(["", "## Cuotas externas", "",
                      f"Mercados comparados: **{live}** / {len(markets)}. Las diferencias NO son apuestas recomendadas.",
                      "The Odds API se desactiva sin clave y autorización. InferSports usa el acceso sin clave, máximo 3 consultas por ejecución; los precios teóricos no son ofertas de casas."])
    if prospective is not None:
        lines.extend(["","## Seguimiento prospectivo real","",
              f'Pronósticos archivados: **{prospective["registrados"]}**',
              f'Resultados reales verificados: **{prospective["finalizados_validos"]}**',
              f'Sin resultado en la fuente: **{prospective["sin_resultado"]}**',
              f'Excluidos por calidad/temporalidad: **{prospective["excluidos"]}**',
              "Este apartado no incluye los backtests retrospectivos."])
        if prospective["global"]["muestra"]:
            g=prospective["global"]
            lines.append(f'Brier prospectivo: **{g["brier_medio"]}**; log loss: **{g["logloss_medio"]}**. '
                         f'Acierto del favorito: **{g["acierto_favorito_pct"]}%**.')
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
    # Un segundo histórico solo para liquidar resultados ya archivados; evita
    # contaminar el entrenamiento, las predicciones y el backtesting.
    settlement_histories=histories
    stats_check={"objetivos_conteo":0,"completos":0,"incompletos":0}
    stats_payload={"version":"postmatch-stats-1.0","partidos":[]}
    if not args.demo:
        past_snapshots=(read_csv(target/"historico_predicciones.csv")
            +read_csv(target/"historico_selecciones.csv")
            +read_csv(target/"historico_oportunidades_150.csv")
            +read_csv(target/"historico_mercados_futuros.csv"))
        settlement_histories,check=augment_results(histories,past_snapshots,now)
        book.mark("marcadores_finales","OK" if not check["sin_marcador"] else "PARCIAL",
                  f'Oficiales: {check["agregados_laliga"]}; ESPN: {check["agregados_espn"]}; '
                  f'sin marcador: {check["sin_marcador"]}',check["objetivos"])
        settlement_histories,stats_check,stats_payload=enrich_statistics(
            settlement_histories,past_snapshots,now,
            cache_path=target/"estadisticas_finales_verificadas.json")
        book.mark("estadisticas_finales",
                  "OK" if not stats_check["incompletos"] else "PARCIAL",
                  f'Conteos: {stats_check["completos"]}/{stats_check["objetivos_conteo"]} '
                  f'partidos completos; campos ESPN: {stats_check["campos_recuperados"]}',
                  stats_check["objetivos_conteo"])
    context=machina_context(now) if not args.demo else {"estado":"DEMO","timestamp_utc":now.isoformat()}
    book.mark("contexto",context["estado"],
              f"Machina Sports: {len(context.get('clasificaciones',{}))} ligas; lesiones sólo Premier si disponibles")
    target.mkdir(parents=True,exist_ok=True)
    (target/"estadisticas_finales_verificadas.json").write_text(
        json.dumps(stats_payload,ensure_ascii=False,indent=2),encoding="utf-8")
    # Explorador: histórico OBSERVACIONAL ya disputado, independiente de Poisson/Elo.
    market_history=build_market_history(settlement_histories,now,days=365)
    (target/"mercados_historicos.json").write_text(
        json.dumps(market_history,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    (target/"contexto_machina.json").write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding="utf-8")
    # Optional bounded historical player sample. Never derive player picks from sparse data.
    prior_players_path=target/"jugadores_historico.json"
    prior_players={}
    if prior_players_path.exists():
        try:
            prior_players=json.loads(prior_players_path.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            prior_players={}
    player_data=collect_players(now,existing=prior_players) if not args.demo else {
        "estado":"DEMO","registros":[],"eventos_consultados":0,"jugadores_con_algun_dato":0}
    prior_players_path.write_text(json.dumps(player_data,ensure_ascii=False,indent=2),encoding="utf-8")
    readiness=player_coverage(player_data,now)
    (target/"cobertura_jugadores.json").write_text(
        json.dumps(readiness,ensure_ascii=False,indent=2),encoding="utf-8")
    book.mark("jugadores",player_data.get("estado","SIN_DATOS"),
              f'{len(player_data.get("registros",[]))} registros; '
              f'{readiness["participaciones_confirmadas"]} participaciones verificadas; '
              'sin apuestas individuales')
    # Genuine historical xG sample only; not an estimated metric.
    xg_snapshot=historic_xg(now) if not args.demo else {"estado":"DEMO","partidos":[],"consultas_xg":0}
    (target/"contexto_xg.json").write_text(json.dumps(xg_snapshot,ensure_ascii=False,indent=2),encoding="utf-8")
    LOG.info("xG verificable en %s partidos previos; estado %s",
             len(xg_snapshot.get("partidos",[])),xg_snapshot["estado"])
    LOG.info("Partidos encontrados %s; históricos %s",len(fixtures),sum(map(len,histories.values())))
    # Informes causales: no alteran el modelo estadístico existente.
    dossiers=[match_dossier(histories.get(f["league"],[]),f) for f in fixtures]
    coverage={"publicados":0,"rechazados":0,
              "identificacion_insuficiente":sum(
                  bool(d["calidad"]["motivos"]) for d in dossiers)}
    (target/"contexto_partidos.json").write_text(
        json.dumps({"calculado_utc":now.isoformat(),"partidos":dossiers,
                    "nota":"Métricas de partidos anteriores exclusivamente; sin inventar xG."},
                    ensure_ascii=False,indent=2),encoding="utf-8")
    predicted,rejected=forecast(histories,fixtures,now,"DEMO" if args.demo else "REAL")
    book.mark("predictor","OK",f"Ensemble Poisson 70% / Elo 30%. Descartados: {len(rejected)}",len(predicted))
    # El módulo de cuotas no ejecuta peticiones sin consentimiento expreso y clave.
    events={} if args.demo else get_optional_quotes(list(LEAGUES))
    markets=build_market_rows(predicted,events,now)
    infer=get_infer_fair(predicted,now) if not args.demo else {}
    markets=merge_infer_prices(markets,infer,predicted)
    # Walk-forward on prior matches: never promote count markets without a pass.
    count_validation=validate_counts(histories,now,max_games=180)
    (target/"validacion_conteos.json").write_text(
        json.dumps(count_validation,ensure_ascii=False,indent=2),encoding="utf-8")
    LOG.info("Líneas de conteos aprobadas retrospectivamente: %d",
             len(count_validation["aprobados"]))
    # Picks are experimental and informational; no betting execution.
    league_lookup={label[0]:code for code,label in LEAGUES.items()}
    selections=[]
    for prediction in predicted:
        code=league_lookup.get(prediction["liga"])
        if code is None:continue
        try:
            selections.append(select_markets(prediction,histories.get(code,[]),markets,now,
                                             validation=count_validation))
        except (ValueError,TypeError,KeyError) as exc:
            LOG.warning("Selector descartó %s: %s",prediction["id"],type(exc).__name__)
    # Export ligero para consultar PRONÓSTICOS FUTUROS por categoría.
    # No se archivan ni se liquidan estas líneas extra: solo el Top 3 original.
    previews=[{
        "id":m["id"],"fecha_utc":m["fecha_utc"],"liga":m["liga"],
        "local":m["local"],"visitante":m["visitante"],
        "calculado_utc":m["calculado_utc"],
        "mercados":m.get("_pronosticos_mercados",{}),
    } for m in selections]
    # FASE 8 — cuotas REALES y comparador opt-in. Se ejecuta DESPUÉS
    # de los pronósticos, nunca modifica los modelos ni los snapshots.
    previous_real_odds={}
    state_file=target/"estado_consultas_cuotas.json"
    prior_quotes_file=target/"cuotas_reales_verificadas.json"
    previous_odds_state={}
    prior_quotes={}
    if state_file.is_file():
        try:
            previous_odds_state=json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            previous_odds_state={}
    if prior_quotes_file.is_file():
        try:
            prior_quotes=json.loads(prior_quotes_file.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            prior_quotes={}
    # Las adicionales congeladas no se recotizan en ninguna ejecución.
    archived_extras=read_csv(target/"historico_oportunidades_150.csv")
    excluded_ids={row["id"] for row in archived_extras if row.get("id")}
    real_history_file=target/"historico_cuotas_reales.json"
    if real_history_file.is_file():
        try:
            previous_real_odds=json.loads(real_history_file.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            previous_real_odds={}
    real_quotes,real_compared,real_history=build_real_odds(
        previews,now,existing=previous_real_odds,
        env={} if args.demo else os.environ,state=previous_odds_state,
        prior_quotes=prior_quotes,excluded_ids=excluded_ids)
    current_odds_state=real_quotes.pop("estado_consultas",previous_odds_state)
    state_file.write_text(
        json.dumps(current_odds_state,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    (target/"cuotas_reales_verificadas.json").write_text(
        json.dumps(real_quotes,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    (target/"comparacion_cuotas_reales.json").write_text(
        json.dumps(real_compared,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    real_history_file.write_text(
        json.dumps(real_history,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    book.mark("cuotas_reales",real_quotes["estado"],
        f'Proveedor opt-in: {real_quotes["auditoria"]["ligas_respondidas"]}; '
        f'{real_compared["auditoria"]["precios_comparados"]} comparaciones verificadas. '
        'Sin clave no se fabrican precios.',real_quotes["auditoria"]["cuotas_validadas"])
    # Radar: solo histórico original ANTERIOR al partido, separado
    # del enriquecimiento postpartido y de las selecciones archivadas.
    radar_context = build_radar_context(histories, previews, now)
    (target/"radar_contexto_equipos.json").write_text(
        json.dumps(radar_context,ensure_ascii=False,separators=(",",":")),
        encoding="utf-8")
    (target/"pronosticos_mercados_futuros.json").write_text(json.dumps({
        "version":"future-markets-1.0","calculado_utc":now.isoformat(),
        "partidos":previews,
        "nota":("Estas son estimaciones prepartido experimentales y NO apuestas ofrecidas. "
                "Todas las líneas visibles se congelan en un seguimiento prospectivo "
                "SEPARADO del Top 3. La evaluación solo empieza tras archivarlas. "
                "Los conteos no calibrados prospectivamente se identifican. "
                "No existe modelo prepartido de faltas o tarjetas rojas."),
    },ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    # FASE 4: primer snapshot por partido antes del inicio.
    # Archivo distinto del histórico Top 3 y sin reconstrucción de partidos pasados.
    prior_future=read_csv(target/"historico_mercados_futuros.csv")
    frozen_future,freeze_report=archive_future_markets(prior_future,previews,now)
    write_csv(target/"historico_mercados_futuros.csv",
              FUTURE_AUDIT_FIELDS,frozen_future)
    tracked_future=settle_future_markets(frozen_future,settlement_histories,now)
    write_csv(target/"seguimiento_mercados_futuros.csv",
              FUTURE_AUDIT_FIELDS,tracked_future)
    future_audit=audit_future_markets(tracked_future,now)
    future_audit["registro_nuevo"]=freeze_report
    (target/"fiabilidad_mercados_futuros.json").write_text(
        json.dumps(future_audit,ensure_ascii=False,separators=(",",":")),
        encoding="utf-8")
    book.mark("auditoria_mercados_futuros","OK",
              f'Archivo propio: {freeze_report["nuevos"]} nuevas líneas, '
              f'{future_audit["finalizadas"]}/{future_audit["registradas"]} '
              'evaluadas; no modifica el Top 3 original',
              future_audit["registradas"])
    top_jornada=global_market_top(selections)
    # No crecer el JSON legado con un dataset que tiene su propia ruta pública.
    public_selections=[{key:value for key,value in m.items()
                        if key!="_pronosticos_mercados"} for m in selections]
    (target/"selecciones.json").write_text(
        json.dumps({"version":"market-selector-0.7","calculado_utc":now.isoformat(),
                    "lineas_conteos_aprobadas_retro":count_validation["aprobados"],
                    "top_3_jornada":top_jornada,"partidos":public_selections,
                    "nota":"Ranking por probabilidad, con filtro de cuota justa mínima y una familia por partido. No son recomendaciones de apuestas."},
                    ensure_ascii=False,indent=2),encoding="utf-8")
    write_csv(target/"selecciones.csv",SELECTOR_FIELDS,market_flat_rows(selections))
    # Immutable prospective picks: first eligible selection of each match only.
    previous_selections=read_csv(target/"historico_selecciones.csv")
    selections_frozen=archive_selections(previous_selections,selections,now)
    write_csv(target/"historico_selecciones.csv",MARKET_PROSPECTIVE_FIELDS,selections_frozen)
    tracked_selections=settle_selections(selections_frozen,settlement_histories,now)
    write_csv(target/"seguimiento_selecciones.csv",MARKET_PROSPECTIVE_FIELDS,tracked_selections)
    market_evaluation=selections_summary(tracked_selections,now)
    detail=build_breakdown(tracked_selections,settlement_histories,now,stats_check)
    (target/"desglose_postpartido.json").write_text(
        json.dumps(detail,ensure_ascii=False,indent=2),encoding="utf-8")
    (target/"evaluacion_selecciones.json").write_text(
        json.dumps(market_evaluation,ensure_ascii=False,indent=2),encoding="utf-8")
    # Secondary 3+1 track: real bookmaker prices were captured and compared
    # above during this SAME authorized run. Freeze a single eligible additional
    # per fixture before kickoff; the immutable original Top 3 stays untouched.
    # Historical manual odds remain INDICATIVA_NO_VERIFICADA, never promoted
    # after the match. No bets are placed; ROI is purely hypothetical.
    offer_source=Path("data/watchlist_cuotas_orientativas.json")
    if offer_source.is_file() and not args.demo:
        try:
            manual_offers=json.loads(offer_source.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            LOG.warning("Muestra manual de cuotas no disponible o con JSON inválido")
            manual_offers={"selecciones":[]}
    else:
        manual_offers={"selecciones":[]}
    previous_offers=read_csv(target/"historico_oportunidades_150.csv")
    frozen_offers=freeze_offers(
        previous_offers,manual_offers,selections,now,
        comparisons=real_compared,top3=selections_frozen)
    write_csv(target/"historico_oportunidades_150.csv",OFFER_FIELDS,frozen_offers)
    tracked_offers,offer_evaluation=evaluate_offers(frozen_offers,settlement_histories,now)
    # The public 3+1 panel can now show WHY some fixtures have no automatic
    # additional pick. No speculative odds are created when feeds are absent.
    offer_evaluation["seleccion_automatica"]=audit_offer_selection(
        previous_offers,frozen_offers,selections,real_compared,now,selections_frozen)
    write_csv(target/"seguimiento_oportunidades_150.csv",OFFER_FIELDS,tracked_offers)
    (target/"evaluacion_oportunidades_150.json").write_text(
        json.dumps(offer_evaluation,ensure_ascii=False,indent=2),encoding="utf-8")
    (target/"oportunidades_150.md").write_text(
        offers_markdown(tracked_offers,offer_evaluation),encoding="utf-8")
    book.mark("oportunidades_150","OK",
              f'{offer_evaluation["registradas"]} cotizaciones archivadas; '
              f'{offer_evaluation["finalizadas"]} mercados liquidados; '
              f'API prepartido: {offer_evaluation["verificacion"]["cuotas_api_observadas_antes_del_partido"]}; '
              f'referencias indicativas: {offer_evaluation["verificacion"]["cuotas_indicativas_no_acreditadas"]}; '
              f'nuevas adicionales de API: {offer_evaluation["seleccion_automatica"]["nuevas_automaticas"]}; '
              f'sin opcion valida: {offer_evaluation["seleccion_automatica"]["abstenciones_sin_opcion_valida"]}',len(frozen_offers))
    # Unified reports are built exclusively from verified source records.
    ml_rows=read_csv(Path("output_ml/predicciones_ml.csv")) if not args.demo else []
    complete_reports=all_dossiers(predicted,dossiers,selections,context,ml_rows,markets,now)
    (target/"informes_partidos.json").write_text(
        json.dumps({"version":"dossier-0.8","calculado_utc":now.isoformat(),
                    "partidos":complete_reports,"aviso":"Investigación experimental sin apostar"},
                    ensure_ascii=False,indent=2),encoding="utf-8")
    (target/"informes_partidos.md").write_text(
        "# Football AI Lab — dossiers completos de la jornada\n\n"+
        "\n\n---\n\n".join(dossier_markdown(item) for item in complete_reports)+"\n",
        encoding="utf-8")

    book.mark("selector","OK",
              f'{len(selections)} partidos; {len(count_validation["aprobados"])} líneas de conteos aptas retrospectivamente; jugadores no habilitados',
              len(market_flat_rows(selections)))
    found=sum(x["estado"] in ("COMPARACIÓN_SIN_VALIDAR","REFERENCIA_INFERSPORTS_SIN_VALIDAR") for x in markets)
    book.mark("mercado","REFERENCIAS" if found else "SIN_REFERENCIAS",
              f"InferSports keyless: {len(infer)} coincidencias (máximo tres consultas); The Odds API: {'activo' if events else 'sin clave'}",
              found)
    back_rows,metrics=run_backtest(histories,LEAGUES,args.backtest_games) if args.backtest_games else ([],{})
    book.mark("auditor","OK" if back_rows else "SIN_MUESTRA",
              "Walk-forward: solo resultados anteriores a cada partido, comparación con baseline",
              len(back_rows))
    write_csv(target/"predicciones.csv",FIELDS,predicted)
    write_csv(target/"mercados.csv",MARKET_FIELDS,markets)
    write_csv(target/"backtest.csv",BACKTEST_FIELDS,back_rows)
    (target/"backtest_resumen.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    past=audit_history(target/"historico_predicciones.csv",predicted)
    tracked=evaluate(past,settlement_histories,now)
    prospective=prospective_summary(tracked,now)
    write_csv(target/"seguimiento.csv",TRACK_FIELDS,tracked)
    (target/"evaluacion_real.json").write_text(
        json.dumps(prospective,ensure_ascii=False,indent=2),encoding="utf-8")
    book.mark("evaluador","OK",
              f'{prospective["finalizados_validos"]} finales verificados, {prospective["pendientes"]} pendientes',
              len(tracked))
    book.mark("mercados_prospectivos","OK",
              f'{market_evaluation["finalizadas"]} selecciones terminadas, '
              f'{market_evaluation["pendientes"]} pendientes; '
              'no confundir con backtest',len(selections_frozen))
    # Añadimos un resumen de las selecciones sin afirmar certeza de éxito.
    selector_lines=["","## Selector de mercados · probabilidades experimentales","",
                    "Top 3 de la próxima jornada: una selección por partido; "
                    "no hay correlación ni rentabilidad garantizada.","",
                    "| Partido | Mercado | Selección | Prob. modelo | Cuota justa |",
                    "|---|---|---|---:|---:|"]
    for entry in top_jornada:
        selector_lines.append(f'| {entry["local"]} – {entry["visitante"]} | '
                              f'{entry["mercado"]} | {entry["seleccion"]} | '
                              f'{entry["probabilidad"]*100:.1f}% | {entry["cuota_justa"]:.2f} |')
    if not top_jornada:
        selector_lines.append("| — | — | Sin selecciones elegibles | — | — |")
    selector_lines.extend(["",
        "## Seguimiento de cuotas superiores a 1,50 (separado del Top 3)","",
        f'Selecciones archivadas: **{offer_evaluation["registradas"]}**; '
        f'finalizadas: **{offer_evaluation["finalizadas"]}**; '
        f'pendientes: **{offer_evaluation["pendientes"]}**.',
        "Véase output/oportunidades_150.md para los resultados por partido. "
        "Precios conversacionales NO verificados; retornos solo simulados.",
    ])
    selector_lines.extend(["",
                           f'Seguimiento real del Top 3: **{market_evaluation["registradas"]}** selecciones '
                           f'archivadas antes del partido; **{market_evaluation["finalizadas"]}** resueltas.',
                           'Informe completo de cada encuentro: output/informes_partidos.md.',
                           f'Líneas de córners/tiros/tarjetas aprobadas en backtest: **{len(count_validation["aprobados"])}**. '
                           "Solo las aprobadas retrospectivamente pueden competir por el Top 3; "
                           "no tienen validación prospectiva.",
                           f'Seguimiento futuro por mercados (FASE 4): '
                           f'{future_audit["registradas"]} líneas congeladas, '
                           f'{future_audit["finalizadas"]} evaluadas, '
                           'independiente del Top 3.',
                           "Cuotas justas = valores matemáticos, NO precios ofrecidos.",
                           "Tiros y goleadores individuales no disponibles.",
                           "Ranking de valor vacío sin cuotas reales verificadas por mercado."])
    (target/"informe.md").write_text(report(now,predicted,rejected,tracked,
        "DEMO" if args.demo else "REAL",metrics,markets,prospective)
        +"\n".join(selector_lines)+"\n",encoding="utf-8")
    book.mark("publicador","OK",f"Archivos de salida escritos en {target}")
    (target/"estado_agentes.json").write_text(json.dumps(book.export(),ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Pronósticos: {len(predicted)}, descartados: {len(rejected)}, backtest: {len(back_rows)}")

if __name__ == "__main__":
    main()
