"""Poisson regularizado de tasas casa/fuera, auditable y sin apuestas."""
from __future__ import annotations
from datetime import date
from math import exp, factorial
import re
import unicodedata

MODEL_VERSION = "poisson-split-0.1.0"
ALIASES = {
    "atletico de madrid": "ath madrid", "atletico madrid": "ath madrid", "atletico": "ath madrid",
    "athletic club": "ath bilbao", "athletic bilbao": "ath bilbao",
    "real betis": "betis", "real sociedad": "sociedad",
    "fc barcelona": "barcelona", "barca": "barcelona",
    "rcd espanyol": "espanyol", "espanyol barcelona": "espanyol", "espanol": "espanyol",
    "deportivo alaves": "alaves", "celta vigo": "celta", "rc celta": "celta",
    "rayo vallecano": "vallecano", "real oviedo": "oviedo",
    "real valladolid": "valladolid", "ud las palmas": "las palmas",
    "cadiz cf": "cadiz", "levante ud": "levante", "elche cf": "elche",
    "rcd mallorca": "mallorca", "girona fc": "girona", "getafe cf": "getafe",
    "villarreal cf": "villarreal", "valencia cf": "valencia", "sevilla fc": "sevilla",
    "manchester united": "man united", "man utd": "man united",
    "manchester city": "man city", "manchester city fc": "man city",
    "tottenham hotspur": "tottenham", "spurs": "tottenham",
    "newcastle united": "newcastle", "newcastle utd": "newcastle",
    "west ham united": "west ham", "nottingham forest": "nott m forest",
    "wolverhampton wanderers": "wolves", "wolverhampton": "wolves",
    "leicester city": "leicester", "leeds united": "leeds",
    "brighton and hove albion": "brighton", "brighton hove albion": "brighton",
    "afc bournemouth": "bournemouth", "bournemouth afc": "bournemouth",
    "crystal palace fc": "crystal palace", "aston villa fc": "aston villa",
    "ipswich town": "ipswich", "southampton fc": "southampton",
    "sunderland afc": "sunderland", "burnley fc": "burnley",
    "fulham fc": "fulham", "brentford fc": "brentford",
    "chelsea fc": "chelsea", "arsenal fc": "arsenal", "liverpool fc": "liverpool",
    "everton fc": "everton",

    # Bundesliga: nombres ESPN frente a football-data.co.uk
    "borussia dortmund": "dortmund", "bvb dortmund": "dortmund",
    "bayer leverkusen": "leverkusen", "bayer 04 leverkusen": "leverkusen",
    "eintracht frankfurt": "ein frankfurt", "eintracht frankfurt am main": "ein frankfurt",
    "vfb stuttgart": "stuttgart", "sc freiburg": "freiburg",
    "rb leipzig": "leipzig", "rasenballsport leipzig": "leipzig",
    "tsg hoffenheim": "hoffenheim", "hoffenheim 1899": "hoffenheim",
    "mainz 05": "mainz", "fsv mainz": "mainz", "fsv mainz 05": "mainz",
    "vfl wolfsburg": "wolfsburg", "fc bayern munich": "bayern munich",
    "borussia monchengladbach": "m gladbach", "borussia m gladbach": "m gladbach",
    "monchengladbach": "m gladbach",
    "fc cologne": "fc koln", "1 fc koln": "fc koln", "koln": "fc koln",
    "fc st pauli": "st pauli", "fc augsburg": "augsburg",
    "werder bremen": "werder bremen", "sv werder bremen": "werder bremen",
    # Serie A
    "inter milan": "inter", "internazionale": "inter", "fc internazionale": "inter",
    "ac milan": "milan", "as roma": "roma", "ss lazio": "lazio",
    "ssc napoli": "napoli", "torino fc": "torino", "hellas verona": "verona",
    "acf fiorentina": "fiorentina", "atalanta bc": "atalanta",
    "bologna fc": "bologna", "juventus fc": "juventus",
    "udinese calcio": "udinese", "parma calcio": "parma",
    "como 1907": "como", "genoa cfc": "genoa",
    # Ligue 1
    "paris saint germain": "paris sg", "psg": "paris sg",
    "olympique marseille": "marseille", "olympique de marseille": "marseille",
    "olympique lyonnais": "lyon", "olympique lyon": "lyon",
    "lille osc": "lille", "as monaco": "monaco",
    "saint etienne": "st etienne", "as saint etienne": "st etienne",
    "stade rennais": "rennes", "stade rennais fc": "rennes",
    "rc lens": "lens", "ogc nice": "nice",
    "montpellier hsc": "montpellier",
    "rc strasbourg": "strasbourg", "rc strasbourg alsace": "strasbourg",
    "fc nantes": "nantes", "stade brestois": "brest",
    "stade de reims": "reims", "toulouse fc": "toulouse",
    "aj auxerre": "auxerre", "angers sco": "angers",

}


def normalize_team(name: str) -> str:
    txt = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    txt = re.sub(r"[^a-z0-9]+", " ", txt.replace("&", " and ")).strip()
    return ALIASES.get(txt, txt)


def pmf(k: int, lam: float) -> float:
    return exp(-lam) * lam ** k / factorial(k)


def probabilities(home_lambda: float, away_lambda: float, max_goals: int = 12) -> dict:
    if home_lambda <= 0 or away_lambda <= 0:
        raise ValueError("Goles esperados deben ser positivos")
    home = draw = away = total = 0.0
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = pmf(h, home_lambda) * pmf(a, away_lambda)
            total += p
            if h > a: home += p
            elif h == a: draw += p
            else: away += p
    if total == 0:
        raise ValueError("Underflow de Poisson")
    goals = home_lambda + away_lambda
    return {
        "home": home / total, "draw": draw / total, "away": away / total,
        "over25": 1 - sum(pmf(k, goals) for k in range(3)),
    }


def estimate_goals(history: list[dict], home: str, away: str, fixture_date: date,
                   min_matches: int = 5, recent_matches: int = 25) -> tuple[float, float] | None:
    prior = sorted((r for r in history if r["date"] < fixture_date), key=lambda r: r["date"], reverse=True)
    if len(prior) < 20:
        return None
    home_id, away_id = normalize_team(home), normalize_team(away)
    home_matches = [r for r in prior if normalize_team(r["home"]) == home_id][:recent_matches]
    away_matches = [r for r in prior if normalize_team(r["away"]) == away_id][:recent_matches]
    if len(home_matches) < min_matches or len(away_matches) < min_matches:
        return None
    recent = prior[:min(380, len(prior))]
    avg_h = max(0.25, sum(r["home_goals"] for r in recent) / len(recent))
    avg_a = max(0.25, sum(r["away_goals"] for r in recent) / len(recent))
    # 8 partidos virtuales a la media liguera para reducir la varianza.
    h_attack = (sum(r["home_goals"] for r in home_matches) + 8*avg_h) / (len(home_matches)+8) / avg_h
    h_defense = (sum(r["away_goals"] for r in home_matches) + 8*avg_a) / (len(home_matches)+8) / avg_a
    a_attack = (sum(r["away_goals"] for r in away_matches) + 8*avg_a) / (len(away_matches)+8) / avg_a
    a_defense = (sum(r["home_goals"] for r in away_matches) + 8*avg_h) / (len(away_matches)+8) / avg_h
    lam_h = max(0.15, min(4.0, avg_h*h_attack*a_defense))
    lam_a = max(0.15, min(4.0, avg_a*a_attack*h_defense))
    return lam_h, lam_a
