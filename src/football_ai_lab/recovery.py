"""Recuperación conservadora de un cron ausente, sin tocar históricos ni APIs de cuotas.

Solo se ejecuta desde el vigilante programado. No se dispara por cambios de
código, ni desde el workflow diario; previene bucles y respeta un cooldown.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess

STALE_AFTER = timedelta(hours=26)
DISPATCH_COOLDOWN = timedelta(hours=12)
RECENT_RUN_COOLDOWN = timedelta(hours=2)
ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending"}


def parse_utc(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def needs_recovery(status, now):
    """Evitar reejecución si los datos son recientes o tienen fecha futura."""
    stamp = parse_utc((status or {}).get("calculado_utc"))
    if stamp is None:
        return True
    age = now - stamp
    return STALE_AFTER <= age and age >= timedelta(0)


def can_dispatch(runs, now):
    """No duplicar runs activos ni reintentos recientes de workflow_dispatch."""
    for row in runs or []:
        created = parse_utc(row.get("createdAt"))
        if row.get("status") in ACTIVE:
            return False
        if created is None:
            continue
        age = now - created
        if timedelta(0) <= age < DISPATCH_COOLDOWN and row.get("event") == "workflow_dispatch":
            return False
        if timedelta(0) <= age < RECENT_RUN_COOLDOWN:
            return False
    return True


def main():
    now = datetime.now(timezone.utc)
    path = Path("output/evaluacion_selecciones.json")
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        status = {}
    if not needs_recovery(status, now):
        print("FOOTBALL HEALTH: análisis reciente, sin recuperación necesaria")
        return
    print("FOOTBALL HEALTH: cron posiblemente omitido, auditando ejecuciones")
    try:
        raw = subprocess.check_output(
            ["gh", "run", "list", "--workflow", "daily.yml", "--limit", "20",
             "--json", "event,status,createdAt"],
            text=True, timeout=20)
        runs = json.loads(raw)
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise SystemExit("No se pudo verificar GitHub Actions; se evita despacho a ciegas")
    if not can_dispatch(runs, now):
        print("FOOTBALL HEALTH: recuperación omitida (run activo o cooldown)")
        return
    subprocess.check_call(["gh", "workflow", "run", "daily.yml", "--ref", "main"], timeout=20)
    print("FOOTBALL HEALTH: solicitado un único reintento controlado")


if __name__ == "__main__":
    main()
