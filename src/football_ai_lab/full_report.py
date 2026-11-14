"""Informe prepartido unificado, reproducible y con trazabilidad de fuentes."""
from __future__ import annotations
from datetime import datetime,timezone
from .core import normalize_team
from .sources import LEAGUES

VERSION="dossier-0.8"
def _key(liga,fecha,local,visitante):
    return (liga,fecha,normalize_team(local),normalize_team(visitante))
def _fprob(value):
    try:return f"{100*float(value):.1f}%"
    except (TypeError,ValueError):return "No disponible"
def _number(value):
    return str(value).replace(".",",") if value is not None else "No disponible"
def _form(ctx):
    if not ctx:return "Historial insuficiente"
    recent=ctx.get("ultimos") or []
    r=" · ".join(x["resultado"] for x in recent)
    return f'{ctx.get("v",0)}V · {ctx.get("e",0)}E · {ctx.get("d",0)}D; secuencia: {r or "sin datos"}'
def _stats(ctx):
    if not ctx:return "Datos insuficientes"
    med=ctx.get("medias") or {}
    return ("Tiros "+_number(med.get("tiros"))+", a puerta "+_number(med.get("tiros_puerta"))+
            ", córners "+_number(med.get("corners"))+", amarillas "+_number(med.get("amarillas")))
def build_one(prediction:dict,context:dict|None,selection:dict|None,
              machina:dict|None=None,ml:dict|None=None,market:dict|None=None)->dict:
    """No inferir noticias, lesiones ni cotizaciones que no estén registradas."""
    m=selection or {}
    context=context or {}
    league_code=next((k for k,v in LEAGUES.items() if v[0]==prediction["liga"]),None)
    standings=((machina or {}).get("clasificaciones") or {}).get(league_code,{})
    standings=standings.get("top10",[])
    def table(team):
        name=normalize_team(team)
        found=next((x for x in standings if normalize_team(x["nombre"])==name),None)
        return {"posicion":found["posicion"],"puntos":found["puntos"],"jugados":found["jugados"]} if found else None
    ml_data=None
    if ml:
        ml_data={"victoria_local":_fprob(ml.get("ml_prob_local")),
                 "empate":_fprob(ml.get("ml_prob_empate")),
                 "victoria_visitante":_fprob(ml.get("ml_prob_visitante")),
                 "aviso":"XGBoost experimental; no mezclado con el modelo principal"}
    refs=[]
    if market and market.get("estado")=="REFERENCIA_INFERSPORTS_SIN_VALIDAR":
        refs.append({"proveedor":market.get("proveedor"),"fecha":market.get("fecha_cuota_utc"),
                     "estado":"Referencia de mercado sin margen, no cuota ofrecida"})
    if market and market.get("estado")=="COMPARACIÓN_SIN_VALIDAR":
        refs.append({"proveedor":market.get("proveedor"),"casa":market.get("casa"),
                     "fecha":market.get("fecha_cuota_utc"),
                     "estado":"Cuota externa ofrecida cuando fue observada; puede variar"})
    problems=list((context.get("calidad") or {}).get("motivos") or [])
    if not m.get("top_probabilidad"):problems.append("No hay selecciones elegibles")
    problems.extend(["xG auténtico no integrado en las probabilidades",
                     "Lesiones y alineaciones no incorporadas al predictor",
                     "No se ha demostrado ventaja frente a cuotas reales"])
    return {"version":VERSION,"id":prediction["id"],"fecha_utc":prediction["fecha_utc"],
            "liga":prediction["liga"],"local":prediction["local"],"visitante":prediction["visitante"],
            "creado_utc":prediction.get("fecha_analisis_utc"),
            "modelo":prediction.get("modelo"),
            "probabilidades":{"local":prediction["prob_local"],
                              "empate":prediction["prob_empate"],
                              "visitante":prediction["prob_visitante"],
                              "mas_2_5":prediction["prob_mas_2_5"]},
            "goles_estimados":{"local":prediction["goles_esperados_local"],
                               "visitante":prediction["goles_esperados_visitante"]},
            "equipos":{"local":{"clasificacion":table(prediction["local"]),
                                "reciente":context.get("local_datos")},
                       "visitante":{"clasificacion":table(prediction["visitante"]),
                                     "reciente":context.get("visitante_datos")}},
            "cara_a_cara":context.get("enfrentamientos") or [],
            "calidad":context.get("calidad") or {},
            "top_3":m.get("top_probabilidad") or [],
            "conteos_aprobados_retro":m.get("mercados_conteos_habilitados_retro",0),
            "valor_comparado":m.get("top_valor_exploratorio") or [],
            "xg":context.get("xg") or {"estado":"NO_DISPONIBLE"},
            "ml":ml_data,"mercado_referencias":refs,"limitaciones":problems,
            "aviso":"Estudio estadístico experimental, no recomendación ni apuesta automática."}

