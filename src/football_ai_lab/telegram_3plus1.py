"""3+1: opt-in Telegram alerts for confirmed prospective selections only.

Strictly reads the frozen Top 3 + one additional per fixture. No exploratory
forecasts, no retrospectively manufactured bookmaker prices, no betting action.
Only reported result keys are stored after Telegram confirms delivery.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .telegram_notify import send

ROOT = Path("output")
STATE_PATH = ROOT / "estado_alertas_3plus1.json"
MADRID = ZoneInfo("Europe/Madrid")
MAX_MESSAGE = 3900
MAX_ITEMS = 16
LOOKBACK_DAYS = 21
VALID_ODDS_TYPES = {"INDICATIVA_NO_VERIFICADA", "OFRECIDA_API_REGISTRADA"}


def _date(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _clean(value, limit=80):
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or ""))).strip()[:limit]


def _csv(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except (OSError, ValueError):
        return []


def _state():
    try:
        obj = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def _price(value):
    try:
        x = float(value)
        return x if 1.5 < x < 1000 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _archived(row):
    kickoff = _date(row.get("fecha_utc"))
    archive = _date(row.get("archivado_utc"))
    return bool(kickoff and archive and archive < kickoff)


def _collect(rows, extra):
    """Limit counts before looking at outcomes; never include 4th analysis."""
    fixtures = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("clave") or not row.get("id"):
            continue
        if not _archived(row):
            continue
        if extra and (row.get("tipo_cuota") not in VALID_ODDS_TYPES or
                      _price(row.get("cuota_decimal")) is None):
            continue
        fixtures.setdefault(row["id"], []).append(row)
    picks = []
    for group in fixtures.values():
        # Deterministic: freeze first original 3 or first eligible additional.
        group.sort(key=lambda r: _date(r.get("archivado_utc")))
        # Preserve original archive order for records with the same timestamp.
        distinct = set()
        for row in group:
            if row["clave"] in distinct:
                continue
            distinct.add(row["clave"])
            picks.append(row)
            if len(distinct) >= (1 if extra else 3):
                break
    return picks


def _finished(row, now):
    kickoff = _date(row.get("fecha_utc"))
    return bool(kickoff and kickoff < now and row.get("estado") == "FINALIZADO"
                and str(row.get("resultado")) in ("0", "1"))


def _summary(top, extra, now):
    def numbers(rows):
        done = [r for r in rows if _finished(r, now)]
        return {"total": len(rows), "resolved": len(done),
                "hits": sum(str(r["resultado"]) == "1" for r in done),
                "pending": len(rows) - len(done)}
    return {"top": numbers(top), "extra": numbers(extra)}


def digest(top_rows, extra_rows, state, now, max_items=MAX_ITEMS):
    """Build a capped digest; mark only the items actually included."""
    now = now.astimezone(timezone.utc)
    top = _collect(top_rows, extra=False)
    extra = _collect(extra_rows, extra=True)
    totals = _summary(top, extra, now)
    previous = set(state.get("reported_keys") or [])
    events = []
    for kind, rows in (("top", top), ("extra", extra)):
        for row in rows:
            kickoff = _date(row.get("fecha_utc"))
            key = kind + ":" + row["clave"]
            if (not _finished(row, now) or key in previous or kickoff is None or
                    not now - timedelta(days=LOOKBACK_DAYS) <= kickoff < now):
                continue
            events.append((kickoff, kind, key, row))
    events.sort(key=lambda item: (item[0], item[1], item[2]))
    if not events:
        return "", dict(state), {
            "enviar": False, "motivo": "sin nuevas liquidaciones 3+1", **totals,
            "notificados": 0,
        }

    parts = [
        "⚽ Football AI Lab · Resultados confirmados 3+1",
        "Fecha: " + now.astimezone(MADRID).strftime("%d/%m/%Y %H:%M") + " (Madrid)",
        ("Top 3: " + str(totals["top"]["hits"]) + " aciertos / " +
         str(totals["top"]["resolved"]) + " resueltos; " +
         str(totals["top"]["pending"]) + " pendientes."),
        ("Adicional +1,50: " + str(totals["extra"]["hits"]) + " aciertos / " +
         str(totals["extra"]["resolved"]) + " resueltas; " +
         str(totals["extra"]["pending"]) + " pendientes."),
    ]
    footer = [
        "Sin resultados finales suficientes, una selección NO cuenta como fallo.",
        "Cuotas y balances hipotéticos: no son apuestas ejecutadas ni rentabilidad real.",
        "https://rasekes86.github.io/football-ai-lab/#performance",
    ]
    included = []
    for kickoff, kind, key, row in events:
        if len(included) >= max_items:
            break
        icon = "✅" if str(row["resultado"]) == "1" else "❌"
        label = "Top 3" if kind == "top" else "Adicional"
        market = _clean(row.get("seleccion"), 75)
        price = ""
        if kind == "extra":
            price = " · " + ("API" if row.get("tipo_cuota") ==
                                     "OFRECIDA_API_REGISTRADA" else "indicativa")
            price += " " + format(_price(row.get("cuota_decimal")), ".3f")
        line = (
            icon + " " + label + ": " + _clean(row.get("local"), 30) + " – " +
            _clean(row.get("visitante"), 30) + " (" + _clean(row.get("liga"), 28) +
            ")\n" + market + price
        )
        if len("\n\n".join([*parts, line, *footer])) > MAX_MESSAGE:
            break
        parts.append(line)
        included.append(key)
    if len(included) < len(events) and len("\n\n".join([*parts, "Hay más resultados verificados pendientes de notificar.", *footer])) <= MAX_MESSAGE:
        parts.append("Hay más resultados verificados pendientes de notificar.")
    if not included:
        return "", dict(state), {"enviar": False, "motivo": "sin espacio", **totals, "notificados": 0}
    next_state = dict(state)
    next_state["version"] = 1
    next_state["reported_keys"] = list(dict.fromkeys([
        *state.get("reported_keys", []), *included
    ]))[-10000:]
    next_state["last_delivery_utc"] = now.isoformat()
    message = "\n\n".join([*parts, *footer])
    assert len(message) <= MAX_MESSAGE
    return message, next_state, {
        "enviar": True, "notificados": len(included),
        "restantes": len(events) - len(included), **totals,
    }


def main(argv=None, env=None, now=None, sender=send):
    parser = argparse.ArgumentParser(description="Resultados confirmados Top 3 + adicional")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(argv)
    env = os.environ if env is None else env
    now = now or datetime.now(timezone.utc)
    state = _state()
    top = _csv(ROOT / "seguimiento_selecciones.csv")
    extra = _csv(ROOT / "seguimiento_oportunidades_150.csv")
    message, next_state, meta = digest(top, extra, state, now)
    if args.preview:
        print(message or "3+1: sin nuevas liquidaciones confirmadas.")
        return meta
    enabled = str(env.get("TELEGRAM_3PLUS1_ENABLED", "")).lower() in ("true", "1", "yes")
    token = str(env.get("TELEGRAM_BOT_TOKEN", "")).strip()
    chat = str(env.get("TELEGRAM_CHAT_ID", "")).strip()
    if not enabled or not token or not chat:
        print("Telegram 3+1 opt-in desactivado; ningún mensaje enviado.")
        return {"enviar": False, "motivo": "no activado"}
    if not message:
        print("Telegram 3+1: no hay resultados nuevos.")
        return meta
    try:
        if not sender(message, token, chat):
            print("Telegram 3+1: entrega no confirmada; sin registrar notificados.")
            return {"enviar": False, "motivo": "entrega no confirmada"}
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(next_state, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        print(f"Telegram 3+1: {meta['notificados']} liquidaciones entregadas.")
        return meta
    except Exception as exc:
        # Never print token, chat ID or message-bearing transport URLs.
        print("Telegram 3+1: no entregado (" + type(exc).__name__ + ").")
        return {"enviar": False, "motivo": "error de envío"}


if __name__ == "__main__":
    status = main()
    if status.get("motivo") in ("error de envío", "entrega no confirmada"):
        raise SystemExit(1)
