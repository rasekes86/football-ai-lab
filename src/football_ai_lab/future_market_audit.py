"""Fase 4: archivo prospectivo independiente de TODAS las líneas futuras expuestas.

Nunca mezcla este seguimiento con el Top 3 original. Cada partido se congela
UNA vez antes del inicio: no se recalculan probabilidades a posteriori.
La liquidación utiliza el mismo contrato verificable del Top 3 y las fuentes
de resultados confirmadas, sin marcar ausencias como pérdidas.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import isfinite, log
import json

from .market_prospective import (
    FIELDS as BASE_FIELDS, contract, settle, utc,
)

VERSION = "future-market-audit-1.0"
FIELDS = [*BASE_FIELDS, "categoria", "posicion_top3", "estado_validacion"]
CATEGORIES = {
    "corners": "Córners totales",
    "shots": "Tiros totales",
    "on_target": "Tiros a puerta totales",
    "yellow": "Tarjetas amarillas totales",
    "goals": "Total goles",
    "result": "1X2",
    "double": "Doble oportunidad",
    "btts": "Ambos marcan",
}
COUNT_KEYS = {"corners", "shots", "on_target", "yellow"}
BINS = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))
MIN_INDEPENDENT_GAMES=30  # Umbral descriptivo, NO prueba de rentabilidad


def _valid_prediction(match: dict, category: str, candidate: dict):
    if category not in CATEGORIES or candidate.get("mercado") != CATEGORIES[category]:
        return None
    selection = str(candidate.get("seleccion") or "").strip()
    if not selection or len(selection) > 260:
        return None
    try:
        p = float(candidate["probabilidad"])
        price = float(candidate["cuota_justa"])
        if not (isfinite(p) and 0 < p < 1 and isfinite(price) and price > 1):
            return None
        # Detector de errores de exportación: cuota JUSTA debe coincidir
        # aproximadamente con el inverso de la probabilidad publicada.
        if abs(price - 1 / p) > 0.03:
            return None
    except (TypeError, KeyError, ValueError, OverflowError):
        return None
    c = dict(candidate)
    c["seleccion"] = selection
    if category in COUNT_KEYS:
        c["metrica"] = category
    spec = contract(match, c)
    if spec is None:
        return None
    top = candidate.get("posicion_top3")
    top = top if type(top) is int and 1 <= top <= 3 else ""
    return c, spec, p, price, top


def archive_future_markets(
    previous: list[dict], previews: list[dict], now: datetime
) -> tuple[list[dict], dict]:
    """Snapshot inmutable por partido (primera ejecución elegible).

    Preserva byte a byte en el dict los registros anteriores. No hace
    backfill de partidos empezados ni completa líneas de ejecuciones futuras.
    """
    now = utc(now)
    rows = [dict(x) for x in previous]
    existing = {str(r.get("id")) for r in rows if r.get("id")}
    keys = {str(r.get("clave")) for r in rows if r.get("clave")}
    created, fixtures, rejected = 0, 0, 0
    for match in previews:
        fixture = str(match.get("id") or "")
        if not fixture or fixture in existing:
            continue
        try:
            start = utc(match["fecha_utc"])
            saved = utc(match["calculado_utc"])
            if not (now < start and saved < start and saved <= now + timedelta(minutes=1)):
                rejected += 1
                continue
            if not all(str(match.get(k) or "").strip() for k in ("liga", "local", "visitante")):
                rejected += 1
                continue
        except (KeyError, TypeError, ValueError):
            rejected += 1
            continue
        staged = []
        market_groups = match.get("mercados")
        if not isinstance(market_groups, dict):
            rejected += 1
            continue
        for category in CATEGORIES:
            candidates = market_groups.get(category, [])
            if not isinstance(candidates, list):
                continue
            # Se congelan exactamente las líneas PUBLICADAS para ese partido.
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    rejected += 1
                    continue
                validated = _valid_prediction(match, category, candidate)
                if validated is None:
                    rejected += 1
                    continue
                c, spec, probability, price, top = validated
                key = "|".join((fixture, category, c["mercado"], c["seleccion"]))
                if key in keys:
                    continue
                staged.append({
                    "clave": key, "id": fixture,
                    "liga": match["liga"], "local": match["local"],
                    "visitante": match["visitante"], "fecha_utc": match["fecha_utc"],
                    "archivado_utc": saved.isoformat(),
                    "mercado": c["mercado"], "seleccion": c["seleccion"],
                    "familia": category, "origen": c.get("origen", ""),
                    "nivel": c.get("nivel", ""),
                    "probabilidad": f"{probability:.6f}",
                    "cuota_justa": f"{price:.3f}",
                    "contrato": json.dumps(spec, ensure_ascii=False, sort_keys=True),
                    "estado": "PENDIENTE", "resultado": "", "valor_real": "",
                    "brier": "", "logloss": "", "partidos_fuente": "",
                    "categoria": category, "posicion_top3": top,
                    "estado_validacion": c.get("nivel", ""),
                })
                keys.add(key)
        if staged:
            rows.extend(staged)
            created += len(staged)
            fixtures += 1
            existing.add(fixture)
    return rows, {
        "nuevos": created, "partidos_nuevos": fixtures,
        "rechazadas": rejected, "total_archivado": len(rows),
    }


def _metrics(rows: list[dict]) -> dict:
    finals = [r for r in rows if r.get("estado") == "FINALIZADO"
              and str(r.get("resultado")) in ("0", "1")]
    n = len(finals)
    games = len({r["id"] for r in finals})
    counts = {
        "registradas": len(rows),
        "pendientes": sum(x.get("estado")=="PENDIENTE" for x in rows),
        "sin_marcador": sum(x.get("estado")=="RESULTADO_NO_DISPONIBLE" for x in rows),
        "sin_estadistica": sum(x.get("estado")=="ESTADISTICA_NO_DISPONIBLE" for x in rows),
    }
    if not n:
        return {
            **counts, "muestra": 0, "partidos_unicos": 0, "aciertos": 0,
            "acierto_pct": None, "probabilidad_media_pct": None,
            "brier": None, "logloss": None, "ece": None,
            "sesgo_pct": None, "calibracion": [],
            "brier_equilibrado_partidos":None,
            "logloss_equilibrado_partidos":None,
            "sesgo_equilibrado_pct":None,
            "partidos_para_umbral":MIN_INDEPENDENT_GAMES,
            "estado_calibracion":"NO_EVALUABLE",
            "evidencia": "SIN_MUESTRA",
        }
    ps = [float(r["probabilidad"]) for r in finals]
    ys = [int(r["resultado"]) for r in finals]
    rate = sum(ys) / n
    avg = sum(ps) / n
    brier = sum((p-y)**2 for p,y in zip(ps, ys)) / n
    loss = sum(-log(max(1e-12, p if y else 1-p))
               for p,y in zip(ps,ys)) / n
    # El modelo puede publicar MUCHAS líneas del mismo partido. Para
    # evaluar fiabilidad sin sobreponderar uno solo, primero promediamos
    # errores de cada encuentro y después promediamos encuentros.
    by_game=defaultdict(list)
    for row,p,y in zip(finals,ps,ys):
        by_game[row["id"]].append((p,y))
    balanced_brier=sum(
        sum((p-y)**2 for p,y in vals)/len(vals)
        for vals in by_game.values()
    )/games
    balanced_logloss=sum(
        sum(-log(max(1e-12,p if y else 1-p)) for p,y in vals)/len(vals)
        for vals in by_game.values()
    )/games
    balanced_bias=sum(
        sum(y-p for p,y in vals)/len(vals)
        for vals in by_game.values()
    )/games
    calibration = []
    for lo,hi in BINS:
        data = [(p,y,row["id"]) for row,p,y in zip(finals,ps,ys)
                if lo <= p < hi or (hi == 1 and p == 1)]
        if not data:
            continue
        size = len(data)
        calibration.append({
            "rango": f"{int(lo*100)}–{int(hi*100)}%",
            "muestra": size,
            "partidos_unicos":len({ident for _,_,ident in data}),
            "probabilidad_media_pct": round(100 * sum(p for p,_,_ in data)/size, 2),
            "acierto_pct": round(100 * sum(y for _,y,_ in data)/size, 2),
        })
    ece = sum(item["muestra"]/n *
              abs(item["probabilidad_media_pct"]-item["acierto_pct"])/100
              for item in calibration)
    evidence = "LIMITADA" if games < 30 else "PRELIMINAR" if games < 100 else "DESCRIPTIVA"
    return {
        **counts, "muestra": n, "partidos_unicos": games, "aciertos": sum(ys),
        "acierto_pct": round(rate*100,2),
        "probabilidad_media_pct": round(avg*100,2),
        "brier": round(brier,6), "logloss": round(loss,6),
        "ece": round(ece,6), "sesgo_pct": round(100*(rate-avg),2),
        "brier_equilibrado_partidos":round(balanced_brier,6),
        "logloss_equilibrado_partidos":round(balanced_logloss,6),
        "sesgo_equilibrado_pct":round(100*balanced_bias,2),
        "partidos_para_umbral":max(0,MIN_INDEPENDENT_GAMES-games),
        "estado_calibracion":("INSUFICIENTES_PARTIDOS" if games<MIN_INDEPENDENT_GAMES
                               else "EVALUABLE_DESCRIPTIVO"),
        "calibracion": calibration, "evidencia": evidence,
    }


def audit_future_markets(rows: list[dict], now: datetime) -> dict:
    """Sin backtesting, entrenamiento ni cuotas ejecutadas; solo snapshots previos."""
    group_market = defaultdict(list)
    group_league = defaultdict(list)
    group_pair = defaultdict(list)
    group_quality = defaultdict(list)
    group_pair_quality = defaultdict(list)
    group_pair_registration = defaultdict(list)
    group_registration = defaultdict(list)
    for r in rows:
        market = r.get("categoria") or "desconocido"
        league = r.get("liga") or "desconocida"
        quality = r.get("nivel") or "SIN_CLASIFICAR"
        group_market[market].append(r)
        group_league[league].append(r)
        group_pair[(market, league)].append(r)
        group_quality[(market, quality)].append(r)
        group_pair_quality[(market, league, quality)].append(r)
        mode = "top3" if str(r.get("posicion_top3") or "").strip() in ("1","2","3") else "adicionales"
        group_pair_registration[(market, league, mode)].append(r)
        group_registration[(market, mode)].append(r)
    good = [r for r in rows if r.get("estado") == "FINALIZADO"]
    # Muestra de auditoría visible sin cargar el CSV completo en el navegador.
    recent = sorted(
        (r for r in rows if r.get("estado") != "PENDIENTE"),
        key=lambda x: (x.get("fecha_utc",""),x.get("clave","")),
        reverse=True,
    )[:240]
    visible = [{
        "clave": r.get("clave"), "id": r.get("id"),
        "liga": r.get("liga"), "local": r.get("local"),
        "visitante": r.get("visitante"), "fecha_utc": r.get("fecha_utc"),
        "categoria": r.get("categoria"), "seleccion": r.get("seleccion"),
        "probabilidad": r.get("probabilidad"), "nivel": r.get("nivel"),
        "posicion_top3": r.get("posicion_top3"),
        "estado": r.get("estado"), "resultado": r.get("resultado"),
        "valor_real": r.get("valor_real"), "partidos_fuente": r.get("partidos_fuente"),
    } for r in recent]
    return {
        "version": VERSION, "calculado_utc": utc(now).isoformat(),
        "origen": "Archivo de pronósticos publicado antes de cada inicio (sin backfill)",
        "registradas": len(rows), "partidos_archivados": len({r["id"] for r in rows}),
        "finalizadas": len(good),
        "pendientes": sum(r.get("estado") == "PENDIENTE" for r in rows),
        "sin_marcador": sum(r.get("estado") == "RESULTADO_NO_DISPONIBLE" for r in rows),
        "sin_estadistica": sum(r.get("estado") == "ESTADISTICA_NO_DISPONIBLE" for r in rows),
        "excluidas": sum(str(r.get("estado", "")).startswith("EXCLUIDO") for r in rows),
        "global": _metrics(rows),
        "ultimas_evaluaciones": visible,
        "por_mercado": {k: _metrics(v) for k,v in sorted(group_market.items())},
        "por_liga": {k: _metrics(v) for k,v in sorted(group_league.items())},
        "por_mercado_liga": {
            cat: {league: _metrics(group_pair[(cat,league)])
                  for league in sorted({x[1] for x in group_pair if x[0]==cat})}
            for cat in sorted(group_market)},
        "por_mercado_calidad": {
            cat: {quality: _metrics(group_quality[(cat,quality)])
                  for quality in sorted({x[1] for x in group_quality if x[0]==cat})}
            for cat in sorted(group_market)},
        "por_mercado_liga_calidad": {
            cat: {
                league: {
                    quality: _metrics(group_pair_quality[(cat, league, quality)])
                    for quality in sorted({x[2] for x in group_pair_quality
                                           if x[0]==cat and x[1]==league})
                }
                for league in sorted({x[1] for x in group_pair_quality if x[0]==cat})
            }
            for cat in sorted(group_market)
        },
        "por_mercado_registro": {
            cat: {mode: _metrics(group_registration[(cat,mode)])
                  for mode in ("top3","adicionales")}
            for cat in sorted(group_market)
        },
        "por_mercado_liga_registro": {
            cat: {
                league: {mode: _metrics(group_pair_registration[(cat,league,mode)])
                         for mode in ("top3","adicionales")}
                for league in sorted({x[1] for x in group_pair if x[0]==cat})
            }
            for cat in sorted(group_market)
        },
        "calidad": {
            "limitacion": "Múltiples líneas del mismo partido están correlacionadas; "
                         "partidos_unicos es la cobertura independiente de encuentros.",
            "cuota": "Sin precios de casas: no se informa ROI de este seguimiento.",
            "fuentes": "Marcadores y conteos verificados, sin sustituir estadísticas ausentes por cero.",
            "prospectivo": "No incluye partidos previos a la primera ejecución de la Fase 4.",
            "independencia": "Se muestran Brier/logloss equilibrados por partido. Cada encuentro pesa igual aunque tenga distinto número de pronósticos.",
            "umbrales": f"Con menos de {MIN_INDEPENDENT_GAMES} partidos únicos no se considera evaluable la calibración. El umbral es descriptivo, no prueba ventaja ni ROI.",
        },
        "advertencia": "La calibración requiere muestras amplias de partidos distintos; "
                       "un acierto alto no demuestra ventaja financiera ni predice éxito.",
    }


def settle_future_markets(rows: list[dict], histories: dict, now: datetime) -> list[dict]:
    """Mismo motor que el Top 3, registros separados para evitar contaminación."""
    settled = settle(rows, histories, now)
    # market_prospective.settle no debe tocar campos de categorización.
    if len(settled) != len(rows):
        raise ValueError("Liquidación incompleta")
    return settled
