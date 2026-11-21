"""Bitácora de agentes especializados deterministas (no simula llamadas a LLM)."""
from __future__ import annotations
from datetime import datetime, timezone

class AgentLog:
    ROLES=("datos","contexto","predictor","mercado","selector","auditor","evaluador","jugadores","mercados_prospectivos","oportunidades_150","marcadores_finales","estadisticas_finales","auditoria_mercados_futuros","cuotas_reales","cuarta_referencia","publicador")
    def __init__(self,now:datetime):
        self.now=now
        self.events=[]
    def mark(self,role:str,status:str,details:str="",count:int|None=None)->None:
        if role not in self.ROLES: raise ValueError(f"Agente desconocido: {role}")
        entry={"agente":role,"estado":status,"detalle":details,"utc":self.now.isoformat()}
        if count is not None: entry["registros"]=count
        self.events.append(entry)
    def export(self)->dict:
        return {"utc":self.now.isoformat(),"modo":"automatización Python — sin LLM en cada ejecución",
                "agentes":self.events}
