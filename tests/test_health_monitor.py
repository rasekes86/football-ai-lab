"""Pruebas deterministas del control de salud, sin red ni credenciales reales."""
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from football_ai_lab.health_monitor import assess, run, alert_text

NOW = datetime(2026, 11, 18, 14, tzinfo=timezone.utc)
TOKEN = "12345:" + "x" * 24
ENV = {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "12345678",
       "FREE_ODDS_ENABLED": "true"}

def stamp(hours=0):
    return (NOW + timedelta(hours=hours)).isoformat()

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

def fixtures(path, *, clock=None, calendar=0, pending=None):
    save(path / "pronosticos_mercados_futuros.json", {
        "calculado_utc": clock or stamp(-2),
        "partidos": [{"id": "SP1|match", "fecha_utc": stamp(36)}]})
    save(path / "evaluacion_selecciones.json", {
        "calculado_utc": clock or stamp(-2)})
    save(path / "cuotas_reales_verificadas.json", {
        "capturado_utc": stamp(-1),
        "auditoria": {"fuentes_gratuitas": [{
            "proveedor": "5DollarFootballAPI",
            "estado": "PARCIAL" if calendar else "CON_CUOTAS",
            "errores_por_fase": {"calendario": calendar}
        }]}})
    save(path / "estado_consultas_cuotas.json", {"actualizado_utc": stamp(-1)})
    with (path / "seguimiento_selecciones.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "fecha_utc", "estado"])
        writer.writeheader()
        writer.writerows(pending or [])

def codes(result):
    return {i["codigo"] for i in result["incidencias"]}

class HealthMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name)
        fixtures(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_healthy_and_no_false_alarm_from_unoffered_odds(self):
        report = assess(self.path, NOW, odds_enabled=True)
        self.assertEqual(report["estado"], "CORRECTO")
        self.assertFalse(report["incidencias"])
        self.assertEqual(report["detalle"]["partidos_proximos"], 1)
        self.assertEqual(report["racha_calendario"], 0)

    def test_real_provider_capture_stale_even_if_ledger_updated(self):
        odds = json.loads((self.path / "cuotas_reales_verificadas.json").read_text())
        odds["capturado_utc"] = stamp(-10)
        save(self.path / "cuotas_reales_verificadas.json", odds)
        report = assess(self.path, NOW)
        self.assertIn("CUOTAS_SIN_ACTUALIZAR", codes(report))
        report_disabled = assess(self.path, NOW, odds_enabled=False)
        self.assertNotIn("CUOTAS_SIN_ACTUALIZAR", codes(report_disabled))

    def test_daily_stale_and_missing_evaluation(self):
        fixtures(self.path, clock=stamp(-37))
        self.assertIn("ANALISIS_CADUCADO", codes(assess(self.path, NOW)))
        (self.path / "evaluacion_selecciones.json").unlink()
        self.assertIn("ANALISIS_CADUCADO", codes(assess(self.path, NOW)))

    def test_two_distinct_calendar_snapshots_required(self):
        fixtures(self.path, calendar=3)
        first = assess(self.path, NOW)
        self.assertNotIn("CALENDARIO_ERRORES_REPETIDOS", codes(first))
        self.assertEqual(first["racha_calendario"], 1)
        repeated = assess(self.path, NOW, first)
        self.assertEqual(repeated["racha_calendario"], 1)
        self.assertNotIn("CALENDARIO_ERRORES_REPETIDOS", codes(repeated))
        odds = json.loads((self.path / "cuotas_reales_verificadas.json").read_text())
        odds["capturado_utc"] = stamp(0)
        save(self.path / "cuotas_reales_verificadas.json", odds)
        second = assess(self.path, NOW, repeated)
        self.assertEqual(second["racha_calendario"], 2)
        self.assertIn("CALENDARIO_ERRORES_REPETIDOS", codes(second))
        odds["capturado_utc"] = stamp(1)
        odds["auditoria"]["fuentes_gratuitas"][0]["errores_por_fase"] = {}
        save(self.path / "cuotas_reales_verificadas.json", odds)
        resolved = assess(self.path, NOW, second)
        self.assertEqual(resolved["racha_calendario"], 0)
        self.assertNotIn("CALENDARIO_ERRORES_REPETIDOS", codes(resolved))

    def test_settlement_alert_uses_distinct_matches_and_respects_missing_stats(self):
        pending = [{"id": "A", "fecha_utc": stamp(-80), "estado": "PENDIENTE"},
                   {"id": "A", "fecha_utc": stamp(-80), "estado": "PENDIENTE"},
                   {"id": "B", "fecha_utc": stamp(-100), "estado": "ESTADISTICA_NO_DISPONIBLE"}]
        fixtures(self.path, pending=pending)
        self.assertNotIn("LIQUIDACION_RETRASADA", codes(assess(self.path, NOW)))
        pending.append({"id": "C", "fecha_utc": stamp(-100), "estado": "PENDIENTE"})
        fixtures(self.path, pending=pending)
        report = assess(self.path, NOW)
        self.assertIn("LIQUIDACION_RETRASADA", codes(report))
        self.assertEqual(report["detalle"]["partidos_sin_liquidar_48h"], 2)

    def test_failed_workflow_persists_until_same_workflow_succeeds(self):
        initial = assess(self.path, NOW, source_workflow="Refresco escalonado de cuotas",
                         source_conclusion="failure")
        self.assertIn("FALLO_REFRESCO", codes(initial))
        schedule = assess(self.path, NOW, initial)
        self.assertIn("FALLO_REFRESCO", codes(schedule))
        other = assess(self.path, NOW, schedule,
                       source_workflow="Analisis futbol diario", source_conclusion="success")
        self.assertIn("FALLO_REFRESCO", codes(other))
        resolved = assess(self.path, NOW, other,
                          source_workflow="Refresco escalonado de cuotas", source_conclusion="success")
        self.assertNotIn("FALLO_REFRESCO", codes(resolved))

    def test_one_initial_notice_then_dedup_then_recovery(self):
        sent = []
        def sender(message, token, chat):
            sent.append((message, token, chat))
            return True
        first = run(self.path, NOW, ENV, sender)
        self.assertEqual(first["envio"], "ENTREGADO")
        self.assertIn("activado", sent[-1][0])
        second = run(self.path, NOW + timedelta(hours=1), ENV, sender)
        self.assertEqual(second["envio"], "SIN_NOVEDADES")
        self.assertEqual(len(sent), 1)
        odds = json.loads((self.path / "cuotas_reales_verificadas.json").read_text())
        odds["capturado_utc"] = stamp(-11)
        save(self.path / "cuotas_reales_verificadas.json", odds)
        failed = run(self.path, NOW + timedelta(hours=1), ENV, sender)
        self.assertEqual(failed["estado"], "INCIDENCIAS")
        self.assertEqual(len(sent), 2)
        self.assertIn("CUOTAS SIN ACTUALIZAR", sent[-1][0])
        again = run(self.path, NOW + timedelta(hours=2), ENV, sender)
        self.assertEqual(again["envio"], "SIN_NOVEDADES")
        fixtures(self.path)
        good = run(self.path, NOW + timedelta(hours=2), ENV, sender)
        self.assertEqual(good["estado"], "CORRECTO")
        self.assertEqual(good["envio"], "ENTREGADO")
        self.assertIn("resueltas", sent[-1][0])
        self.assertEqual(len(sent), 3)

    def test_failed_send_does_not_mark_as_notified_and_retries(self):
        sent = []
        def sender(message, token, chat):
            sent.append(message)
            return len(sent) > 1
        first = run(self.path, NOW, ENV, sender)
        self.assertEqual(first["envio"], "NO_CONFIRMADO")
        state = json.loads((self.path / "estado_salud.json").read_text())
        self.assertEqual(state["notificadas"], [])
        second = run(self.path, NOW, ENV, sender)
        # A missing 'notificadas' vs [] is intentional only on first startup.
        self.assertEqual(second["envio"], "NO_CONFIRMADO")

    def test_preview_never_sends_or_writes(self):
        def forbidden(*args):
            raise AssertionError("preview called Telegram")
        report = run(self.path, NOW, ENV, forbidden, preview=True)
        self.assertEqual(report["estado"], "CORRECTO")
        self.assertFalse((self.path / "estado_salud.json").exists())
        self.assertNotIn(TOKEN, json.dumps(report))
        self.assertIn("activado", report["mensaje"])

    def test_private_keys_never_written_to_monitor_state(self):
        run(self.path, NOW, ENV, lambda *args: True)
        state=(self.path / "estado_salud.json").read_text()
        self.assertNotIn(TOKEN, state)
        self.assertNotIn(ENV["TELEGRAM_CHAT_ID"], state)

if __name__ == "__main__":
    unittest.main()
