"""Conectores a fuentes públicas. Acceso best-effort, sujeto a disponibilidad."""
from __future__ import annotations
import csv
from datetime import date, datetime, timedelta, timezone
from io import StringIO
import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOG = logging.getLogger(__name__)
LEAGUES = {
    "SP1": ("LaLiga", "esp.1"), "SP2": ("Segunda División", "esp.2"),
    "E0": ("Premier League", "eng.1"),
    "D1": ("Bundesliga", "ger.1"), "I1": ("Serie A", "ita.1"),
    "F1": ("Ligue 1", "fra.1"),
}
HISTORY_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard"


def http_read(url: str, timeout: int = 20) -> bytes:
    request = Request(url, headers={"User-Agent": "FootballAILab/0.1 (educational research)", "Accept": "*/*"})
    with urlopen(request, timeout=timeout) as response:
        return response.read(8_000_000)


def parse_date(raw: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except (ValueError, TypeError, AttributeError):
            pass
    return None


def parse_history(body: bytes) -> list[dict]:
    try:
        txt = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = body.decode("cp1252")
    reader = csv.DictReader(StringIO(txt))
    required = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("CSV sin columnas esperadas")
    records = []
    for row in reader:
        d = parse_date(row.get("Date") or "")
        try:
            hg, ag = int(row.get("FTHG") or ""), int(row.get("FTAG") or "")
        except ValueError:
            continue
        h, a = (row.get("HomeTeam") or "").strip(), (row.get("AwayTeam") or "").strip()
        if d and h and a:
            match={"date":d, "home":h, "away":a, "home_goals":hg, "away_goals":ag}
            # Only completed historical matches. Missing metrics remain None; never zero.
            optional={"home_shots":"HS","away_shots":"AS","home_on_target":"HST",
                      "away_on_target":"AST","home_corners":"HC","away_corners":"AC",
                      "home_yellow":"HY","away_yellow":"AY","home_red":"HR","away_red":"AR"}
            for field,original in optional.items():
                value=(row.get(original) or "").strip()
                try:match[field]=max(0,int(float(value))) if value else None
                except ValueError:match[field]=None
            records.append(match)
    return records


def season_codes(today: date, count: int = 4) -> list[str]:
    first = today.year if today.month >= 7 else today.year - 1
    return [f"{y%100:02d}{(y+1)%100:02d}" for y in range(first-count+1, first+1)]


def load_history(league: str, today: date) -> list[dict]:
    records = []
    for season in season_codes(today):
        url = HISTORY_URL.format(season=season, league=league)
        try:
            entries = parse_history(http_read(url))
            records.extend(entries)
            LOG.info("%s: %s partidos", url, len(entries))
        except Exception as exc:
            LOG.warning("Histórico no disponible %s: %s", url, exc)
    distinct = {(r["date"], r["home"], r["away"]): r for r in records}
    return sorted(distinct.values(), key=lambda r: r["date"])


def parse_espn_events(body: bytes, league: str, today: date) -> list[dict]:
    out = []
    now = datetime.now(timezone.utc)
    for event in json.loads(body).get("events", []):
        try:
            if event["status"]["type"]["name"] not in {"STATUS_SCHEDULED", "STATUS_PRE"}:
                continue
            kickoff = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
            if kickoff < now:
                continue
            competitors = event["competitions"][0]["competitors"]
            home = next(x for x in competitors if x["homeAway"] == "home")["team"]["displayName"]
            away = next(x for x in competitors if x["homeAway"] == "away")["team"]["displayName"]
            out.append({"league": league, "kickoff": kickoff, "home": home, "away": away, "event_id": event.get("id", "")})
        except (KeyError, ValueError, StopIteration, IndexError, TypeError) as exc:
            LOG.warning("Partido incompleto: %s", exc)
    return out


def load_fixtures(league: str, today: date, days: int = 7) -> list[dict]:
    seen = {}
    for offset in range(days):
        d = today + timedelta(days=offset)
        url = ESPN_URL.format(code=LEAGUES[league][1]) + "?" + urlencode({"dates": d.strftime("%Y%m%d")})
        try:
            for event in parse_espn_events(http_read(url), league, today):
                key = event["event_id"] or str((event["kickoff"], event["home"], event["away"]))
                seen[key] = event
        except Exception as exc:
            LOG.warning("Calendario ESPN %s %s: %s", league, d, exc)
    return sorted(seen.values(), key=lambda f: f["kickoff"])
