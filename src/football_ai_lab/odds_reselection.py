"""Revisión excepcional y rastreable de las adicionales FUTURAS.

Autorizada de manera puntual: cambiar el criterio de EV máximo a mayor
probabilidad estadística dentro de los filtros vigentes. No recupera cuotas
de Internet, no reescribe resultados pasados, no oculta la selección anterior.
La evidencia son comparaciones API registradas ANTES de esta revisión.
Después de ejecutarse una vez, las adicionales vuelven a ser inmutables.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import logging

from .pipeline import read_csv, write_csv
from .value_watchlist import (
    API, FIELDS, _compared_candidates, _utc, markdown, selection_audit, summary,
)

LOG = logging.getLogger(__name__)
MARKER = "historico_revisiones_adicionales_150.json"


def read_json(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback
    except (OSError, ValueError):
        return fallback


def plan_revisions(offers, matches, comparison, top3, now):
    """Solo propuestas más probables y aún prepartido, sin asumir cuota actual."""
    snapshot = _utc(comparison["capturado_utc"])
    if snapshot > now or now - snapshot > timedelta(days=7):
        raise ValueError("La comparacion historica no esta disponible en una ventana auditable")
    by_id = {m.get("id"):m for m in matches if m.get("id")}
    pending = {}
    for old in offers:
        if old.get("tipo_cuota") != API or old.get("estado") != "PENDIENTE":
            continue
        try:
            if not snapshot < _utc(old["fecha_utc"]) or not now < _utc(old["fecha_utc"]):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        match = by_id.get(old.get("id"))
        if not match or (match.get("fecha_utc") != old.get("fecha_utc") or
                         match.get("local") != old.get("local") or
                         match.get("visitante") != old.get("visitante") or
                         match.get("liga") != old.get("liga")):
            continue
        # El snapshot de comparación es anterior al análisis actual. No
        # atribuimos a la nueva cuota el timestamp de ese nuevo análisis.
        pending[old["id"]] = {**match, "calculado_utc":""}
    best = {row["id"]:row for row in _compared_candidates(
        list(pending.values()), comparison, snapshot, top3)}
    replacements = {}
    audit = []
    for old in offers:
        if old.get("id") not in pending:
            continue
        proposal = best.get(old.get("id"))
        if proposal is None or old.get("id") in replacements:
            continue
        if proposal["clave"] == old.get("clave"):
            continue
        if float(proposal["probabilidad"]) <= float(old["probabilidad"]) + 0.000001:
            continue
        if _utc(proposal["fecha_cuota_utc"]) > now:
            continue
        proposal["archivado_utc"] = now.isoformat()
        # El registro anterior NO se pierde: está en el fichero de revisiones.
        audit.append({
            "id": old["id"], "partido": old["local"]+" - "+old["visitante"],
            "anterior": dict(old), "nueva": dict(proposal),
            "observacion_cuota_utc": proposal["fecha_cuota_utc"],
            "nota":("Precio prepartido observado en una captura anterior, NO "
                    "cotizacion actual ni precio garantizado en el momento de revision"),
        })
        replacements[old["id"]] = proposal
    return replacements, audit


def run(target=Path("output"), now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now debe tener zona horaria")
    marker = target/MARKER
    if marker.is_file():
        LOG.info("Revision excepcional ya aplicada, no se reabre ninguna cuota")
        return {"estado":"YA_APLICADA","revisiones":0}
    compared = read_json(target/"comparacion_cuotas_reales.json", {})
    matches = read_json(target/"pronosticos_mercados_futuros.json", {}).get("partidos") or []
    offers = read_csv(target/"historico_oportunidades_150.csv")
    top3 = read_csv(target/"historico_selecciones.csv")
    tracked = read_csv(target/"seguimiento_oportunidades_150.csv")
    if not compared.get("comparaciones") or not matches or not offers or not tracked:
        raise RuntimeError("Falta un snapshot verificable o un historial; no se modifica nada")
    replacements, events = plan_revisions(offers, matches, compared, top3, now)
    updated = [replacements.get(r.get("id"), r) for r in offers]
    # El seguimiento es un estado derivado; nunca se cambia una fila
    # liquidada, y cada nueva seleccion sustituye solo la anterior pendiente.
    revised_tracking = [
        replacements[r["id"]] if r.get("id") in replacements and
        r.get("clave") == next(x["anterior"]["clave"] for x in events if x["id"]==r["id"])
        and r.get("estado") == "PENDIENTE" else r
        for r in tracked
    ]
    report = {
        "version":1,"operacion":"REVISION_EXCEPCIONAL_SOLICITADA_POR_USUARIO",
        "revisado_utc":now.isoformat(),
        "snapshot_comparacion_utc":compared["capturado_utc"],
        "criterio":"Maximizar probabilidad estimada; cuota >1,50, EV>3%, calidad y mismo mercado exacto",
        "calibracion":"No demostrada: muestra prospectiva insuficiente",
        "sin_nuevas_peticiones_API":True,
        "revisiones":events,
        "cambiadas":len(events),
        "adicionales_que_permanecen":len(offers)-len(events),
        "nota":("Las observaciones API fueron capturadas antes de la revision. "
                "Las selecciones originales se preservan en este documento y "
                "quedan fuera de los balances activos. Despues de esta "
                "revision, las nuevas quedan bloqueadas definitivamente."),
    }
    if not events:
        raise RuntimeError("No se detecto una alternativa mas probable verificable; no se reescriben archivos")
    eval_report = summary(revised_tracking,now)
    eval_report["seleccion_automatica"] = selection_audit(
        offers,updated,matches,compared,now,top3)
    write_csv(target/"historico_oportunidades_150.csv",FIELDS,updated)
    write_csv(target/"seguimiento_oportunidades_150.csv",FIELDS,revised_tracking)
    (target/"evaluacion_oportunidades_150.json").write_text(
        json.dumps(eval_report,ensure_ascii=False,indent=2),encoding="utf-8")
    (target/"oportunidades_150.md").write_text(
        markdown(revised_tracking,eval_report),encoding="utf-8")
    marker.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    LOG.info("Revisadas %s adicionales: %s",len(events),
             ", ".join(x["partido"] for x in events))
    return {"estado":"REVISADAS","revisiones":len(events),
            "ids":[x["id"] for x in events]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    print(run())
