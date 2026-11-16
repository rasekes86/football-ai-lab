#!/usr/bin/env python3
"""Genera un catálogo local de URLs de escudos desde los equipos de ESPN.

No descarga ni redistribuye imágenes. Solo enlaza URLs publicadas para identificar
clubes de las seis competiciones. La ausencia de datos mantiene el monograma.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from football_ai_lab.core import normalize_team  # noqa: E402

LEAGUES = {
    "LaLiga": "esp.1", "Segunda División": "esp.2",
    "Premier League": "eng.1", "Bundesliga": "ger.1",
    "Serie A": "ita.1", "Ligue 1": "fra.1",
}
FILES = (
    "historico_predicciones.csv", "predicciones.csv", "seguimiento.csv",
    "historico_selecciones.csv", "seguimiento_selecciones.csv",
    "seguimiento_oportunidades_150.csv", "selecciones.csv",
)
HOSTS = ("site.web.api.espn.com", "site.api.espn.com")
LOGO_HOST = "https://a.espncdn.com/"


def fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value).lower())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", value).strip()


def simpler(value: str) -> str:
    """Equivalencia conservadora: solo elimina términos genéricos del club."""
    parts = fold(normalize_team(value)).split()
    junk = {"fc", "cf", "cd", "ac", "sc", "sd", "afc", "club", "de", "futbol",
            "football", "soccer", "calcio", "ud"}
    return " ".join(token for token in parts if token not in junk)


def teams_needed(output: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for name in FILES:
        path = output / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                league = row.get("liga", "")
                if league not in LEAGUES:
                    continue
                for key in ("local", "visitante"):
                    team = (row.get(key) or "").strip()
                    if team:
                        result[league].add(team)
    return result


def _read_catalog(code: str, fetcher=None) -> dict:
    def _get(url: str):
        if fetcher is not None:
            return fetcher(url)
        req = Request(url, headers={
            "User-Agent": "FootballAILabDashboard/1.1 (team crest catalog)",
            "Accept": "application/json",
        })
        with urlopen(req, timeout=15) as response:
            return json.load(response)

    errors = []
    for host in HOSTS:
        url = f"https://{host}/apis/site/v2/sports/soccer/{code}/teams?limit=250"
        try:
            result = _get(url)
            if isinstance(result, dict) and result.get("sports"):
                return result
            raise ValueError("Catálogo vacío o inesperado")
        except (OSError, ValueError, TimeoutError, TypeError) as exc:
            errors.append(f"{host}: {exc}")
    print(f"AVISO {code}: no se pudo consultar ESPN: {' / '.join(errors)[:180]}")
    return {}


def club_records(data: dict) -> list[dict]:
    clubs = []
    for sport in data.get("sports", []):
        for league in sport.get("leagues", []):
            for item in league.get("teams", []):
                club = item.get("team", item)
                if not isinstance(club, dict):
                    continue
                urls = [club.get("logo")]
                urls += [logo.get("href") for logo in club.get("logos", []) if isinstance(logo, dict)]
                logo = next((url for url in urls
                             if isinstance(url, str) and url.startswith(LOGO_HOST)), None)
                if not logo:
                    continue
                names = [club.get(k) for k in ("displayName", "shortDisplayName",
                                                "name", "slug", "abbreviation")]
                names = [n for n in names if isinstance(n, str) and n.strip()]
                if not names:
                    continue
                clubs.append({"names": names, "logo": logo})
    return clubs


def assign_crests(names: set[str], clubs: list[dict]) -> dict[str, str]:
    """Jamás enlaza clubes ambiguos o parecidos por una búsqueda difusa."""
    exact: dict[str, set[str]] = defaultdict(set)
    simple: dict[str, set[str]] = defaultdict(set)
    for club in clubs:
        for label in club["names"]:
            exact[normalize_team(label)].add(club["logo"])
            simple[simpler(label)].add(club["logo"])
    results = {}
    for name in sorted(names):
        direct = exact[normalize_team(name)]
        if len(direct) == 1:
            results[name] = next(iter(direct))
        elif not direct:
            reduced = simple[simpler(name)]
            if len(reduced) == 1 and simpler(name):
                results[name] = next(iter(reduced))
    return results


def build(output: Path, destination: Path, fetcher=None) -> dict:
    targets = teams_needed(output)
    catalog = {}
    stats = {}
    for league, code in LEAGUES.items():
        wanted = targets.get(league, set())
        data = _read_catalog(code, fetcher=fetcher) if wanted else {}
        found = assign_crests(wanted, club_records(data))
        for name, image_url in found.items():
            catalog[f"{league}|{name}"] = image_url
        stats[league] = {"equipos": len(wanted), "escudos": len(found)}
        print(f"{league}: {len(found)}/{len(wanted)} escudos",
              ("· sin coincidencia: " + ", ".join(sorted(wanted-set(found))[:14]))
              if len(found) != len(wanted) else "")
    payload = {
        "version": 1,
        "fuente": "ESPN / a.espncdn.com (escudos de identificación)",
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "cobertura": stats,
        "teams": catalog,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
                           encoding="utf-8")
    return payload


if __name__ == "__main__":
    out = build(ROOT / "output", ROOT / "site/crests.json")
    print(f"Total: {len(out['teams'])} escudos enlazados en el dashboard.")
