"""Modelo Elo independiente: actualiza puntuaciones usando solo partidos previos."""
from __future__ import annotations
from datetime import date
from .core import normalize_team

VERSION = "elo-home60-k20-0.1"
HOME_ADVANTAGE = 60.0
K_FACTOR = 20.0

def elo_predict(history: list[dict], home: str, away: str, cutoff: date) -> dict | None:
    past = sorted((m for m in history if m["date"] < cutoff), key=lambda m: m["date"])
    if len(past) < 30:
        return None
    ratings: dict[str,float] = {}
    count: dict[str,int] = {}
    for m in past:
        h = normalize_team(m["home"])
        a = normalize_team(m["away"])
        rh, ra = ratings.get(h, 1500.), ratings.get(a, 1500.)
        expected = 1. / (1. + 10. ** ((ra-rh-HOME_ADVANTAGE)/400.))
        result = 1. if m["home_goals"] > m["away_goals"] else .5 if m["home_goals"] == m["away_goals"] else 0.
        ratings[h] = rh + K_FACTOR * (result-expected)
        ratings[a] = ra + K_FACTOR * ((1-result)-(1-expected))
        count[h], count[a] = count.get(h,0)+1, count.get(a,0)+1
    h, a = normalize_team(home), normalize_team(away)
    if count.get(h,0)<5 or count.get(a,0)<5:
        return None
    binary = 1. / (1. + 10. ** ((ratings[a]-ratings[h]-HOME_ADVANTAGE)/400.))
    recent = past[-min(380, len(past)):]
    draw_rate = sum(m["home_goals"] == m["away_goals"] for m in recent)/len(recent)
    draw_rate = max(.18,min(.36,draw_rate))
    return {"home":binary*(1-draw_rate), "draw":draw_rate,
            "away":(1-binary)*(1-draw_rate), "rating_gap":ratings[h]-ratings[a]}
