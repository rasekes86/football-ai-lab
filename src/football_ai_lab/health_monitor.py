"""Monitor de salud de Football AI Lab sin APIs de cuotas adicionales.

Lee artefactos públicos ya publicados y avisa al chat privado por Telegram.
Estado sin secretos; solo notifica cambios, no cada ejecución.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from .telegram_notify import send

DAILY_LIMIT = timedelta(hours=36)
ODDS_LIMIT = timedelta(hours=9)
EARLY_SETTLEMENT_GRACE = timedelta(hours=10)
SETTLEMENT_GRACE = timedelta(hours=48)
MIN_CALENDAR_ERRORS = 2
MIN_CALENDAR_ROUNDS = 2
STALE_ODDS_DAYS = 5
STATE_FILENAME = "estado_salud.json"

def _dt(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None

def _json(path):
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}

def _csv(path):
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))
    except (OSError, ValueError, csv.Error):
        return []

def _flag(value, default=True):
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in ("1", "yes", "true", "on")

def _issue(code, severity, message):
    return {"codigo": code, "severidad": severity, "descripcion": message}

def assess(target, now, previous=None, *, odds_enabled=True,
           source_workflow="", source_conclusion=""):
    """Evaluate deterministic, non-financial monitoring signals.

    A missing price or a losing pick is NOT an error. Several predictions
    from the same fixture count as ONE fixture in delayed settlement checks.
    Calendar errors must recur in two DISTINCT odds snapshots.
    """
    now = now.astimezone(timezone.utc)
    previous = previous if isinstance(previous, dict) else {}
    forecast = _json(target / "pronosticos_mercados_futuros.json")
    track = _json(target / "evaluacion_selecciones.json")
    odds = _json(target / "cuotas_reales_verificadas.json")
    ledger = _json(target / "estado_consultas_cuotas.json")
    picks = (_csv(target / "seguimiento_selecciones.csv")
             + _csv(target / "seguimiento_oportunidades_150.csv"))
    issues = []
    detail = {}

    forecast_time = _dt(forecast.get("calculado_utc"))
    evaluation_time = _dt(track.get("calculado_utc"))
    newest_daily = min(forecast_time, evaluation_time) if forecast_time and evaluation_time else None
    if newest_daily is None or newest_daily > now + timedelta(minutes=5) or now - newest_daily > DAILY_LIMIT:
        issues.append(_issue("ANALISIS_CADUCADO", "ALTA",
            "El análisis o su evaluación están ausentes o tienen más de 36 horas."))
    detail["analisis_utc"] = newest_daily.isoformat() if newest_daily else None

    future = forecast.get("partidos") if isinstance(forecast.get("partidos"), list) else []
    relevant = [m for m in future if isinstance(m, dict)
                and (kick := _dt(m.get("fecha_utc")))
                and now < kick <= now + timedelta(days=STALE_ODDS_DAYS)]
    detail["partidos_proximos"] = len(relevant)

    capture = _dt(odds.get("capturado_utc"))
    odds_run = _dt(ledger.get("actualizado_utc"))
    provider = next((x for x in odds.get("auditoria", {}).get("fuentes_gratuitas", [])
                     if isinstance(x, dict) and x.get("proveedor") == "5DollarFootballAPI"), {})
    detail["cuotas_utc"] = capture.isoformat() if capture else None
    detail["consultas_utc"] = odds_run.isoformat() if odds_run else None
    if odds_enabled and relevant:
        # An updated ledger is not proof of a fresh bookmaker snapshot.
        if capture is None or capture > now + timedelta(minutes=5) or now - capture > ODDS_LIMIT:
            issues.append(_issue("CUOTAS_SIN_ACTUALIZAR", "ALTA",
                "Hay partidos próximos, pero el refresco de cuotas lleva más de 9 horas sin actualizarse."))
        if provider.get("estado") in ("SIN_CLAVE", "DESACTIVADO"):
            issues.append(_issue("PROVEEDOR_NO_ACTIVO", "ALTA",
                "El proveedor de cuotas consta como desactivado o sin clave pese a estar habilitado."))
    # An issue in ONE round may be a transient provider failure. Two NEW
    # failed snapshots in a row trigger the alert. Re-reading the same
    # snapshot (e.g. by the four-hour scheduler) never increments the streak.
    previous_capture = str(previous.get("ultima_captura_revisada") or "")
    marker = capture.isoformat() if capture else ""
    streak = max(0, min(50, int(previous.get("racha_calendario") or 0)))
    errors = provider.get("errores_por_fase") or {}
    calendar_errors = int(errors.get("calendario") or 0)
    detail["errores_calendario_ultima_ronda"] = calendar_errors
    provider_errors = int(provider.get("errores") or 0)
    detail["errores_totales_proveedor_ultima_ronda"] = provider_errors
    generic_streak = max(0, min(50, int(previous.get("racha_proveedor") or 0)))
    if odds_enabled and marker and marker != previous_capture:
        generic_streak = generic_streak + 1 if provider_errors >= 2 else 0
    if odds_enabled and marker and marker != previous_capture:
        streak = streak + 1 if calendar_errors >= MIN_CALENDAR_ERRORS else 0
    if odds_enabled and streak >= MIN_CALENDAR_ROUNDS:
        issues.append(_issue("CALENDARIO_ERRORES_REPETIDOS", "ALTA",
            "Dos rondas distintas presentan al menos 2 errores de calendario cada una. "
            "Revisar la API y las ventanas de consulta."))
    if odds_enabled and generic_streak >= 2 and streak < 2:
        issues.append(_issue("PROVEEDOR_ERRORES_REPETIDOS", "ALTA",
            "Dos rondas de cuotas consecutivas han registrado al menos "
            "2 errores del proveedor. Revisar cuotas, liga y/o calendario."))
    if not odds_enabled:
        streak = 0
        generic_streak = 0
    detail["racha_calendario"] = streak
    detail["racha_proveedor"] = generic_streak

    # Contar partidos distintos, no las cuatro selecciones del mismo partido.
    # Una ronda nocturna omitida requiere aviso antes de las 48 horas.
    # Estadisticas ausentes no equivalen a pronosticos fallidos.
    def pending_older_than(grace):
        return {
            str(row.get("id") or "")
            for row in picks
            if row.get("id") and row.get("estado") == "PENDIENTE"
            and (kick := _dt(row.get("fecha_utc")))
            and now - kick > grace
        }
    early = pending_older_than(EARLY_SETTLEMENT_GRACE)
    delayed = pending_older_than(SETTLEMENT_GRACE)
    detail["partidos_sin_liquidar_10h"] = len(early)
    detail["partidos_sin_liquidar_48h"] = len(delayed)
    if len(delayed) >= 2:
        issues.append(_issue("LIQUIDACION_RETRASADA", "MEDIA",
            f"{len(delayed)} partidos llevan más de 48 horas pendientes de liquidación "
            "(se cuentan partidos distintos, no selecciones)."))
    elif len(early) >= 2:
        issues.append(_issue("LIQUIDACION_MATINAL_PENDIENTE", "MEDIA",
            f"{len(early)} partidos llevan más de 10 horas sin liquidar; "
            "revisar la ronda postpartido nocturna de GitHub Actions."))

    # A failed workflow stays unresolved until THAT workflow succeeds;
    # a later unrelated monitoring tick must not falsely clear the incident.
    failures = dict(previous.get("fallos_workflow") or {})
    valid_sources = ("Analisis futbol diario", "Refresco escalonado de cuotas")
    if source_workflow in valid_sources and source_conclusion:
        if source_conclusion == "success":
            failures.pop(source_workflow, None)
        elif source_conclusion in ("failure", "timed_out", "cancelled"):
            failures[source_workflow] = source_conclusion
    for name, failure in sorted(failures.items()):
        if name not in valid_sources:
            continue
        key = "FALLO_ANALISIS" if name == valid_sources[0] else "FALLO_REFRESCO"
        issues.append(_issue(key, "ALTA",
            f"GitHub Actions informa de una ejecución {failure} en {name}; "
            "pendiente de la siguiente ejecución satisfactoria."))
    issues.sort(key=lambda x: x["codigo"])
    return {
        "version": 1,
        "comprobado_utc": now.isoformat(),
        "estado": "INCIDENCIAS" if issues else "CORRECTO",
        "incidencias": issues,
        "detalle": detail,
        "ultima_captura_revisada": marker or previous_capture,
        "racha_calendario": streak,
        "racha_proveedor": generic_streak,
        "fallos_workflow": failures,
    }

def alert_text(issues, now, *, recovered=False, initial=False):
    if issues:
        head = "🚨 Football AI Lab · Incidencias detectadas"
        rows = [head, "Comprobación: " + now.strftime("%d/%m %H:%M UTC"), ""]
        for issue in issues[:8]:
            rows.append("• " + issue["codigo"].replace("_", " ") + ": " + issue["descripcion"])
        rows.extend(["", "Consulta las ejecuciones: https://github.com/rasekes86/football-ai-lab/actions",
                     "No se modifican pronósticos, cuotas ni resultados."])
    elif recovered:
        rows = ["✅ Football AI Lab · Incidencias anteriores resueltas.",
                "Comprobación: " + now.strftime("%d/%m %H:%M UTC"),
                "El sistema vuelve a cumplir los controles automáticos."]
    elif initial:
        rows = ["🛡️ Football AI Lab · Monitor de salud activado.",
                "Análisis, cuotas y liquidaciones bajo supervisión automática.",
                "Solo avisaré al detectar incidencias o su resolución."]
    else:
        rows = []
    return "\n".join(rows)[:3900]

def run(target=Path("output"), now=None, env=None, sender=send,
        *, preview=False):
    now = now or datetime.now(timezone.utc)
    env = os.environ if env is None else env
    previous = _json(target / STATE_FILENAME)
    report = assess(target, now, previous,
        odds_enabled=_flag(env.get("FREE_ODDS_ENABLED"), True),
        source_workflow=str(env.get("SOURCE_WORKFLOW") or ""),
        source_conclusion=str(env.get("SOURCE_CONCLUSION") or ""))
    issues = report["incidencias"]
    current = sorted(issue["codigo"] for issue in issues)
    old = previous.get("notificadas")
    old = sorted(old) if isinstance(old, list) else None
    initial = old is None
    changed = old != current
    enabled = _flag(env.get("HEALTH_ALERTS_ENABLED"), True)
    token = str(env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = str(env.get("TELEGRAM_CHAT_ID") or "").strip()
    # None means "initial welcome not confirmed yet": retry on next run.
    report["notificadas"] = old
    report["ultima_entrega_utc"] = previous.get("ultima_entrega_utc")
    report["envio"] = "SIN_NOVEDADES"
    message = alert_text(issues, now, recovered=bool(old and not current), initial=initial)
    if preview:
        return {"estado": report["estado"], "incidencias": issues,
                "detalle": report["detalle"], "mensaje": message or "Sin avisos nuevos."}
    if not enabled:
        report["envio"] = "DESACTIVADO"
    elif not token or not chat:
        report["envio"] = "SIN_CREDENCIALES"
    elif changed:
        try:
            confirmed = sender(message, token, chat)
        except Exception:
            confirmed = False  # Never log exception or bot URL with token.
        if confirmed:
            report["notificadas"] = current
            report["ultima_entrega_utc"] = now.isoformat()
            report["envio"] = "ENTREGADO"
        else:
            report["envio"] = "NO_CONFIRMADO"
    target.mkdir(parents=True, exist_ok=True)
    (target / STATE_FILENAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"estado": report["estado"], "incidencias": issues,
            "envio": report["envio"], "detalle": report["detalle"]}

def main():
    parser = argparse.ArgumentParser(description="Control de salud sin consultar cuotas")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    result = run(preview=args.preview)
    print(json.dumps(result, ensure_ascii=False))
    if result.get("envio") == "NO_CONFIRMADO":
        raise SystemExit("Telegram no confirmó aviso de salud; se reintentará sin cambiar estado.")

if __name__ == "__main__":
    main()
