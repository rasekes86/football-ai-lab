"""Desglose trazable por partido de los mercados del Top 3.

El resultado se calcula exclusivamente por market_prospective.settle.
Este módulo solo describe la evidencia observada y su fuente.
"""
from __future__ import annotations

from datetime import datetime
import json
from .core import normalize_team
from .market_prospective import utc, MADRID
from .sources import LEAGUES

VERSION = "postmatch-breakdown-1.0"
METRICS = {
    "shots": "Tiros totales",
    "on_target": "Tiros a puerta",
    "corners": "Córners",
    "yellow": "Tarjetas amarillas",
    "red": "Tarjetas rojas",
}


def _match_index(histories):
    idx = {}
    for code, matches in histories.items():
        for g in matches:
            key = (code, g["date"], normalize_team(g["home"]), normalize_team(g["away"]))
            idx[key] = g
    return idx


def _value(game, side, metric):
    val = game.get(side + "_" + metric) if game else None
    return val if isinstance(val, int) and not isinstance(val, bool) else None


def _stats(game):
    sources = game.get("fuentes_metricas") or {}
    values = {}
    for metric, title in METRICS.items():
        home, away = _value(game, "home", metric), _value(game, "away", metric)
        src = {sources.get(side + "_" + metric, "")
               for side in ("home", "away") if _value(game, side, metric) is not None}
        src.discard("")
        values[metric] = {
            "nombre": title, "local": home, "visitante": away,
            "total": home + away if home is not None and away is not None else None,
            "fuentes": sorted(src),
        }
    return values


def _explanation(pick, game, metrics):
    status = pick["estado"]
    if status == "RESULTADO_NO_DISPONIBLE":
        return "No se ha podido verificar el marcador final."
    if status == "ESTADISTICA_NO_DISPONIBLE":
        try:
            spec = json.loads(pick["contrato"])
            metric = spec.get("metrica")
        except (ValueError, TypeError, KeyError):
            metric = None
        name = METRICS.get(metric, "la métrica requerida")
        return f"No hay datos completos y verificables para {name.lower()}."
    if status == "PENDIENTE":
        return "Aún no corresponde realizar la liquidación."
    if status.startswith("EXCLUIDO"):
        return "La selección no cumple los controles de registro prepartido."
    if status != "FINALIZADO" or game is None:
        return "Sin datos suficientes para explicar esta selección."
    try:
        spec = json.loads(pick.get("contrato") or "{}")
    except (TypeError, ValueError):
        return "Contrato sin formato verificable."
    typ = spec.get("tipo")
    outcome = "ACIERTO" if pick.get("resultado") == "1" else "FALLO"
    if typ == "conteo":
        metric = spec.get("metrica")
        stat = metrics.get(metric, {})
        if stat.get("total") is None:
            return "No hay total verificable para este mercado."
        return (f"{outcome}: {METRICS.get(metric, metric)}: "
                f"{stat['local']} local + {stat['visitante']} visitante = "
                f"{stat['total']}; línea {spec.get('linea')}.")
    if typ in ("total", "goles_equipo", "ambos", "resultado", "doble", "handicap"):
        return (f"{outcome}: marcador final {game['home_goals']}-"
                f"{game['away_goals']}; resultado observado {pick.get('valor_real', '—')}.")
    return f"{outcome}: resultado final contrastado."


def build_breakdown(selections: list[dict], histories: dict,
                    now: datetime, audit: dict | None = None) -> dict:
    by_league = {v[0]: code for code, v in LEAGUES.items()}
    matches = _match_index(histories)
    groups = {}
    for item in selections:
        ident = item.get("id")
        if not ident:
            continue
        groups.setdefault(ident, []).append(item)
    output = []
    for ident, rows in groups.items():
        first = rows[0]
        try:
            code = by_league[first["liga"]]
            day = utc(first["fecha_utc"]).astimezone(MADRID).date()
            key = (code, day, normalize_team(first["local"]),
                   normalize_team(first["visitante"]))
            game = matches.get(key)
        except (KeyError, ValueError, TypeError):
            game = None
        stats = _stats(game) if game else {}
        source_score = ((game.get("fuente_resultado") or
                         "football-data.co.uk · histórico CSV") if game else "")
        picks = []
        for row in rows:
            sources = []
            try:
                spec = json.loads(row.get("contrato") or "{}")
                if spec.get("tipo") == "conteo":
                    sources = stats.get(spec.get("metrica"), {}).get("fuentes", [])
                elif game:
                    sources = [source_score]
            except (TypeError, ValueError):
                pass
            picks.append({
                "clave": row.get("clave"), "mercado": row.get("mercado"),
                "seleccion": row.get("seleccion"), "estado": row.get("estado"),
                "resultado": row.get("resultado"),
                "valor_real": row.get("valor_real"),
                "fuentes": sources,
                "explicacion": _explanation(row, game, stats),
            })
        output.append({
            "id": ident, "liga": first.get("liga"), "local": first.get("local"),
            "visitante": first.get("visitante"), "fecha_utc": first.get("fecha_utc"),
            "marcador": (f"{game['home_goals']}-{game['away_goals']}" if game else None),
            "fuente_marcador": source_score,
            "estadisticas": stats, "selecciones": picks,
            "evaluadas": sum(p.get("estado") == "FINALIZADO" for p in picks),
            "aciertos": sum(p.get("estado") == "FINALIZADO" and
                            p.get("resultado") == "1" for p in picks),
        })
    output.sort(key=lambda x: (x["fecha_utc"] or "", x["id"]))
    return {"version": VERSION, "calculado_utc": now.isoformat(),
            "auditoria_estadisticas": audit or {},
            "partidos": output,
            "nota": "Los resultados proceden de snapshots archivados antes del inicio. "
                    "Métricas faltantes sin estimación, sin resultados inventados."}
