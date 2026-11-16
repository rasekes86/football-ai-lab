"""Dataset observacional para el explorador de mercados (separado del modelo).

Solo partidos finalizados del histórico de las seis ligas. Se conservan los
huecos de las estadísticas y el origen; ninguna selección se crea a posteriori.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from .sources import LEAGUES
from .core import normalize_team

VERSION = "market-explorer-1.0"
METRICS = ("corners", "shots", "on_target", "yellow", "red", "fouls")
LABELS = {
    "corners": "Córners", "shots": "Tiros",
    "on_target": "Tiros a puerta", "yellow": "Amarillas",
    "red": "Rojas", "fouls": "Faltas cometidas",
}


def _count(value):
    """Nunca transformar estadística vacía en cero ni interpretar porcentajes."""
    if type(value) is int and 0 <= value <= 400:
        return value
    return None


def _metric(game, key):
    home = _count(game.get("home_" + key))
    away = _count(game.get("away_" + key))
    source_map = game.get("fuentes_metricas") or {}
    sources = []
    for field, value in (("home_"+key, home), ("away_"+key, away)):
        if value is None:
            continue
        source = source_map.get(field)
        if not source and not game.get("fuente_resultado"):
            source = "football-data.co.uk · histórico CSV"
        if source:
            sources.append(str(source))
    return {
        "local": home,
        "visitante": away,
        "total": home + away if home is not None and away is not None else None,
        "fuentes": sorted(set(sources)),
    }


def build_market_history(histories: dict, now: datetime, days: int = 365,
                         limit_per_league: int = 500) -> dict:
    if now.tzinfo is None:
        raise ValueError("now debe incluir la zona horaria")
    if not 1 <= days <= 730 or not 1 <= limit_per_league <= 1000:
        raise ValueError("Rango fuera de límites de publicación")
    end = now.astimezone(timezone.utc).date()
    cutoff = end - timedelta(days=days)
    matches = []
    coverage = {}
    for code, (league_name, _) in LEAGUES.items():
        seen = set()
        ordered = sorted(histories.get(code, []),
                         key=lambda x: x.get("date", cutoff), reverse=True)
        valid = []
        for game in ordered:
            try:
                day = game["date"]
                if not cutoff <= day <= end:
                    continue
                home, away = str(game["home"]).strip(), str(game["away"]).strip()
                hg, ag = _count(game["home_goals"]), _count(game["away_goals"])
                if not home or not away or hg is None or ag is None:
                    continue
                key = (code, day, normalize_team(home), normalize_team(away))
                if key in seen:
                    continue
                seen.add(key)
                stats = {metric: _metric(game, metric) for metric in METRICS}
                src = str(game.get("fuente_resultado") or
                          "football-data.co.uk · histórico CSV")
                valid.append({
                    "id": f"{code}|{day.isoformat()}|{key[2]}|{key[3]}",
                    "liga": league_name, "fecha": day.isoformat(),
                    "local": home, "visitante": away,
                    "goles_local": hg, "goles_visitante": ag,
                    "resultado": "1" if hg > ag else "X" if hg == ag else "2",
                    "fuente_marcador": src, "estadisticas": stats,
                })
                if len(valid) >= limit_per_league:
                    break
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        matches.extend(valid)
        coverage[league_name] = {
            "partidos": len(valid),
            "metricas": {metric: sum(m["estadisticas"][metric]["total"] is not None
                                    for m in valid) for metric in METRICS},
        }
    matches.sort(key=lambda x: (x["fecha"], x["liga"], x["local"]), reverse=True)
    return {
        "version": VERSION,
        "generado_utc": now.isoformat(),
        "intervalo_dias": days,
        "fuentes": ["football-data.co.uk · histórico CSV",
                    "ESPN summary · solo partidos y estadísticas verificados"],
        "cobertura": coverage, "partidos": matches,
        "nota": ("Observaciones históricas de partidos finalizados. "
                 "No son pronósticos ni cuotas. Una métrica ausente es null, nunca cero. "
                 "No se utiliza este dataset para entrenar o seleccionar pronósticos."),
    }
