"""Aviso opcional a Telegram, desactivado hasta configurar secretos privados.

No usa cuentas de apuestas, no publica datos privados y se ejecuta solo en
la tarea programada/manual de GitHub Actions. Nunca escribe tokens en logs.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
from urllib.request import Request,urlopen

def message(data:dict,followup:dict|None=None)->str:
    top=data.get("top_3_jornada") or []
    date=data.get("calculado_utc","sin fecha")
    lines=["⚽ Football AI Lab · Resumen experimental",
           "Actualización: "+str(date)[:16]+" UTC",
           "Top por probabilidad modelada (NO apuestas recomendadas):"]
    if top:
        for i,p in enumerate(top[:3],1):
            lines.append(f'{i}. {p["local"]} – {p["visitante"]}\n'
                         f'   {p["seleccion"]}: {float(p["probabilidad"])*100:.1f}% '
                         f'(cuota justa, NO ofrecida: {float(p["cuota_justa"]):.2f})')
    else:lines.append("Sin selecciones elegibles para este periodo.")
    if followup:
        lines.append(f'Pronósticos de mercados archivados: {followup.get("registradas",0)}; '
                     f'finalizados y verificados: {followup.get("finalizadas",0)}.')
    lines.extend(["No confirma cuotas reales, alineaciones ni ganancias.",
                 "Ver informes: https://github.com/rasekes86/football-ai-lab/blob/main/output/informe.md"])
    return "\n".join(lines)[:4000]

def send(text:str,token:str,chat_id:str,opener=urlopen)->bool:
    if not re.fullmatch(r"\d{4,}:[A-Za-z0-9_-]{20,}",token):
        raise ValueError("Token con formato inválido (sin revelar credenciales)")
    if not re.fullmatch(r"-?\d{5,20}",chat_id):
        raise ValueError("Chat ID no válido")
    endpoint="https://api.telegram.org/bot"+token+"/sendMessage"
    body=json.dumps({"chat_id":chat_id,"text":text,
                     "disable_web_page_preview":True}).encode("utf-8")
    request=Request(endpoint,data=body,headers={"Content-Type":"application/json"},
                    method="POST")
    # Avoid ever exposing token if a provider returns an HTTP error with its URL.
    response=opener(request,timeout=10)
    with response as data:
        blob=json.loads(data.read())
        return blob.get("ok") is True

def main()->None:
    token=os.environ.get("TELEGRAM_BOT_TOKEN","").strip()
    chat=os.environ.get("TELEGRAM_CHAT_ID","").strip()
    if not token or not chat:
        print("Telegram desactivado: faltan secretos en GitHub (sin enviar mensajes).")
        return
    try:
        data=json.loads(Path("output/selecciones.json").read_text(encoding="utf-8"))
        more=json.loads(Path("output/evaluacion_selecciones.json").read_text(encoding="utf-8"))
        delivered=send(message(data,more),token,chat)
        print("Telegram:", "entregado" if delivered else "proveedor no confirmó la entrega")
    except Exception as exc:
        # Do not print the exception or URL: they may contain the bot token.
        print("Telegram no entregado:",type(exc).__name__)
if __name__=="__main__":main()
