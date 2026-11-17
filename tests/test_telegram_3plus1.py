"""Telegram 3+1: only original selections, verified outcomes and opt-in sending."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from football_ai_lab import telegram_3plus1 as alerts

NOW = datetime(2026,11,22,12,tzinfo=timezone.utc)
KICK = "2026-11-21T15:00:00Z"
SAVED = "2026-11-17T15:00:00Z"


def pick(key, outcome="1", status="FINALIZADO", **kwargs):
    row = {"id": "SP1|fixture", "clave": key, "liga": "LaLiga",
           "local": "Sevilla", "visitante": "Real Betis",
           "fecha_utc": KICK, "archivado_utc": SAVED,
           "mercado": "Total goles", "seleccion": "Menos de 2,5 goles",
           "estado": status, "resultado": outcome, "probabilidad": "0.58"}
    row.update(kwargs)
    return row


def extra(key="extra", **kwargs):
    row = pick(key, tipo_cuota="OFRECIDA_API_REGISTRADA", cuota_decimal="2.100")
    row.update(kwargs)
    return row


class Telegram3Plus1Tests(unittest.TestCase):
    def test_confirmed_hit_miss_and_indicative_are_sports_outcomes(self):
        top = [pick("top1", outcome="1"), pick("top2", outcome="0"),
               pick("top3", status="ESTADISTICA_NO_DISPONIBLE", outcome="")]
        extra_rows = [extra(tipo_cuota="INDICATIVA_NO_VERIFICADA")]
        message, state, info = alerts.digest(top, extra_rows, {}, NOW)
        self.assertTrue(info["enviar"])
        self.assertEqual(info["top"], {"total":3, "resolved":2,"hits":1,"pending":1})
        self.assertEqual(info["extra"], {"total":1, "resolved":1,"hits":1,"pending":0})
        self.assertEqual(info["notificados"],3)
        self.assertIn("Top 3: 1 aciertos / 2",message)
        self.assertIn("Adicional +1,50: 1 aciertos / 1",message)
        self.assertIn("indicativa 2.100",message)
        self.assertIn("NO cuenta como fallo",message)
        self.assertNotIn("ganancia real",message)
        self.assertIn("top:top1",state["reported_keys"])
        self.assertIn("extra:extra",state["reported_keys"])

    def test_no_repeat_on_same_or_next_execution(self):
        first,state,meta = alerts.digest([pick("a")],[extra()],{},NOW)
        self.assertEqual(meta["notificados"],2)
        message,next_state,meta = alerts.digest([pick("a")],[extra()],state,NOW)
        self.assertEqual(message,"")
        self.assertEqual(next_state,state)
        self.assertEqual(meta["notificados"],0)
        # Newly settled result is sent without repeating those already notified.
        second,after,meta = alerts.digest(
            [pick("a"),pick("b",outcome="0")], [extra()],state,NOW
        )
        self.assertEqual(meta["notificados"],1)
        self.assertEqual(after["reported_keys"][-1],"top:b")
        self.assertEqual(second.count("❌ Top 3"),1)

    def test_never_count_fourth_top_pick_or_two_additionals(self):
        top=[pick("top1"),pick("top2"),pick("top3"),pick("top4")]
        adds=[extra("extra1"),extra("extra2",cuota_decimal="4.500")]
        _,_,meta=alerts.digest(top,adds,{},NOW)
        self.assertEqual(meta["top"]["total"],3)
        self.assertEqual(meta["extra"]["total"],1)
        self.assertEqual(meta["notificados"],4)

    def test_missing_result_or_date_excluded_without_false_losses(self):
        top=[pick("not_done",id="fixture-A",status="PENDIENTE",outcome=""),
             pick("not_scored",id="fixture-B",status="RESULTADO_NO_DISPONIBLE",outcome=""),
             pick("wrong_day",id="fixture-C",archivado_utc="2026-11-22T17:00:00Z"),
             pick("future",id="fixture-D",fecha_utc="2026-11-25T15:00:00Z"),
             pick("good",id="fixture-E")]
        odds=[extra("too_low",cuota_decimal="1.500"),
              extra("invalid_price",cuota_decimal="inf"),
              extra("legitimate",estado="ESTADISTICA_NO_DISPONIBLE",resultado="")]
        msg,state,meta=alerts.digest(top,odds,{},NOW)
        self.assertEqual(meta["top"]["resolved"],1)
        self.assertEqual(meta["top"]["pending"],3)
        self.assertEqual(meta["extra"]["resolved"],0)
        self.assertEqual(meta["notificados"],1)
        self.assertNotIn("too_low",json.dumps(state))
        self.assertIn("pendientes",msg)

    def test_message_capped_only_marks_included_and_does_not_leak(self):
        matches=[pick("key"+str(i),id="ID"+str(i),
                      local="A"*29,visitante="B"*29,
                      seleccion="S"*75)
                 for i in range(35)]
        msg,state,meta=alerts.digest(matches,[],{},NOW,max_items=5)
        self.assertLessEqual(len(msg),3900)
        self.assertEqual(meta["notificados"],5)
        self.assertEqual(len(state["reported_keys"]),5)
        self.assertIn("pendientes de notificar",msg)

    def test_preview_and_disabled_gate_never_send(self):
        with patch.object(alerts,"_state",return_value={}), \
             patch.object(alerts,"_csv",side_effect=lambda path:
                 [pick("good")] if path.name=="seguimiento_selecciones.csv" else []):
            called=[]
            def sender(*args):
                called.append(args)
                return True
            with patch("builtins.print"):
                result=alerts.main([],env={"TELEGRAM_BOT_TOKEN":"SECRET",
                                           "TELEGRAM_CHAT_ID":"123"},now=NOW,sender=sender)
                preview=alerts.main(["--preview"],env={},now=NOW,sender=sender)
            self.assertEqual(result["motivo"],"no activado")
            self.assertTrue(preview["enviar"])
            self.assertEqual(called,[])

    def test_state_only_persisted_after_confirmed_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            state_file=Path(directory)/"state.json"
            with patch.object(alerts,"STATE_PATH",state_file), \
                 patch.object(alerts,"_csv",side_effect=lambda path:
                     [pick("safe")] if path.name=="seguimiento_selecciones.csv" else []), \
                 patch("builtins.print"):
                settings={"TELEGRAM_3PLUS1_ENABLED":"true",
                          "TELEGRAM_BOT_TOKEN":"FAKE-SECRET-TOKEN",
                          "TELEGRAM_CHAT_ID":"000123"}
                result=alerts.main([],env=settings,now=NOW,sender=lambda *_: False)
                self.assertEqual(result["motivo"],"entrega no confirmada")
                self.assertFalse(state_file.exists())
                result=alerts.main([],env=settings,now=NOW,sender=lambda *_:True)
                self.assertEqual(result["notificados"],1)
                saved=state_file.read_text()
                self.assertNotIn("FAKE-SECRET-TOKEN",saved)
                self.assertNotIn("000123",saved)
                self.assertEqual(json.loads(saved)["reported_keys"],["top:safe"])
                result=alerts.main([],env=settings,now=NOW,sender=lambda *_:True)
                self.assertFalse(result["enviar"])


if __name__=="__main__":
    unittest.main()
