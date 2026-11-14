"""Consenso transparente, sin entrenamiento sobre el mismo partido."""
from __future__ import annotations
from datetime import date
from .core import estimate_goals, probabilities
from .elo import elo_predict

VERSION = "poisson70-elo30-0.2"

def predict(history: list[dict], home: str, away: str, kickoff_date: date) -> dict | None:
    lambdas = estimate_goals(history, home, away, kickoff_date)
    if lambdas is None:
        return None
    poisson = probabilities(*lambdas)
    elo = elo_predict(history, home, away, kickoff_date)
    weight = .30 if elo else 0.
    out = {k: (1-weight)*poisson[k] + weight*(elo[k] if elo else 0.)
           for k in ("home","draw","away")}
    total = sum(out.values())
    for key in out:
        out[key] /= total
    out.update({"over25": poisson["over25"],"home_lambda": lambdas[0],
                "away_lambda": lambdas[1], "elo_home": elo["home"] if elo else None,
                "elo_draw": elo["draw"] if elo else None, "elo_away": elo["away"] if elo else None,
                "rating_gap": elo["rating_gap"] if elo else None,
                "weight_elo": weight})
    return out
