"""Fase 7: resúmenes opcionales de Telegram con prevención de duplicados.

Sin Bot API ni credenciales para las pruebas. Solo se transmite por una acción
explícitamente habilitada y con secretos de GitHub. No envía recomendaciones de
apuestas: reporta estimaciones experimentales y liquidaciones verificadas.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .future_market_audit import CATEGORIES
from .telegram_notify import send

MADRID = ZoneInfo("Europe/Madrid")
STATE_PATH = Path("output/estado_alertas_telegram.json")
MAX_MESSAGE = 3900
QUALITY = {
    "all": None,
    "top3": "top3",
    "audited": "BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA",
    "exploratory": "EXPLORATORIO_NO_VALIDADO",
    "uncalibrated": "MODELO_NO_CALIBRADO",
}
SHORT = {
    "corners": "Córners", "shots": "Tiros", "on_target": "Tiros a puerta",
    "yellow": "Amarillas", "goals": "Goles", "result": "1X2",
    "double": "Doble oportunidad", "btts": "Ambos marcan",
}


def _clean(text, size=100):
    raw = re.sub(r"[\x00-\x1f\x7f]+", " ", str(text or ""))
    return re.sub(r"\s+", " ", raw).strip()[:size]


def _time(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def _integer(value, default, lo, hi):
    try:
        n = int(str(value))
        return n if lo <= n <= hi else default
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Settings:
    markets: frozenset[str] = frozenset(CATEGORIES)
    leagues: frozenset[str] = frozenset()
    min_probability: float = 0.65
    quality: str = "all"
    horizon_hours: int = 72
    result_days: int = 21
    max_upcoming: int = 6
    max_results: int = 8

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        raw_markets = env.get("TELEGRAM_ALERT_MARKETS", "")
        markets = frozenset(x.strip().lower() for x in raw_markets.split(",") if x.strip())
        markets = markets & set(CATEGORIES) if markets else frozenset(CATEGORIES)
        leagues = frozenset(x.strip().casefold() for x in
                            env.get("TELEGRAM_ALERT_LEAGUES", "").split(",") if x.strip())
        try:
            prob = float(env.get("TELEGRAM_ALERT_MIN_PROBABILITY", "0.65"))
        except (TypeError, ValueError):
            prob = 0.65
        if not 0 < prob < 1:
            prob = 0.65
        quality = env.get("TELEGRAM_ALERT_QUALITY", "all").strip().lower()
        return cls(
            markets=frozenset(markets), leagues=leagues,
            min_probability=prob,
            quality=quality if quality in QUALITY else "all",
            horizon_hours=_integer(env.get("TELEGRAM_ALERT_HORIZON_HOURS", "72"),72,1,168),
            result_days=_integer(env.get("TELEGRAM_ALERT_RESULTS_DAYS", "21"),21,1,30),
            max_upcoming=_integer(env.get("TELEGRAM_ALERT_MAX_UPCOMING", "6"),6,1,12),
            max_results=_integer(env.get("TELEGRAM_ALERT_MAX_RESULTS", "8"),8,1,14),
        )


def _number(value):
    try:
        p = float(value)
        return p if 0 < p < 1 else None
    except (ValueError, TypeError):
        return None


def _quality(row, config):
    if config.quality == "all":
        return True
    if config.quality == "top3":
        return str(row.get("posicion_top3") or "") in ("1", "2", "3")
    return row.get("nivel") == QUALITY[config.quality]


def _eligible(row, market, league, config):
    p = _number(row.get("probabilidad"))
    return (market in config.markets and
            (not config.leagues or str(league).casefold() in config.leagues) and
            p is not None and p >= config.min_probability and
            _quality(row, config))


def _rank(p):
    """Prioridad de trazabilidad, NO señal de valor económico."""
    return (
        0 if str(p.get("posicion_top3") or "") in ("1", "2", "3") else
        1 if p.get("nivel") == QUALITY["audited"] else
        2 if p.get("nivel") == QUALITY["exploratory"] else 3,
        -float(p["probabilidad"]),
        str(p.get("seleccion") or ""),
    )


def upcoming(data: dict, config: Settings, now: datetime):
    now = now.astimezone(timezone.utc)
    until = now + timedelta(hours=config.horizon_hours)
    found = []
    seen = set()
    for match in data.get("partidos") or []:
        if not isinstance(match, dict) or not match.get("id") or match["id"] in seen:
            continue
        kickoff = _time(match.get("fecha_utc"))
        if kickoff is None or not (now < kickoff <= until):
            continue
        league = str(match.get("liga") or "")
        picks = []
        for market, rows in (match.get("mercados") or {}).items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict) and _eligible(row, market, league, config):
                    picks.append((market,row))
        seen.add(match["id"])
        if picks:
            market, pick = sorted(picks,key=lambda x:_rank(x[1]))[0]
            found.append({
                "id": match["id"], "league": league,
                "home": _clean(match.get("local")), "away": _clean(match.get("visitante")),
                "kickoff": kickoff, "market": market, "pick": pick,
            })
    return sorted(found,key=lambda x:(x["kickoff"],x["id"]))[:config.max_upcoming]


def _valid_archive(row):
    start = _time(row.get("fecha_utc"))
    saved = _time(row.get("archivado_utc"))
    return start is not None and saved is not None and saved < start


def new_results(rows: list[dict], state: dict, config: Settings, now: datetime):
    now = now.astimezone(timezone.utc)
    earliest = now - timedelta(days=config.result_days)
    seen = set(state.get("reported_keys") or [])
    found = []
    for row in rows:
        if not isinstance(row,dict) or not row.get("clave"):
            continue
        if str(row.get("estado")) != "FINALIZADO" or str(row.get("resultado")) not in ("0","1"):
            continue  # Nunca inventar resultados sin verificar.
        if row["clave"] in seen or not _valid_archive(row):
            continue
        kickoff = _time(row.get("fecha_utc"))
        if kickoff is None or not earliest <= kickoff < now:
            continue
        if not _eligible(row,row.get("categoria"),row.get("liga"),config):
            continue
        found.append((kickoff,row))
    found.sort(key=lambda pair:(-pair[0].timestamp(),str(pair[1]["clave"])))
    return [row for _,row in found[:config.max_results]]


def _pending(rows, config, now):
    earliest = now.astimezone(timezone.utc) - timedelta(days=2)
    result = {"ESTADISTICA_NO_DISPONIBLE":0,"RESULTADO_NO_DISPONIBLE":0}
    for row in rows:
        status=row.get("estado")
        when=_time(row.get("fecha_utc"))
        if status not in result or when is None or when < earliest or when > now:
            continue
        if _eligible(row,row.get("categoria"),row.get("liga"),config) and _valid_archive(row):
            result[status]+=1
    return result


def _format_kickoff(value):
    return value.astimezone(MADRID).strftime("%d/%m %H:%M")


def _quality_label(row):
    q = row.get("nivel")
    if q == QUALITY["audited"]:
        return "Backtest retrospectivo; sin validación prospectiva suficiente"
    if q == QUALITY["exploratory"]:
        return "Exploratorio"
    return "Modelo no calibrado"


def digest(data, reviewed, state, config: Settings, now: datetime):
    """Mensaje limitado, con claves marcadas solo si aparecen realmente en él."""
    now = now.astimezone(timezone.utc)
    today = now.astimezone(MADRID).date().isoformat()
    daily = state.get("last_daily_madrid") != today
    selected = upcoming(data, config, now) if daily else []
    final = new_results(reviewed, state, config, now)
    if not daily and not final:
        return "", dict(state), {"enviar":False, "motivo":"sin novedades"}
    parts = [
        "⚽ Football AI Lab · Fase 7" if daily else "🧾 Football AI Lab · Nuevos resultados",
        "Fecha: "+now.astimezone(MADRID).strftime("%d/%m/%Y %H:%M")+" (Madrid)",
    ]
    footer = [
        "Datos experimentales. Probabilidad ≠ rentabilidad. No son apuestas recomendadas.",
        "https://rasekes86.github.io/football-ai-lab/#radar",
    ]
    def fits(line, reserve=0):
        return len("\n\n".join([*parts, line, *footer])) + reserve <= MAX_MESSAGE
    if daily:
        parts.append(f"🔎 Próximas {config.horizon_hours} h · p mínima {config.min_probability*100:.0f}%")
        if not selected:
            parts.append("No hay pronósticos futuros que cumplan los filtros en este periodo.")
    kept_upcoming = 0
    for item in selected:
        p=item["pick"]
        label=SHORT.get(item["market"],item["market"])
        line=(
            f"• {_format_kickoff(item['kickoff'])} · {_clean(item['home'],45)} – "
            f"{_clean(item['away'],45)} ({_clean(item['league'],30)})\n"
            f"  {_clean(label,36)} · {_clean(p.get('seleccion'),95)}"
            f" · {float(p['probabilidad'])*100:.1f}% estimado\n"
            f"  {_quality_label(p)}"
        )
        # Dejar sitio a varias liquidaciones antes que llenar el mensaje
        # exclusivamente con pronósticos próximos.
        if fits(line, reserve=900 if final else 0):
            parts.append(line)
            kept_upcoming+=1
        else:
            break
    included=[]
    if final:
        if fits("✅ Liquidaciones nuevas verificadas:"):
            parts.append("✅ Liquidaciones nuevas verificadas:")
        for row in final:
            sign="✓" if str(row["resultado"])=="1" else "✗"
            when=_time(row["fecha_utc"])
            line=(
                f"{sign} {_format_kickoff(when)} {_clean(row.get('local'),35)} – "
                f"{_clean(row.get('visitante'),35)} · {_clean(row.get('seleccion'),80)}"
                f" ({'acierto' if sign=='✓' else 'fallo'})"
            )
            if fits(line, reserve=200 if daily else 0):
                parts.append(line)
                included.append(row)
            else:
                break  # Solo marcar como notificados los que realmente aparecen.
        if len(included)<len(final) and fits("Hay más resultados pendientes de enviar."):
            parts.append("Hay más resultados pendientes de enviar.")
    elif daily:
        parts.append("🧾 Sin nuevas selecciones liquidadas desde el último aviso.")
    if daily:
        missed=_pending(reviewed,config,now)
        if any(missed.values()):
            line=("⏳ Sin verificar (NO son fallos): "
                  f"{missed['ESTADISTICA_NO_DISPONIBLE']} estadísticas, "
                  f"{missed['RESULTADO_NO_DISPONIBLE']} marcadores.")
            if fits(line):
                parts.append(line)
    msg="\n\n".join([*parts,*footer])
    if len(msg)>MAX_MESSAGE:
        raise ValueError("Mensaje más largo que el límite permitido")
    merged=dict(state)
    merged["version"]=2
    merged["last_delivery_utc"]=now.isoformat()
    if daily:
        merged["last_daily_madrid"]=today
    keys=list(dict.fromkeys([*state.get("reported_keys",[]),
                              *[str(r["clave"]) for r in included]]))
    merged["reported_keys"]=keys[-10000:]
    return msg,merged,{
        "enviar":True,"diario":daily,
        "proximos":kept_upcoming,"resultados":len(included),
    }


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError,ValueError,OSError):
        return {}


def _load_csv(path):
    try:
        with Path(path).open(encoding="utf-8-sig",newline="") as handle:
            return list(csv.DictReader(handle))
    except (FileNotFoundError,OSError):
        return []


def main(argv=None, env=None, now=None, sender=send):
    cli=argparse.ArgumentParser(description="Alertas de seguimiento Football AI Lab")
    cli.add_argument("--preview",action="store_true",help="Ver resumen sin enviar ni guardar estado")
    args=cli.parse_args(argv)
    env=os.environ if env is None else env
    now=now or datetime.now(timezone.utc)
    config=Settings.from_env(env)
    state=_load_json(STATE_PATH)
    data=_load_json(Path("output/pronosticos_mercados_futuros.json"))
    reviewed=_load_csv(Path("output/seguimiento_mercados_futuros.csv"))
    message,next_state,detail=digest(data,reviewed,state,config,now)
    if args.preview:
        print(message or "Sin mensajes nuevos para enviar.")
        return detail
    enabled=str(env.get("TELEGRAM_ALERTS_ENABLED","")).lower() in ("1","true","yes")
    token=str(env.get("TELEGRAM_BOT_TOKEN","")).strip()
    chat=str(env.get("TELEGRAM_CHAT_ID","")).strip()
    if not enabled or not token or not chat:
        print("Telegram Fase 7 desactivado; no se envía ni se guarda estado.")
        return {"enviar":False,"motivo":"no configurado"}
    if not message:
        print("Telegram Fase 7: sin novedades, no se envía.")
        return detail
    try:
        delivered=sender(message,token,chat)
        if not delivered:
            print("Telegram Fase 7: proveedor no confirmó la entrega; sin actualizar estado.")
            return {"enviar":False,"motivo":"entrega no confirmada"}
        STATE_PATH.parent.mkdir(parents=True,exist_ok=True)
        STATE_PATH.write_text(json.dumps(next_state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"Telegram Fase 7: resumen entregado ({detail['proximos']} próximos, "
              f"{detail['resultados']} liquidaciones); estado guardado sin credenciales.")
        return detail
    except Exception as exc:
        # La excepción del proveedor puede contener la URL del bot y su token.
        print("Telegram Fase 7: no entregado ("+type(exc).__name__+"); secretos protegidos.")
        return {"enviar":False,"motivo":"error de envío"}


if __name__=="__main__":
    outcome=main()
    if outcome.get("motivo") in ("error de envío","entrega no confirmada"):
        raise SystemExit(1)
