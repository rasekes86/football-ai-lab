"""Seguimiento independiente de precios de bookmaker del Top 3 original.

No consulta APIs: utiliza los snapshots públicos ya obtenidos por real_odds.
Sin coincidencia exacta prepartido no se registra precio ni retorno monetario.
El histórico original de selecciones y la adicional +1,50 son inmutables.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import isfinite
from zoneinfo import ZoneInfo
import json

FIELDS = [
    "clave", "id", "liga", "local", "visitante", "fecha_utc",
    "archivado_utc", "mercado", "seleccion", "probabilidad",
    "cuota_justa", "contrato", "cuota_decimal", "bookmaker",
    "bookmaker_id", "proveedor", "evento_id", "fuente",
    "capturado_utc", "actualizado_utc", "marca_tiempo_tipo",
    "mercado_proveedor", "resultado_proveedor", "linea_cuota",
    "fase_cuota", "estado", "resultado", "retorno_simulado_unidad",
]
ALLOWED_PROVIDERS = {"5DollarFootballAPI", "API-Football", "The Odds API V4"}
MAX_PRICE_AGE_HOURS = 24
MADRID = ZoneInfo("Europe/Madrid")


def _utc(raw):
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _price(raw):
    try:
        if isinstance(raw, bool):
            return None
        value = float(raw)
        return value if isfinite(value) and 1.001 < value <= 1000 else None
    except (TypeError, ValueError):
        return None


def _target(row):
    """Contrato guardado ANTES del inicio, nunca etiqueta generada después."""
    try:
        c = json.loads(row.get("contrato") or "{}")
        typ = c.get("tipo")
        if typ == "resultado":
            outcome = {"H": "1", "D": "X", "A": "2"}.get(c.get("pick"))
            return ("h2h", outcome, None) if outcome else None
        if typ == "ambos":
            outcome = {"Sí": "yes", "Si": "yes", "No": "no"}.get(c.get("pick"))
            return ("btts", outcome, None) if outcome else None
        if typ in ("total", "conteo"):
            if typ == "total":
                market = "totals"
            else:
                market = {"corners": "corners", "yellow": "yellow"}.get(c.get("metrica"))
            if market is None:
                return None
            direction = str(c.get("direccion") or "").casefold()
            outcome = "over" if direction in ("más", "mas") else (
                "under" if direction in ("menos", "menor") else None)
            line = float(c.get("linea"))
            if (outcome is None or not isfinite(line) or line < 0.5
                    or abs((line % 1) - 0.5) > 1e-8):
                return None
            return (market, outcome, line)
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    # Doble oportunidad, goles por equipo, tiros, hándicap sin mercado
    # exactamente equivalente: NO se asigna la cuota de otro mercado.
    return None


def quote_needed_ids(archived, existing, now):
    """Partidos donde falta precio de al menos un Top 3 compatible, prepartido."""
    now = _utc(now)
    if now is None:
        return set()
    have = {r.get("clave") for r in existing or []}
    return {row["id"] for row in archived or []
            if row.get("id") and row.get("clave") not in have
            and _target(row) is not None
            and (kickoff := _utc(row.get("fecha_utc"))) is not None
            and (saved := _utc(row.get("archivado_utc"))) is not None
            and saved < kickoff and now < kickoff}


def _compatible(pick, quote, now):
    target = _target(pick)
    if target is None or not isinstance(quote, dict):
        return False
    if any(quote.get(x) != pick.get(y) for x, y in (
        ("fixture_id", "id"), ("liga", "liga"), ("local", "local"),
        ("visitante", "visitante"), ("fecha_utc", "fecha_utc"))):
        return False
    market, outcome, line = target
    if quote.get("mercado") != market or quote.get("resultado") != outcome:
        return False
    if line is None:
        if quote.get("linea") is not None:
            return False
    else:
        try:
            if quote.get("linea") is None or abs(float(quote["linea"]) - line) > 1e-8:
                return False
        except (TypeError, ValueError):
            return False
    start, archived = _utc(pick.get("fecha_utc")), _utc(pick.get("archivado_utc"))
    captured, updated = _utc(quote.get("capturado_utc")), _utc(quote.get("actualizado_utc"))
    if not all((start, archived, captured, updated)):
        return False
    if not (archived < start and archived <= captured <= now < start
            and updated <= now and updated < start
            and 0 <= (now - captured).total_seconds() <= MAX_PRICE_AGE_HOURS * 3600):
        return False
    if _price(quote.get("cuota")) is None:
        return False
    if quote.get("proveedor") not in ALLOWED_PROVIDERS:
        return False
    if not all(str(quote.get(k) or "").strip() for k in (
        "bookmaker", "bookmaker_id", "evento_id", "fuente", "capturado_utc")):
        return False
    return str(quote["fuente"]).startswith("https://")


def freeze_top3_quotes(archived, quotes, existing, now):
    """Primera captura válida por clave; no recotizar ni modificar el pasado."""
    now = _utc(now)
    if now is None:
        raise ValueError("Fecha UTC obligatoria")
    already = {r["clave"]: dict(r) for r in existing or []
               if isinstance(r, dict) and r.get("clave")}
    by_fixture = defaultdict(list)
    for quote in (quotes or {}).get("cuotas", []):
        if isinstance(quote, dict):
            by_fixture[quote.get("fixture_id")].append(quote)
    for item in archived or []:
        key = item.get("clave")
        if not key or key in already:
            continue
        candidates = [q for q in by_fixture.get(item.get("id"), [])
                      if _compatible(item, q, now)]
        # Misma consulta: elegir determinísticamente el primer bookmaker.
        # No seleccionar a posteriori el precio más favorable.
        candidates.sort(key=lambda q: (
            q["capturado_utc"], str(q["proveedor"]), str(q["bookmaker_id"]),
            float(q["cuota"])))
        if not candidates:
            continue
        q = candidates[0]
        row = {k: item.get(k, "") for k in FIELDS}
        row.update({
            "cuota_decimal": f'{float(q["cuota"]):.4f}',
            "bookmaker": q["bookmaker"],
            "bookmaker_id": q["bookmaker_id"],
            "proveedor": q["proveedor"],
            "evento_id": q["evento_id"],
            "fuente": q["fuente"],
            "capturado_utc": q["capturado_utc"],
            "actualizado_utc": q["actualizado_utc"],
            "marca_tiempo_tipo": q.get("marca_tiempo_tipo", ""),
            "mercado_proveedor": q["mercado"],
            "resultado_proveedor": q["resultado"],
            "linea_cuota": "" if q.get("linea") is None else str(q["linea"]),
            "fase_cuota": q.get("fase_cuota", ""),
            "estado": "PENDIENTE",
            "resultado": "",
            "retorno_simulado_unidad": "",
        })
        already[key] = row
    return sorted(already.values(), key=lambda row: (row.get("fecha_utc", ""),
                                                    row.get("clave", "")))


def settle_top3_quotes(captured, settled_top, additional, now):
    """Liquida únicamente filas con precio real capturado y resultado verificado.

    Los solapamientos exactos con la adicional 3+1 se excluyen del ROI Top 3,
    pero se mantienen en el histórico de precios por trazabilidad.
    """
    from .value_watchlist import active_top3
    now = _utc(now)
    if now is None:
        raise ValueError("Fecha UTC obligatoria")
    active = {x.get("clave") for x in active_top3(captured, additional or [])}
    result_by_key = {r.get("clave"): r for r in settled_top or [] if r.get("clave")}
    tracked = []
    for original in captured or []:
        row = dict(original)
        row["estado"] = "PENDIENTE"
        row["resultado"] = ""
        row["retorno_simulado_unidad"] = ""
        settled = result_by_key.get(row.get("clave"))
        if row.get("clave") not in active:
            row["estado"] = "SOLAPADA_ADICIONAL"
        elif settled and settled.get("estado") == "FINALIZADO" and str(settled.get("resultado")) in ("0", "1"):
            row["estado"] = "FINALIZADO"
            row["resultado"] = str(settled["resultado"])
            price = _price(row.get("cuota_decimal"))
            if price is not None:
                profit = price - 1 if row["resultado"] == "1" else -1
                row["retorno_simulado_unidad"] = f"{profit:.4f}"
        elif settled:
            row["estado"] = settled.get("estado") or "PENDIENTE"
        tracked.append(row)
    return tracked


def _aggregate(rows):
    settled = [x for x in rows if x.get("estado") == "FINALIZADO"
               and x.get("resultado") in ("0", "1")
               and x.get("retorno_simulado_unidad") not in (None, "")]
    n = len(settled)
    profit = sum(float(x["retorno_simulado_unidad"]) for x in settled)
    wins = sum(x["resultado"] == "1" for x in settled)
    return {
        "cotizadas": len(rows),
        "liquidadas": n,
        "aciertos": wins,
        "fallos": n - wins,
        "acierto_pct": round(100 * wins / n, 2) if n else None,
        "beneficio_hipotetico_unidades": round(profit, 4),
        "roi_hipotetico_pct": round(100 * profit / n, 2) if n else None,
    }


def top3_odds_report(archived, captured, tracked, now, state=None):
    now = _utc(now)
    if now is None:
        raise ValueError("Fecha UTC obligatoria")
    leagues = defaultdict(list)
    markets = defaultdict(list)
    days = defaultdict(list)
    for row in tracked:
        leagues[row.get("liga", "")].append(row)
        markets[row.get("mercado", "")].append(row)
        start = _utc(row.get("fecha_utc"))
        if start:
            days[start.astimezone(MADRID).date().isoformat()].append(row)
    pending = sum(row.get("estado") not in ("FINALIZADO", "SOLAPADA_ADICIONAL")
                  for row in tracked)
    overlap = sum(row.get("estado") == "SOLAPADA_ADICIONAL" for row in tracked)
    return {
        "version": "top3-bookmaker-prices-1.0", "calculado_utc": now.isoformat(),
        "selecciones_originales": len(archived or []),
        "con_cuota_observada": len(captured or []),
        "sin_cuota_observada": max(0, len(archived or []) - len(captured or [])),
        "pendientes_con_cuota": pending,
        "solapadas_adicional": overlap,
        "global": _aggregate([r for r in tracked if r.get("estado") != "SOLAPADA_ADICIONAL"]),
        "por_liga": {k: _aggregate(v) for k, v in sorted(leagues.items())},
        "por_mercado": {k: _aggregate(v) for k, v in sorted(markets.items())},
        "por_dia": {k: _aggregate(v) for k, v in sorted(days.items(), reverse=True)},
        "presupuesto": {
            "proveedor_principal": "5DollarFootballAPI Free",
            "maximo_interno_hora": 24,
            "creditos_mensuales_consumidos": 0,
            "consultas_ultima_hora": len((state or {}).get("solicitudes_utc") or []),
            "otros_proveedores_de_pago": "DESACTIVADOS",
        },
        "nota": (
            "Cuotas observadas antes del partido por proveedor externo, no precios "
            "garantizados al usuario ni apuestas realizadas. ROI SIMULADO solo sobre "
            "precios archivados de selecciones Top 3 activas, excluyendo solapamientos "
            "con la adicional. Sin cuota exacta no hay ROI; sin resultado no hay fallo."
        ),
    }
