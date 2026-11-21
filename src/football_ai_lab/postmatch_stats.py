"""Estadísticas postpartido contrastadas para liquidación prospectiva.

SOLO usa partidos finalizados y contratos prepartido. No altera el histórico
de entrenamiento, pronósticos originales ni apuestas hipotéticas archivadas.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path
from urllib.parse import urlencode

from .core import normalize_team
from .sources import ESPN_URL, LEAGUES, http_read
from .verified_results import _pending_fixtures, _final_espn, _key

LOG = logging.getLogger(__name__)
VERSION = "postmatch-stats-1.0"
MAX_SCOREBOARD_DAYS = 24
MAX_SUMMARIES = 18
COUNTS = ("shots", "on_target", "corners", "yellow", "red", "fouls")
ALIASES = {
    "shots": ("totalShots", "shots"),
    "on_target": ("shotsOnTarget", "shotsOnGoal"),
    "corners": ("cornerKicks", "corners"),
    "yellow": ("yellowCards",),
    "red": ("redCards",),
    "fouls": ("fouls", "foulsCommitted", "totalFouls"),
}
FIELDS = tuple(f"{side}_{metric}" for side in ("home", "away") for metric in COUNTS)
SUMMARY_ROOT = "https://site.api.espn.com/apis/site/v2/sports/soccer/"


def _integer(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 200 else None
    if isinstance(value, str) and value.strip().isdigit():
        integer = int(value.strip())
        return integer if integer <= 200 else None
    return None


def _stat_map(stats):
    """Solo nombres exactos y valores enteros, nunca fracciones ni porcentajes."""
    if not isinstance(stats, list):
        return {}
    raw = {}
    for item in stats:
        if not isinstance(item, dict):
            continue
        key = item.get("name")
        if not isinstance(key, str):
            continue
        val = _integer(item.get("value"))
        if val is None:
            val = _integer(item.get("displayValue"))
        if val is not None:
            raw[key] = val
    output = {}
    for metric, names in ALIASES.items():
        vals = [raw[name] for name in names if name in raw]
        if vals and len(set(vals)) == 1:
            output[metric] = vals[0]
    return output


def _parse_summary(data: dict, league: str, home: str, away: str, event_id: str):
    if not isinstance(data, dict) or not isinstance(data.get("boxscore"), dict):
        return None
    headers = (data.get("header") or {}).get("competitions") or []
    if headers:
        competition = headers[0]
        if not isinstance(competition, dict):
            return None
        # No mezclar datos si la cabecera declara un encuentro distinto.
        if competition.get("id") and str(competition["id"]) != event_id:
            return None
        competitors = competition.get("competitors") or []
        if competitors:
            names = {normalize_team((c.get("team") or {}).get("displayName", ""))
                     for c in competitors if isinstance(c, dict)}
            if names != {normalize_team(home), normalize_team(away)}:
                return None
    players = data["boxscore"].get("teams")
    if not isinstance(players, list) or len(players) != 2:
        return None
    wanted = {"home": normalize_team(home), "away": normalize_team(away)}
    identified = {}
    for team in players:
        if not isinstance(team, dict):
            return None
        name = normalize_team((team.get("team") or {}).get("displayName", ""))
        side = next((side for side, label in wanted.items() if label == name), None)
        if side is None or side in identified:
            return None
        identified[side] = _stat_map(team.get("statistics"))
    if set(identified) != set(wanted):
        return None
    result = {}
    for side, stats in identified.items():
        for metric, number in stats.items():
            result[f"{side}_{metric}"] = number
    return result or None


def _wanted_counts(archived: list[dict], now: datetime) -> dict[tuple, set[str]]:
    eligible = _pending_fixtures(archived, now)
    codes = {label[0]: code for code, label in LEAGUES.items()}
    wanted: dict[tuple, set[str]] = defaultdict(set)
    from zoneinfo import ZoneInfo
    madrid = ZoneInfo("Europe/Madrid")
    for row in archived:
        try:
            contract = json.loads(row.get("contrato") or "{}")
            if contract.get("tipo") != "conteo":
                continue
            metric = contract["metrica"]
            if metric not in COUNTS:
                continue
            kickoff = datetime.fromisoformat(str(row["fecha_utc"]).replace("Z", "+00:00"))
            if kickoff.tzinfo is None:
                continue
            code = codes[row["liga"]]
            key = _key(code, kickoff.astimezone(madrid).date(), row["local"], row["visitante"])
            if key in eligible:
                wanted[key].add(metric)
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
    return wanted


def _usable(game, metrics):
    return all(_integer(game.get(f"{side}_{metric}")) is not None
               for metric in metrics for side in ("home", "away"))


def _safe_cached(path: Path):
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload["partidos"] if isinstance(payload.get("partidos"), list) else []
    except (OSError, ValueError, TypeError, KeyError):
        return []


def _apply(game, stats, provenance):
    fields = game.setdefault("fuentes_metricas", {})
    inserted = 0
    for field in FIELDS:
        number = _integer(stats.get(field))
        if number is None:
            continue
        if _integer(game.get(field)) is None:
            game[field] = number
            fields[field] = provenance
            inserted += 1
    return inserted


def enrich_statistics(histories: dict, archived: list[dict], now: datetime,
                      cache_path: Path = Path("output/estadisticas_finales_verificadas.json"),
                      fetcher=None) -> tuple[dict, dict, dict]:
    """ESPN scoreboard final + summary de mismo ID/equipos/marcador.

    Los datos de football-data.co.uk existentes tienen prioridad, los valores
    ausentes permanecen ausentes y el cache verifica siempre el marcador.
    """
    fetcher = fetcher or http_read
    output = {code: [dict(x) for x in items] for code, items in histories.items()}
    wanted = _wanted_counts(archived, now)
    matches = {}
    duplicates = set()
    for code, games in output.items():
        for game in games:
            key = _key(code, game["date"], game["home"], game["away"])
            if key in matches:
                duplicates.add(key)
            matches[key] = game
            # Fuente por campo, sin adjudicar un cero a los ausentes.
            sources = dict(game.get("fuentes_metricas") or {})
            for field in FIELDS:
                if _integer(game.get(field)) is not None and field not in sources:
                    sources[field] = "football-data.co.uk · histórico CSV"
            game["fuentes_metricas"] = sources

    # Explorador: obtener faltas de todos los partidos prospectivos ya
    # finalizados, aunque no haya apuesta de faltas. No altera el Top 3.
    auxiliary_fouls = {key: {"fouls"} for key in _pending_fixtures(archived, now)
                       if key in matches and key not in duplicates}
    requested = defaultdict(set)
    for key, metrics in wanted.items():
        requested[key].update(metrics)
    for key, metrics in auxiliary_fouls.items():
        requested[key].update(metrics)

    existing = _safe_cached(cache_path)
    by_key = {}
    for item in existing:
        try:
            key = _key(item["liga_codigo"], date.fromisoformat(item["fecha"]),
                       item["local"], item["visitante"])
            url = str(item["fuente_url"])
            if (not url.startswith(SUMMARY_ROOT) or "/summary?event=" not in url
                    or item["liga_codigo"] not in LEAGUES):
                continue
            by_key[key] = item
        except (KeyError, ValueError, TypeError):
            continue
    reused = 0
    for key, metrics in requested.items():
        if key in duplicates or key not in matches or key not in by_key:
            continue
        game = matches[key]
        item = by_key[key]
        if (item.get("goles_local"), item.get("goles_visitante")) != (
                game["home_goals"], game["away_goals"]):
            continue
        reused += _apply(game, item.get("estadisticas") or {}, item["fuente_url"])

    by_day = defaultdict(set)
    for key, metrics in requested.items():
        if key in duplicates or key not in matches or _usable(matches[key], metrics):
            continue
        by_day[(key[0], key[1])].add(key)
    scoreboards = 0
    summaries = 0
    fresh = 0
    mismatched = 0
    failures = 0
    for (code, day), keys in sorted(by_day.items(), key=lambda x: x[0][1], reverse=True)[:MAX_SCOREBOARD_DAYS]:
        url = ESPN_URL.format(code=LEAGUES[code][1]) + "?" + urlencode({
            "dates": day.strftime("%Y%m%d"), "limit": 200
        })
        scoreboards += 1
        try:
            events = json.loads(fetcher(url)).get("events") or []
        except (OSError, ValueError, TypeError, TimeoutError) as exc:
            failures += 1
            LOG.warning("No se pudieron consultar estadísticas %s %s: %s", code, day, exc)
            continue
        found = defaultdict(list)
        for event in events:
            parsed = _final_espn(event, code, day)
            if parsed is None:
                continue
            key = _key(code, day, parsed["home"], parsed["away"])
            if key in keys:
                found[key].append((parsed, event))
        for key in keys:
            if summaries >= MAX_SUMMARIES:
                break
            if len(found[key]) != 1:
                continue  # Partido no encontrado o identidad ambigua.
            parsed, event = found[key][0]
            game = matches[key]
            if (parsed["home_goals"], parsed["away_goals"]) != (
                    game["home_goals"], game["away_goals"]):
                mismatched += 1
                LOG.warning("ESPN difiere del marcador comprobado: %s; se descartan métricas", key)
                continue
            event_id = str(event.get("id") or "")
            if not event_id.isdigit():
                continue
            summary_url = SUMMARY_ROOT + LEAGUES[code][1] + "/summary?event=" + event_id
            summaries += 1
            try:
                data = json.loads(fetcher(summary_url))
                stats = _parse_summary(data, code, parsed["home"], parsed["away"], event_id)
            except (OSError, ValueError, TypeError, TimeoutError) as exc:
                failures += 1
                LOG.warning("Summary ESPN no disponible %s: %s", event_id, exc)
                continue
            if not stats:
                continue
            fresh += _apply(game, stats, summary_url)
            by_key[key] = {
                "liga_codigo": code, "fecha": day.isoformat(),
                "local": parsed["home"], "visitante": parsed["away"],
                "goles_local": parsed["home_goals"],
                "goles_visitante": parsed["away_goals"],
                "event_id": event_id, "fuente_url": summary_url,
                "verificado_utc": now.isoformat(), "estadisticas": stats,
            }

    cached = list(by_key.values())
    cached.sort(key=lambda x: (x.get("fecha", ""), x.get("liga_codigo", "")))
    # Auditoría por encuentro: separar falta de marcador, duplicado y
    # estadísticas ausentes. Un marcador disponible no significa que las
    # estadísticas del contrato estén completas.
    objectives = []
    for key, metrics in sorted(wanted.items(), key=lambda x: (x[0][1], x[0][0], x[0][2:])):
        game = matches.get(key)
        missing = [
            f"{side}_{metric}" for metric in sorted(metrics)
            for side in ("home", "away")
            if not game or _integer(game.get(f"{side}_{metric}")) is None
        ]
        if key in duplicates:
            reason = "DUPLICADO_HISTORICO"
        elif game is None:
            reason = "SIN_MARCADOR_VERIFICADO"
        elif missing:
            reason = "ESTADISTICAS_INCOMPLETAS"
        else:
            reason = "COMPLETO"
        objectives.append({
            "liga_codigo": key[0], "fecha": key[1].isoformat(),
            "local_normalizado": key[2], "visitante_normalizado": key[3],
            "metricas_requeridas": sorted(metrics),
            "campos_ausentes": missing, "motivo": reason,
            "marcador_verificado": game is not None,
            "marcador": (
                f"{game['home_goals']}-{game['away_goals']}" if game else None
            ),
        })
    covered = sum(o["motivo"] == "COMPLETO" for o in objectives)
    reasons = {reason: sum(o["motivo"] == reason for o in objectives)
               for reason in ("SIN_MARCADOR_VERIFICADO", "DUPLICADO_HISTORICO",
                              "ESTADISTICAS_INCOMPLETAS")}
    report = {
        "version": VERSION, "calculado_utc": now.isoformat(),
        "objetivos_conteo": len(wanted), "completos": covered,
        "incompletos": len(wanted)-covered, "scoreboards_consultados": scoreboards,
        "summaries_consultados": summaries, "campos_recuperados": fresh,
        "campos_recuperados_cache": reused,
        "conflictos_marcador": mismatched, "fallos_fuente": failures,
        "objetivos_detalle": objectives,
        "incompletos_por_motivo": reasons,
        "partidos_con_faltas": sum(
            _usable(matches[key], {"fouls"}) for key in auxiliary_fouls), 
        "objetivos_faltas": len(auxiliary_fouls),
        "limites": {"scoreboards": MAX_SCOREBOARD_DAYS, "summaries": MAX_SUMMARIES},
        "nota": "Solo estadísticas de partidos finalizados e identidades y marcadores concordantes. "
                "La ausencia se conserva, nunca equivale a cero. No contamina pronósticos.",
    }
    payload = {"version": VERSION, "calculado_utc": now.isoformat(),
               "auditoria": report, "partidos": cached}
    return output, report, payload
