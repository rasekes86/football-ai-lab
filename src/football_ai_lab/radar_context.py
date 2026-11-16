"""Contexto estrictamente anterior al partido para el radar de pronósticos.

Fuente: históricos finalizados usados ya por el motor. NO usa resultados
del partido que se pretende pronosticar ni entrena/ajusta probabilidades.
Los recuentos desconocidos siguen ausentes (no son ceros).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .core import normalize_team
from .sources import LEAGUES

VERSION = "radar-context-1.0"
MADRID = ZoneInfo("Europe/Madrid")
WINDOWS = (5, 10, 20)
METRICS = ("goals", "corners", "shots", "on_target", "yellow", "red", "fouls")


def _num(value):
    return value if type(value) is int and 0 <= value <= 400 else None


def _record(game: dict, team: str):
    try:
        hg = _num(game["home_goals"])
        ag = _num(game["away_goals"])
        if hg is None or ag is None:
            return None
        home = normalize_team(game["home"])
        away = normalize_team(game["away"])
        if not home or not away or home == away or team not in (home, away):
            return None
        at_home = team == home
        own, against = (hg, ag) if at_home else (ag, hg)
        values = {"goals": hg + ag}
        for metric in METRICS:
            if metric == "goals":
                continue
            h = _num(game.get("home_" + metric))
            a = _num(game.get("away_" + metric))
            values[metric] = h + a if h is not None and a is not None else None
        return {
            "date": game["date"].isoformat(),
            "venue": "home" if at_home else "away",
            "result": "W" if own > against else "D" if own == against else "L",
            "gf": own, "ga": against,
            "btts": own > 0 and against > 0,
            "totals": values,
        }
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def _window(rows: list[dict], n: int) -> dict:
    recent = rows[:n]
    observed = {}
    for metric in METRICS:
        values = [row["totals"].get(metric) for row in recent]
        valid = [v for v in values if _num(v) is not None]
        observed[metric] = {
            "n": len(valid),
            "mean": round(sum(valid) / len(valid), 2) if valid else None,
            # Secuencia de partidos antiguos conservada para calcular el
            # cumplimiento de una línea SIN inventar tasas.
            "values": values,
        }
    return {
        "matches": len(recent),
        "latest": recent[0]["date"] if recent else None,
        "wins": sum(row["result"] == "W" for row in recent),
        "draws": sum(row["result"] == "D" for row in recent),
        "losses": sum(row["result"] == "L" for row in recent),
        "both_scored": sum(row["btts"] for row in recent),
        "goals_for": round(sum(row["gf"] for row in recent) / len(recent), 2) if recent else None,
        "goals_against": round(sum(row["ga"] for row in recent) / len(recent), 2) if recent else None,
        "metrics": observed,
    }


def build_radar_context(histories: dict, fixtures: list[dict], now: datetime) -> dict:
    """Ventanas 5/10/20 totales y en sede, fecha estrictamente anterior.

    Se usa el histórico ORIGINAL, sin el enriquecimiento de liquidaciones
    ni los resultados añadidos para partidos archivados.
    """
    if now.tzinfo is None:
        raise ValueError("now debe incluir zona horaria")
    codes = {label[0]: code for code, label in LEAGUES.items()}
    result = []
    for fixture in fixtures:
        try:
            start = datetime.fromisoformat(
                str(fixture["fecha_utc"]).replace("Z", "+00:00")
            )
            if start.tzinfo is None or start <= now:
                continue
            code = codes[fixture["liga"]]
            game_day = start.astimezone(MADRID).date()
            if not fixture.get("id"):
                continue
        except (KeyError, ValueError, TypeError):
            continue
        teams = {}
        for side, venue in (("local", "home"), ("visitante", "away")):
            name = str(fixture.get(side) or "")
            canonical = normalize_team(name)
            candidates, seen = [], set()
            for game in histories.get(code, []):
                try:
                    if game["date"] >= game_day:
                        continue  # no hay hora fiable: se excluye el día completo
                    identity = (game["date"], normalize_team(game["home"]),
                                normalize_team(game["away"]))
                    if identity in seen:
                        continue
                    record = _record(game, canonical)
                    if record:
                        candidates.append(record)
                        seen.add(identity)
                except (KeyError, TypeError):
                    continue
            candidates.sort(key=lambda x: x["date"], reverse=True)
            by_venue = [row for row in candidates if row["venue"] == venue]
            teams[side] = {
                "name": name, "venue": venue,
                "overall": {str(n): _window(candidates, n) for n in WINDOWS},
                "venue_only": {str(n): _window(by_venue, n) for n in WINDOWS},
            }
        result.append({
            "id": fixture["id"],
            "liga": fixture["liga"],
            "fecha_utc": fixture["fecha_utc"],
            "local": fixture["local"], "visitante": fixture["visitante"],
            "equipos": teams,
        })
    return {
        "version": VERSION,
        "generado_utc": now.isoformat(),
        "fuente": "football-data.co.uk · histórico previo al encuentro",
        "ventanas": list(WINDOWS),
        "partidos": result,
        "nota": ("Los últimos 5/10/20 partidos y sus condiciones de local/visitante "
                 "son observaciones PREVIAS, sin resultados del día del encuentro. "
                 "No son la probabilidad del modelo ni prueban rentabilidad. "
                 "La cobertura excluye estadísticas no disponibles."),
    }
