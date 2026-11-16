"""Telegram Fase 7: filtros, revisión verificada, duplicados y secretos."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from football_ai_lab import telegram_alerts as alerts

NOW = datetime(2026,11,16,8,30,tzinfo=timezone.utc)
FUTURE="2026-11-17T19:00:00+00:00"
OLD="2026-11-15T18:00:00+00:00"


def forecast(id="SP2|future",market="corners",league="Segunda División",
             chance=.72,level="BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA",
             date=FUTURE):
    return {"id":id,"liga":league,"local":"Tenerife","visitante":"Ceuta",
            "fecha_utc":date,"mercados":{market:[{
                "mercado":"Córners totales","seleccion":"Más de 8,5 córners",
                "probabilidad":chance,"cuota_justa":round(1/chance,3),
                "nivel":level,"posicion_top3":2,"linea":8.5,
            }]}}


def settled(key="k1",status="FINALIZADO",outcome="1",saved="2026-11-14T08:00:00Z",
            market="corners",kickoff=OLD):
    return {"clave":key,"id":"SP2|past","liga":"Segunda División",
            "local":"Granada","visitante":"Las Palmas","fecha_utc":kickoff,
            "archivado_utc":saved,"categoria":market,
            "probabilidad":"0.72","seleccion":"Más de 8,5 córners",
            "nivel":"BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA",
            "estado":status,"resultado":outcome,"posicion_top3":"2"}


class AlertTests(unittest.TestCase):
    def test_defaults_and_filter_settings(self):
        s=alerts.Settings.from_env({})
        self.assertIn("corners",s.markets)
        self.assertEqual(s.horizon_hours,72)
        custom=alerts.Settings.from_env({
            "TELEGRAM_ALERT_MARKETS":"corners, double,not-real",
            "TELEGRAM_ALERT_LEAGUES":"LaLiga, Segunda División",
            "TELEGRAM_ALERT_QUALITY":"top3",
            "TELEGRAM_ALERT_MIN_PROBABILITY":"0.75",
            "TELEGRAM_ALERT_HORIZON_HOURS":"48",
        })
        self.assertEqual(custom.markets,frozenset({"corners","double"}))
        self.assertEqual(custom.leagues,
                         frozenset({"laliga","segunda división"}))
        self.assertEqual(custom.min_probability,.75)
        self.assertEqual(custom.quality,"top3")
        self.assertEqual(custom.horizon_hours,48)
        invalid=alerts.Settings.from_env({
            "TELEGRAM_ALERT_MIN_PROBABILITY":"nan",
            "TELEGRAM_ALERT_HORIZON_HOURS":"-3",
            "TELEGRAM_ALERT_QUALITY":"unknown",
        })
        self.assertEqual(invalid.min_probability,.65)
        self.assertEqual(invalid.horizon_hours,72)
        self.assertEqual(invalid.quality,"all")

    def test_upcoming_excludes_past_wrong_market_and_below_threshold(self):
        data={"partidos":[
            forecast(), forecast(id="SP1|x",market="double",chance=.81),
            forecast(id="SP2|past",date=OLD),
            forecast(id="SP2|low",chance=.51),
            forecast(id="SP2|far",date="2026-11-29T20:00:00+00:00"),
        ]}
        matches=alerts.upcoming(data,alerts.Settings(),NOW)
        self.assertEqual([x["id"] for x in matches],["SP1|x","SP2|future"])
        only=alerts.Settings.from_env({"TELEGRAM_ALERT_MARKETS":"corners",
                                       "TELEGRAM_ALERT_QUALITY":"audited"})
        self.assertEqual([x["id"] for x in alerts.upcoming(data,only,NOW)],
                         ["SP2|future"])
        self.assertEqual(len(alerts.upcoming(data,alerts.Settings.from_env({
            "TELEGRAM_ALERT_LEAGUES":"Premier League"}),NOW)),0)

    def test_daily_digest_contains_future_and_verified_results(self):
        text,state,meta=alerts.digest(
            {"partidos":[forecast()]},
            [settled("yes",outcome="1"),settled("no",outcome="0")],
            {},alerts.Settings(),NOW)
        self.assertTrue(meta["enviar"])
        self.assertEqual(meta["proximos"],1)
        self.assertEqual(meta["resultados"],2)
        self.assertIn("Tenerife",text)
        self.assertIn("Fase 7",text)
        self.assertIn("acierto",text)
        self.assertIn("fallo",text)
        self.assertIn("estimado",text)
        self.assertIn("No son apuestas recomendadas",text)
        self.assertEqual(state["last_daily_madrid"],"2026-11-16")
        self.assertEqual(set(state["reported_keys"]),{"yes","no"})
        self.assertLess(len(text),3901)

    def test_scheduled_and_manual_duplicate_suppression(self):
        data={"partidos":[forecast()]}
        rows=[settled("one")]
        first,state,_=alerts.digest(data,rows,{},alerts.Settings(),NOW)
        self.assertTrue(first)
        again,unchanged,meta=alerts.digest(data,rows,state,alerts.Settings(),NOW)
        self.assertEqual(again,"")
        self.assertFalse(meta["enviar"])
        self.assertEqual(unchanged,state)
        new_text,state2,update=alerts.digest(data,rows+[settled("two")],state,
                                              alerts.Settings(),NOW)
        self.assertFalse(update["diario"])
        self.assertEqual(update["resultados"],1)
        self.assertNotIn("Próximas 72",new_text)
        self.assertIn("two",state2["reported_keys"])

    def test_missing_stats_and_unverified_not_losses(self):
        rows=[
            settled("missing",status="ESTADISTICA_NO_DISPONIBLE",outcome=""),
            settled("no_score",status="RESULTADO_NO_DISPONIBLE",outcome=""),
            settled("not_finished",status="PENDIENTE",outcome=""),
            settled("bad",saved="2026-11-16T08:00:00Z"), # after kickoff
            settled("valid",outcome="0")
        ]
        msg,state,meta=alerts.digest({"partidos":[]},rows,{},alerts.Settings(),NOW)
        self.assertEqual(meta["resultados"],1)
        self.assertIn("NO son fallos",msg)
        self.assertIn("1 estadísticas, 1 marcadores",msg)
        self.assertEqual(state["reported_keys"],["valid"])

    def test_madrid_calendar_day_and_late_results(self):
        when=datetime(2026,11,16,23,30,tzinfo=timezone.utc)
        msg,state,meta=alerts.digest({"partidos":[]},[],
                   {"last_daily_madrid":"2026-11-16"},alerts.Settings(),when)
        self.assertTrue(meta["diario"]) # 00:30 del día 17 en Madrid
        self.assertEqual(state["last_daily_madrid"],"2026-11-17")
        self.assertIn("Sin nuevas",msg)
        delayed=settled("late",kickoff="2026-10-01T18:00:00+00:00")
        self.assertEqual(alerts.new_results([delayed],{},alerts.Settings(),NOW),[])

    def test_main_preview_and_enabled_gate_do_not_send(self):
        with patch.object(alerts,"_load_json",return_value={"partidos":[forecast()]}),\
             patch.object(alerts,"_load_csv",return_value=[]):
            called=[]
            def sender(*args):
                called.append(args); return True
            with patch("builtins.print"):
                first=alerts.main([],env={"TELEGRAM_BOT_TOKEN":"dummy",
                    "TELEGRAM_CHAT_ID":"123456"},now=NOW,sender=sender)
                preview=alerts.main(["--preview"],env={},now=NOW,sender=sender)
            self.assertEqual(first["motivo"],"no configurado")
            self.assertTrue(preview["enviar"])
            self.assertEqual(called,[])

    def test_confirmed_send_persists_without_credentials_and_no_send_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/"estado.json"
            with patch.object(alerts,"STATE_PATH",state),\
                 patch.object(alerts,"_load_json",side_effect=lambda x: {
                     "partidos":[forecast()]} if "pronosticos_" in str(x) else {}),\
                 patch.object(alerts,"_load_csv",return_value=[]),\
                 patch("builtins.print"):
                args={"TELEGRAM_ALERTS_ENABLED":"true",
                      "TELEGRAM_BOT_TOKEN":"FAKE-BOT-SECRET",
                      "TELEGRAM_CHAT_ID":"999000"}
                result=alerts.main([],env=args,now=NOW,sender=lambda *x:False)
                self.assertEqual(result["motivo"],"entrega no confirmada")
                self.assertFalse(state.exists())
                result=alerts.main([],env=args,now=NOW,sender=lambda *x:True)
                self.assertTrue(result["enviar"])
                contents=state.read_text()
                self.assertNotIn("FAKE-BOT-SECRET",contents)
                self.assertNotIn("999000",contents)
                self.assertEqual(json.loads(contents)["last_daily_madrid"],"2026-11-16")

    def test_long_message_only_marks_results_actually_shown(self):
        forecasts=[]
        for i in range(12):
            item=forecast(id=f"future{i}")
            item["local"]="L"*130
            item["visitante"]="V"*130
            forecasts.append(item)
        results=[]
        for i in range(14):
            row=settled(key=f"result{i}",outcome="1")
            row["local"]="Club A"*20
            row["visitante"]="Club B"*20
            row["seleccion"]="Más de 9,5 córners totales "*10
            results.append(row)
        text,state,meta=alerts.digest(
            {"partidos":forecasts},results,{},alerts.Settings(
                max_upcoming=12,max_results=14),NOW)
        self.assertLessEqual(len(text),3900)
        self.assertEqual(meta["resultados"],len(state["reported_keys"]))
        self.assertEqual(meta["resultados"],
                         text.count("✓ "))
        self.assertGreater(meta["resultados"],0)

    def test_message_is_bounded_and_removes_control_characters(self):
        items=[]
        for i in range(20):
            obj=forecast(id=f"match{i}",market="corners",
                         date="2026-11-17T19:00:00+00:00")
            obj["local"]="A"*130+"\n@BotFather"
            obj["visitante"]="B"*130
            items.append(obj)
        txt,*_=alerts.digest({"partidos":items},[],{},
            alerts.Settings(max_upcoming=12),NOW)
        self.assertLessEqual(len(txt),3900)
        self.assertNotIn("\n@BotFather",txt)

if __name__=="__main__":
    unittest.main()
