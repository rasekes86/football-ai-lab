"""Cuarta selección del modelo cuando no se archivó cuota real +1,50.

Archivo INDEPENDIENTE del histórico de bookmakers: cuota justa = 1/p, nunca
una cuota ofrecida. Un pronóstico archivado prepartido no se reescribe.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json

from .selector import goal_candidates
from .market_prospective import contract, settle
from .value_watchlist import FIELDS

KIND = "CUOTA_JUSTA_TEORICA_NO_OFRECIDA"
MIN_P = .55
MAX_P = 1 / 1.501


def freeze(predictions: list[dict], previous: list[dict],
           frozen_top3: list[dict], now: datetime) -> list[dict]:
    """Archiva una cuarta selección distinta de las tres originales, solo antes del partido."""
    rows = [dict(r) for r in previous]
    covered = {r.get("id") for r in rows}
    occupied = defaultdict(set)
    for row in frozen_top3:
        occupied[row.get("id")].add((row.get("mercado"), row.get("seleccion")))
    for m in predictions:
        event_id = m.get("id")
        if not event_id or event_id in covered:
            continue
        try:
            kickoff = datetime.fromisoformat(m["fecha_utc"].replace("Z", "+00:00"))
            if kickoff.tzinfo is None or now >= kickoff:
                continue
            options = []
            for c in goal_candidates(m):
                p = float(c["probabilidad"])
                if not MIN_P <= p <= MAX_P:
                    continue
                if (c["mercado"], c["seleccion"]) in occupied[event_id]:
                    continue
                specification = contract(m, c)
                if not specification:
                    continue
                # No prior retrospective counts; only Poisson goal candidates.
                options.append((p, c["mercado"], c["seleccion"], c, specification))
            if not options:
                continue
            p, _, _, choice, specification = max(options, key=lambda o: (o[0], o[1], o[2]))
            payload = dict.fromkeys(FIELDS, "")
            payload.update(
                clave=event_id + "|" + choice["mercado"] + "|" + choice["seleccion"],
                id=event_id, liga=m["liga"], local=m["local"],
                visitante=m["visitante"], fecha_utc=m["fecha_utc"],
                archivado_utc=now.isoformat(), mercado=choice["mercado"],
                seleccion=choice["seleccion"], familia=choice["familia"],
                origen=choice["origen"], nivel="MODELO_NO_CALIBRADO",
                probabilidad=f"{p:.6f}", cuota_justa=f"{1/p:.3f}",
                contrato=json.dumps(specification, sort_keys=True, ensure_ascii=False),
                tipo_cuota=KIND, origen_cuota="Cuota justa matemática (NO ofrecida)",
                ref_modelo_utc=now.isoformat(), estado="PENDIENTE",
            )
            rows.append(payload)
            covered.add(event_id)
        except (ValueError, TypeError, KeyError):
            continue
    return rows


def evaluate(rows: list[dict], histories: dict, now: datetime) -> list[dict]:
    """Liquida por resultado deportivo, pero no calcula retornos a cuotas inexistentes."""
    tracked = settle(rows, histories, now)
    for row in tracked:
        row["retorno_simulado_unidad"] = ""
        row["retorno_precio_api_unidad"] = ""
        row["cuota_decimal"] = ""
    return tracked
