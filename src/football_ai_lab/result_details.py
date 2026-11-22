"""Detalle trazable por partido de los pronósticos 3+1 ya archivados.

No obtiene resultados, genera picks ni altera el histórico: solo interpreta
estados calculados por el motor de liquidación.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .telegram_3plus1 import _date, _finished

MADRID = ZoneInfo("Europe/Madrid")
WINDOW_DAYS = 7


def build_details(top, extra, old_top, old_extra, now):
    """Partidos del periodo con alguna selección Top 3/adicional válida."""
    old_final = {
        kind + ":" + row["clave"]
        for kind, rows in (("top", old_top), ("extra", old_extra))
        for row in rows if row.get("clave") and _finished(row, now)
    }
    groups = {}
    start = now - timedelta(days=WINDOW_DAYS)
    for kind, records in (("top", top), ("extra", extra)):
        for row in records:
            kickoff = _date(row.get("fecha_utc"))
            if not row.get("id") or not kickoff or not start <= kickoff < now:
                continue
            entry = groups.setdefault(row["id"], {
                "id": row["id"],
                "fecha_utc": kickoff.isoformat(),
                "liga": row.get("liga", ""),
                "local": row.get("local", ""),
                "visitante": row.get("visitante", ""),
                "_rows": [],
            })
            entry["_rows"].append((kind, row))
    matches = []
    for entry in groups.values():
        kickoff = _date(entry["fecha_utc"])
        rows = entry.pop("_rows")
        checkable = now >= kickoff + timedelta(hours=2)
        total = len(rows)
        done = sum(_finished(row, now) for _, row in rows)
        new = sum(
            _finished(row, now) and kind + ":" + row["clave"] not in old_final
            for kind, row in rows
        )
        unresolved = [row for _, row in rows if not _finished(row, now)]
        reasons = []
        if unresolved and not checkable:
            reasons.append("Aún no han transcurrido 2 horas desde el inicio")
        statuses = {row.get("estado") for row in unresolved}
        if "RESULTADO_NO_DISPONIBLE" in statuses:
            reasons.append("Sin marcador final contrastado")
        if "ESTADISTICA_NO_DISPONIBLE" in statuses:
            reasons.append("Faltan estadísticas finales contrastadas")
        if any(str(s).startswith("EXCLUIDO") for s in statuses):
            reasons.append("Hay selecciones excluidas por datos o fechas inválidos")
        if checkable and "PENDIENTE" in statuses:
            reasons.append("Sin liquidación concluyente en esta revisión")
        if unresolved and not reasons:
            reasons.append("Quedan selecciones sin confirmación")
        status = (
            "LIQUIDADO" if done == total else
            "PARCIAL" if done else
            "EN_ESPERA" if not checkable else "PENDIENTE"
        )
        def stats(kind):
            included = [row for label, row in rows if label == kind]
            return {"registradas": len(included),
                    "liquidadas": sum(_finished(row, now) for row in included)}
        matches.append({
            **entry,
            "revisable": checkable,
            "estado": status,
            "selecciones": total,
            "liquidadas": done,
            "pendientes": total - done,
            "nuevas_liquidaciones": new,
            "top3": stats("top"),
            "adicional": stats("extra"),
            "motivos": reasons,
        })
    matches.sort(key=lambda m: (m["fecha_utc"], m["id"]), reverse=True)
    totals = {
        "con_selecciones": len(matches),
        "revisables": sum(m["revisable"] for m in matches),
        "liquidados": sum(m["estado"] == "LIQUIDADO" for m in matches),
        "parciales": sum(m["estado"] == "PARCIAL" for m in matches),
        "pendientes": sum(m["estado"] == "PENDIENTE" for m in matches),
        "en_espera": sum(m["estado"] == "EN_ESPERA" for m in matches),
    }
    return matches, totals


def preview(matches, limit=6):
    """Priorizar pendientes, parciales y novedades; informe completo en /detalle."""
    unresolved = [m for m in matches if m["estado"] != "LIQUIDADO"]
    fresh = [m for m in matches if m["nuevas_liquidaciones"] and m not in unresolved]
    rest = [m for m in matches if m not in unresolved and m not in fresh]
    ordered = unresolved + fresh + rest
    lines = []
    for m in ordered[:limit]:
        symbol = {"LIQUIDADO": "✅", "PARCIAL": "🟡",
                  "PENDIENTE": "⏳", "EN_ESPERA": "🕒"}[m["estado"]]
        when = _date(m["fecha_utc"]).astimezone(MADRID).strftime("%d/%m %H:%M")
        lines.append(
            f'{symbol} {when} · {str(m["local"])[:25]} – '
            f'{str(m["visitante"])[:25]} · {m["liquidadas"]}/{m["selecciones"]}'
            + (f' ({m["nuevas_liquidaciones"]} nuevas)' if m["nuevas_liquidaciones"] else "")
            + ("\n   " + "; ".join(m["motivos"])[:145] if m["motivos"] else "")
        )
    return lines, len(ordered) - len(lines)
