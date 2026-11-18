"""Rondas de cuotas con memoria, sin repetir consultas recientes ni superar
el presupuesto conservador del plan gratuito. Solo se almacenan timestamps e IDs.
"""
from datetime import datetime, timedelta, timezone
import time

FREE_BUDGET=48  # Del máximo de 60/h dejamos 12 de margen.
MIN_INTERVAL=3.2  # Menos de 20 peticiones/minuto.
PRICED_HOURS=4
EMPTY_HOURS=2
UNMATCHED_HOURS=6  # Proveedor sin evento equivalente: evitar escanear cada dos horas


def parse(value):
    try:
        d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (TypeError,ValueError,OverflowError):
        return None


def due_matches(fixtures,state,now,days=5):
    """Devuelve primero partidos nunca consultados y luego capturas caducadas."""
    previous=(state or {}).get("fixtures") or {}
    due=[]
    skipped=0
    for m in fixtures:
        kick=parse(m.get("fecha_utc"))
        ident=m.get("id")
        if not ident or not kick or not now<kick<=now+timedelta(days=days):
            continue
        record=previous.get(ident) or {}
        last=parse(record.get("consultado_utc"))
        hours=(UNMATCHED_HOURS if record.get("motivo_consulta")=="SIN_EVENTO_VERIFICADO"
               else PRICED_HOURS if record.get("con_cuotas") else EMPTY_HOURS)
        if last and timedelta(0)<=now-last<timedelta(hours=hours):
            skipped+=1
            continue
        due.append((0 if last is None else 1,
                    last or now-timedelta(days=10),kick,str(ident),m))
    due.sort(key=lambda row:row[:4])
    return [row[-1] for row in due],skipped


class RequestLedger:
    """Control de cupo horario entre ejecuciones; espaciado real en producción."""
    def __init__(self,state,now,limit=FREE_BUDGET,live=False):
        self.now=now.astimezone(timezone.utc)
        self.live=live
        self.limit=max(1,int(limit))
        state=state if isinstance(state,dict) else {}
        self.calls=sorted(d for x in state.get("solicitudes_utc",[])
                          if (d:=parse(x)) and self.now-timedelta(hours=1)<d<=self.now)
        self.fixtures=dict(state.get("fixtures") or {})

    def clock(self):
        return datetime.now(timezone.utc) if self.live else self.now

    def remaining(self):
        current=self.clock()
        self.calls=[x for x in self.calls if current-timedelta(hours=1)<x<=current]
        return max(0,self.limit-len(self.calls))

    def take(self):
        if not self.remaining():return False
        if self.live:
            while True:
                now=self.clock()
                if not self.remaining():return False
                recent=[x for x in self.calls if x>now-timedelta(seconds=60)]
                delay=0.0
                if len(recent)>=19:
                    delay=max(delay,(recent[0]+timedelta(seconds=61)-now).total_seconds())
                if self.calls:
                    delay=max(delay,MIN_INTERVAL-(now-self.calls[-1]).total_seconds())
                if delay<=0:break
                time.sleep(max(0.05,delay))
        self.calls.append(self.clock())
        return True

    def mark(self,ident,priced,reason=None):
        record={"consultado_utc":self.clock().isoformat(),
                "con_cuotas":bool(priced)}
        if reason:
            record["motivo_consulta"]=str(reason)
        self.fixtures[ident]=record

    def export(self):
        now=self.clock()
        self.remaining()
        valid=[(k,v) for k,v in self.fixtures.items()
               if parse((v or {}).get("consultado_utc"))
               and now-timedelta(days=9)<parse(v["consultado_utc"])<=now]
        valid.sort(key=lambda pair:pair[1]["consultado_utc"],reverse=True)
        return {"version":1,"actualizado_utc":now.isoformat(),
                "limite_interno_hora":self.limit,
                "solicitudes_utc":[x.isoformat() for x in self.calls],
                "fixtures":dict(valid[:500])}
