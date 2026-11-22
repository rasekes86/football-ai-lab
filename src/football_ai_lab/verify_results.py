"""Verifica partidos finalizados sin generar picks, cuotas ni backtests.

Reutiliza el motor de resultados y los snapshots prospectivos congelados.
Solo escribe archivos de seguimiento derivados; nunca los historico_*.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from .pipeline import read_csv, write_csv
from .sources import LEAGUES, load_history
from .verified_results import augment_results
from .postmatch_stats import enrich_statistics
from .postmatch_breakdown import build_breakdown
from .market_prospective import FIELDS as PICK_FIELDS, settle, summary as pick_summary
from .prospective import TRACK_FIELDS, evaluate as eval_legacy, summarize as sum_legacy
from .future_market_audit import FIELDS as FUTURE_FIELDS, settle_future_markets, audit_future_markets
from .fourth_reference import evaluate as eval_fourth
from .value_watchlist import OFFER_FIELDS, evaluate as eval_offers, summary as sum_offers, active_top3, markdown
from .top3_odds import FIELDS as TOP3_FIELDS, settle_top3_quotes, top3_odds_report
from .telegram_3plus1 import _collect, _date, _finished
from .telegram_notify import send

ROOT = Path("output")
LOG = logging.getLogger(__name__)
OUTPUTS = (
 "seguimiento.csv", "evaluacion_real.json", "seguimiento_selecciones.csv",
 "evaluacion_selecciones.json", "desglose_postpartido.json",
 "estadisticas_finales_verificadas.json", "seguimiento_oportunidades_150.csv",
 "evaluacion_oportunidades_150.json", "oportunidades_150.md",
 "seguimiento_adicionales_teoricas.csv", "seguimiento_cuotas_top3.csv",
 "evaluacion_cuotas_top3.json", "seguimiento_mercados_futuros.csv",
 "fiabilidad_mercados_futuros.json", "verificacion_resultados_telegram.json",
)

def read_json(path):
 try:
  result=json.loads(path.read_text(encoding="utf-8"))
  return result if isinstance(result,dict) else {}
 except (OSError, ValueError):
  return {}

def write_json(path, payload):
 path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def keep_verified(new, previous, key):
 """Nunca convertir un acierto/fallo comprobado en fallo por caída del proveedor."""
 old={r.get(key):r for r in previous if r.get(key) and
      r.get("estado")=="FINALIZADO" and r.get("resultado") in ("0","1")}
 out=[]
 for row in new:
  before=old.get(row.get(key))
  if before and (row.get("estado")!="FINALIZADO"
                 or row.get("resultado")!=before.get("resultado")):
   if row.get("estado")=="FINALIZADO":
    LOG.warning("Resultado contradictorio para %s: conservar hasta auditoría",row.get(key))
   out.append(dict(before))
  else:
   out.append(row)
 return out

def selected(top_rows, extra_rows):
 top=_collect(top_rows,extra=False)
 extra=_collect(extra_rows,extra=True)
 extras={r["id"]:r for r in extra}
 norm=lambda t:" ".join(str(t or "").casefold().split())
 top=[r for r in top if not (r["id"] in extras and
      norm(r.get("mercado"))==norm(extras[r["id"]].get("mercado")) and
      norm(r.get("seleccion"))==norm(extras[r["id"]].get("seleccion")))]
 return top,extra

def make_summary(top, extra, prior_top, prior_extra, now):
 top,extra=selected(top,extra)
 old_top,old_extra=selected(prior_top,prior_extra)
 prior={kind+":"+r["clave"] for kind,rows in
        (("top",old_top),("extra",old_extra)) for r in rows if _finished(r,now)}
 start=now-timedelta(days=7)
 def count(rows):
  recent=[r for r in rows if (dt:=_date(r.get("fecha_utc"))) and start<=dt<now]
  done=[r for r in recent if _finished(r,now)]
  wins=sum(r["resultado"]=="1" for r in done)
  return {"registradas":len(recent),"aciertos":wins,
          "fallos":len(done)-wins,"pendientes":len(recent)-len(done)}
 new=sum(_finished(r,now) and kind+":"+r["clave"] not in prior for kind,rows
         in (("top",top),("extra",extra)) for r in rows)
 a,b=count(top),count(extra)
 stamp=now.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M")
 lines=["✅ Football AI Lab · Verificación terminada",
        "Hora: "+stamp+" (Madrid)",
        "Nuevas selecciones liquidadas: "+str(new),"",
        "Últimos 7 días · Top 3 y adicional >1,50",
        "🎯 Top 3: "+str(a["aciertos"])+" aciertos · "+str(a["fallos"])+" fallos · "+str(a["pendientes"])+" pendientes",
        "💶 Adicional: "+str(b["aciertos"])+" aciertos · "+str(b["fallos"])+" fallos · "+str(b["pendientes"])+" pendientes","",
        "Sin marcador o estadística verificados = pendiente, nunca fallo.",
        "Rentabilidad y cuotas, si figuran, son simulaciones.",
        "https://rasekes86.github.io/football-ai-lab/#performance"]
 return {"version":1,"verificado_utc":now.isoformat(),"nuevas_liquidaciones":new,
         "top3":a,"adicional":b,"mensaje":"\n".join(lines)}

def verify(root=ROOT,now=None,loader=load_history,marks=augment_results,stats=enrich_statistics):
 now=now or datetime.now(timezone.utc)
 root=Path(root)
 if now.tzinfo is None: raise ValueError("Fecha UTC obligatoria")
 top=read_csv(root/"historico_selecciones.csv")
 extra=read_csv(root/"historico_oportunidades_150.csv")
 fourth=read_csv(root/"historico_adicionales_teoricas.csv")
 future=read_csv(root/"historico_mercados_futuros.csv")
 legacy=read_csv(root/"historico_predicciones.csv")
 if not top and not extra: raise RuntimeError("No existen pronósticos históricos; no se sobrescribe nada")
 old_top=read_csv(root/"seguimiento_selecciones.csv")
 old_extra=read_csv(root/"seguimiento_oportunidades_150.csv")
 base={code:loader(code,now.date()) for code in LEAGUES}
 if not any(base.values()): raise RuntimeError("Fuentes no disponibles; se conserva el resultado anterior")
 primary=top+extra+fourth
 base,mark_info=marks(base,legacy+primary+future,now)
 base,stats_info,cache=stats(base,legacy+primary+future,now,
                            cache_path=root/"estadisticas_finales_verificadas.json",
                            primary_archived=primary)
 top_tr=keep_verified(settle(top,base,now),old_top,"clave")
 extra_tr,_=eval_offers(extra,base,now)
 extra_tr=keep_verified(extra_tr,old_extra,"clave")
 fourth_tr=keep_verified(eval_fourth(fourth,base,now),
                         read_csv(root/"seguimiento_adicionales_teoricas.csv"),"clave")
 future_tr=keep_verified(settle_future_markets(future,base,now),
                         read_csv(root/"seguimiento_mercados_futuros.csv"),"clave")
 legacy_tr=keep_verified(eval_legacy(legacy,base,now),read_csv(root/"seguimiento.csv"),"id")
 market_report=pick_summary(active_top3(top_tr,extra_tr),now)
 market_report["top3_original_registradas"]=len(top_tr)
 market_report["top3_promovidas_a_adicional"]=len(top_tr)-len(active_top3(top_tr,extra_tr))
 extra_report=sum_offers(extra_tr,now)
 prior_extra_report=read_json(root/"evaluacion_oportunidades_150.json")
 if "seleccion_automatica" in prior_extra_report:
  extra_report["seleccion_automatica"]=prior_extra_report["seleccion_automatica"]
 future_report=audit_future_markets(future_tr,now)
 old_future=read_json(root/"fiabilidad_mercados_futuros.json")
 if "registro_nuevo" in old_future:
  future_report["registro_nuevo"]=old_future["registro_nuevo"]
 priced=read_csv(root/"historico_cuotas_top3.csv")
 priced_tr=settle_top3_quotes(priced,top_tr,extra_tr+fourth_tr,now)
 priced_report=top3_odds_report(top,priced,priced_tr,now,
                               read_json(root/"estado_consultas_cuotas.json"))
 message=make_summary(top_tr,extra_tr,old_top,old_extra,now)
 message["fuentes"]={"objetivos":mark_info["objetivos"],
                     "sin_marcador":mark_info["sin_marcador"],
                     "estadisticas_completas":stats_info["completos"],
                     "estadisticas_objetivo":stats_info["objetivos_conteo"]}
 # Únicamente resultados derivados; los pronósticos, cuotas y archivos históricos siguen intactos.
 write_csv(root/"seguimiento_selecciones.csv",PICK_FIELDS,top_tr)
 write_csv(root/"seguimiento_oportunidades_150.csv",OFFER_FIELDS,extra_tr)
 write_csv(root/"seguimiento_adicionales_teoricas.csv",OFFER_FIELDS,fourth_tr)
 write_csv(root/"seguimiento_mercados_futuros.csv",FUTURE_FIELDS,future_tr)
 write_csv(root/"seguimiento.csv",TRACK_FIELDS,legacy_tr)
 write_csv(root/"seguimiento_cuotas_top3.csv",TOP3_FIELDS,priced_tr)
 write_json(root/"evaluacion_selecciones.json",market_report)
 write_json(root/"evaluacion_oportunidades_150.json",extra_report)
 write_json(root/"fiabilidad_mercados_futuros.json",future_report)
 write_json(root/"evaluacion_real.json",sum_legacy(legacy_tr,now))
 write_json(root/"evaluacion_cuotas_top3.json",priced_report)
 write_json(root/"desglose_postpartido.json",build_breakdown(top_tr,base,now,stats_info))
 write_json(root/"estadisticas_finales_verificadas.json",cache)
 (root/"oportunidades_150.md").write_text(markdown(extra_tr,extra_report),encoding="utf-8")
 write_json(root/"verificacion_resultados_telegram.json",message)
 return message

def main(argv=None):
 p=argparse.ArgumentParser()
 p.add_argument("--notify",action="store_true")
 args=p.parse_args(argv)
 logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
 if args.notify:
  msg=read_json(ROOT/"verificacion_resultados_telegram.json").get("mensaje")
  token=os.environ.get("TELEGRAM_BOT_TOKEN","")
  chat=os.environ.get("TELEGRAM_CHAT_ID","")
  if not msg or not token or not chat: raise SystemExit("Faltan mensaje o credenciales Telegram")
  try:
   if not send(msg,token,chat): raise RuntimeError("Proveedor no confirmó envío")
  except Exception as exc:
   raise SystemExit("No se pudo entregar el resumen: "+type(exc).__name__) from None
  print("Resumen entregado por Telegram.")
 else:
  result=verify()
  print("Verificación completada. Nuevas selecciones:",result["nuevas_liquidaciones"])

if __name__=="__main__":main()