def markdown(dossier:dict)->str:
    d=dossier
    h=d["equipos"]["local"];a=d["equipos"]["visitante"]
    lines=[f'## {d["local"]} – {d["visitante"]}',"",
           f'**{d["liga"]} · {d["fecha_utc"]} · modelo {d["modelo"]}**',"",
           "### Probabilidades del modelo principal","",
           "| Local | Empate | Visitante | Más de 2,5 goles |",
           "|---:|---:|---:|---:|",
           "| "+ " | ".join(_fprob(d["probabilidades"][x]) for x in
                 ("local","empate","visitante","mas_2_5"))+" |","",
           "### Forma, descanso y estadísticas",""]
    for side,data in (("local",h),("visitante",a)):
        name=d[side]
        ctx=data["reciente"] or {}
        cls=data["clasificacion"]
        standing=(f'posición {cls["posicion"]} · {cls["puntos"]} puntos' if cls else
                  "clasificación no disponible en datos recuperados")
        rest=ctx.get("dias_descanso")
        lines.extend([f'**{name}:** {standing}.',
                      f'- Últimos partidos: {_form(ctx)}',
                      f'- Días desde el último partido liguero registrado: {_number(rest)}',
                      f'- Medias recientes: {_stats(ctx)}',""])
    lines.append("### Enfrentamientos previos")
    h2h=d.get("cara_a_cara") or []
    lines.extend(f'- {x["fecha"]}: {x["local"]} {x["marcador"]} {x["visitante"]}' for x in h2h[:5])
    if not h2h:lines.append("- No disponibles en el histórico consultado")
    lines.extend(["","### Tres selecciones del modelo (experimentales)"])
    for i,c in enumerate(d.get("top_3") or [],1):
        lines.append(f'{i}. **{c["seleccion"]}** ({c["mercado"]}): '
                     f'{100*c["probabilidad"]:.1f}% · cuota justa {c["cuota_justa"]:.2f}; '
                     f'procedencia {c["origen"]}; estado {c["nivel"]}')
    if not d.get("top_3"):lines.append("- No existen tres selecciones elegibles verificables")
    lines.extend(["","### Comparación de modelos y fuentes"])
    if d.get("ml"):
        x=d["ml"]
        lines.append(f'- XGBoost experimental: {x["victoria_local"]} / {x["empate"]} / {x["victoria_visitante"]}. No sustituye al modelo principal.')
    else:lines.append("- XGBoost para este encuentro: sin predicción reciente y verificada")
    if d.get("mercado_referencias"):
        for m in d["mercado_referencias"]:
            lines.append(f'- Mercado: {m["estado"]} ({m["proveedor"]}, fecha {m["fecha"]})')
    else:lines.append("- Cuotas ofrecidas y referencias específicas: no disponibles en este informe")
    lines.extend(["","### Qué falta o conviene vigilar"])
    lines.extend(f'- {x}' for x in d.get("limitaciones",[]))
    lines.extend(["","*No es una recomendación de apuesta ni demuestra rentabilidad.*",""])
    return "\n".join(lines)

def build_all(predictions:list[dict],contexts:list[dict],selections:list[dict],
              machina:dict|None=None,ml_rows:list[dict]|None=None,
              market_rows:list[dict]|None=None,now:datetime|None=None)->list[dict]:
    now=now or datetime.now(timezone.utc)
    code_to_label={k:v[0] for k,v in LEAGUES.items()}
    con={_key(code_to_label.get(c["liga"],c["liga"]),c["fecha_utc"],c["local"],c["visitante"]):c
         for c in contexts}
    sel={s["id"]:s for s in selections}
    mar={x["id"]:x for x in (market_rows or [])}
    xs={}
    for x in (ml_rows or []):
        try:
            issued=datetime.fromisoformat(x["fecha_analisis_utc"].replace("Z","+00:00"))
            if issued.tzinfo is None or not 0 <= (now-issued).total_seconds() <= 8*86400:continue
            xs[_key(x["liga"],x["fecha_utc"],x["local"],x["visitante"])]=x
        except (KeyError,ValueError,TypeError):continue
    result=[]
    for p in predictions:
        key=_key(p["liga"],p["fecha_utc"],p["local"],p["visitante"])
        result.append(build_one(p,con.get(key),sel.get(p["id"]),machina,xs.get(key),mar.get(p["id"])))
    return result
