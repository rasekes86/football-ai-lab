"""Marcadores finales verificados para liquidación; nunca usados para entrenar ni pronosticar.

Prioridad: resultados oficiales revisados con URL, histórico existente,
y marcador final publicado por ESPN. Nunca inferir la finalización por el reloj.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .core import normalize_team
from .sources import ESPN_URL, LEAGUES, http_read

LOG = logging.getLogger(__name__)
MADRID = ZoneInfo("Europe/Madrid")
MAX_DAYS_BACK = 45
MAX_ESPN_DAYS = 24


def _utc(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Falta zona horaria")
    return dt.astimezone(timezone.utc)


def _key(league: str, when: date, home: str, away: str) -> tuple:
    return (league, when, normalize_team(home), normalize_team(away))


def _pending_fixtures(archived: list[dict], now: datetime) -> set[tuple]:
    codes = {label[0]: code for code, label in LEAGUES.items()}
    result = set()
    for item in archived:
        try:
            code = codes[item["liga"]]
            start = _utc(item["fecha_utc"])
            saved = _utc(item.get("archivado_utc") or item["fecha_analisis_utc"])
            if not saved < start or saved > now:
                continue
            if not now >= start + timedelta(hours=2):
                continue
            if now - start > timedelta(days=MAX_DAYS_BACK):
                continue
            result.add(_key(code, start.astimezone(MADRID).date(),
                            item["local"], item["visitante"]))
        except (KeyError, ValueError, TypeError):
            continue
    return result


def _final_espn(event: dict, league: str, day: date) -> dict | None:
    try:
        state = event["status"]["type"]
        status = str(state.get("name") or "").upper()
        if state.get("completed") is not True or (
            "FINAL" not in status and "FULL_TIME" not in status
            and status != "STATUS_FT"
        ):
            return None
        kickoff = _utc(event["date"])
        if kickoff.astimezone(MADRID).date() != day:
            return None
        players = event["competitions"][0]["competitors"]
        home = next(p for p in players if p["homeAway"] == "home")
        away = next(p for p in players if p["homeAway"] == "away")
        hg, ag = int(home["score"]), int(away["score"])
        if min(hg, ag) < 0:
            return None
        return {"date": day, "home": home["team"]["displayName"],
                "away": away["team"]["displayName"],
                "home_goals": hg, "away_goals": ag,
                "fuente_resultado": "ESPN resultado final"}
    except (KeyError, StopIteration, IndexError, TypeError, ValueError):
        return None


def _curated(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        records = json.loads(path.read_text(encoding="utf-8"))["partidos"]
        valid = []
        for row in records:
            if row.get("estado") != "FINALIZADO":
                continue
            url = str(row.get("fuente_url") or "")
            if not url.startswith("https://www.laliga.com/"):
                continue
            day = date.fromisoformat(row["fecha"])
            hg, ag = row["goles_local"], row["goles_visitante"]
            if type(hg) is not int or type(ag) is not int or min(hg, ag) < 0:
                continue
            valid.append((row["liga_codigo"], {
                "date": day, "home": row["local"], "away": row["visitante"],
                "home_goals": hg, "away_goals": ag,
                "fuente_resultado": url,
            }))
        return valid
    except (KeyError, ValueError, TypeError, OSError) as exc:
        LOG.warning("Resultados oficiales revisados no disponibles: %s", exc)
        return []


def augment_results(histories: dict, archived: list[dict], now: datetime,
                    verified_path: Path = Path("data/resultados_finales_verificados.json"),
                    fetcher=None) -> tuple[dict, dict]:
    """Conserva los históricos intactos; añade solo partidos finalizados contrastables."""
    fetcher = fetcher or http_read
    output = {code: [dict(g) for g in games] for code, games in histories.items()}
    wanted = _pending_fixtures(archived, now)
    locations = {}
    for code, games in output.items():
        for index, game in enumerate(games):
            locations[_key(code, game["date"], game["home"], game["away"])] = index

    official, espn, conflicts = 0, 0, 0
    # Las revisiones oficiales prevalecen si difiere el marcador del CSV.
    for code, game in _curated(verified_path):
        key = _key(code, game["date"], game["home"], game["away"])
        if key not in wanted or code not in output:
            continue
        if key in locations:
            idx = locations[key]
            old = output[code][idx]
            if (old["home_goals"], old["away_goals"]) != (
                game["home_goals"], game["away_goals"]
            ):
                conflicts += 1
                LOG.warning("Marcador histórico discordante para %s; se usa revisión oficial", key)
                output[code][idx] = game
            continue
        locations[key] = len(output[code])
        output[code].append(game)
        official += 1

    to_fetch = defaultdict(set)
    for code, day, home, away in wanted - locations.keys():
        to_fetch[(code, day)].add((home, away))
    for (code, day), pairs in sorted(to_fetch.items(), key=lambda x: x[0][1], reverse=True)[:MAX_ESPN_DAYS]:
        url = ESPN_URL.format(code=LEAGUES[code][1]) + "?" + urlencode({
            "dates": day.strftime("%Y%m%d"), "limit": 200,
        })
        try:
            events = json.loads(fetcher(url)).get("events", [])
        except (OSError, ValueError, TypeError, TimeoutError) as exc:
            LOG.warning("Resultados ESPN no disponibles %s %s: %s", code, day, exc)
            continue
        for event in events:
            match = _final_espn(event, code, day)
            if match is None:
                continue
            key = _key(code, day, match["home"], match["away"])
            if key not in wanted or key in locations:
                continue
            locations[key] = len(output[code])
            output[code].append(match)
            espn += 1
    return output, {
        "objetivos": len(wanted), "agregados_laliga": official,
        "agregados_espn": espn, "conflictos_oficiales": conflicts,
        "sin_marcador": sum(key not in locations for key in wanted),
    }
