import json
import unittest
from datetime import datetime, timezone, timedelta
from football_ai_lab.top3_odds import (
    freeze_top3_quotes, settle_top3_quotes, top3_odds_report,
    quote_needed_ids, FIELDS
)
from football_ai_lab.free_odds import get_five_odds

NOW = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
START = "2026-11-22T17:00:00+00:00"
ARCHIVE = "2026-11-21T13:00:00+00:00"
CAPTURE = "2026-11-22T11:00:00+00:00"
ID = "SP1|202611221700|local|visitante"


def pick(market="Total goles", spec=None):
    if spec is None:
        spec = {"tipo": "total", "direccion": "Menos", "linea": 4.5}
    return {
        "clave": ID+"|"+market, "id": ID, "liga": "LaLiga",
        "local": "Local", "visitante": "Visitante", "fecha_utc": START,
        "archivado_utc": ARCHIVE, "mercado": market,
        "seleccion": "Menos de 4,5 goles", "probabilidad": "0.84",
        "cuota_justa": "1.19", "contrato": json.dumps(spec),
    }


def quote(**overrides):
    out = {
        "fixture_id": ID, "liga": "LaLiga", "local": "Local",
        "visitante": "Visitante", "fecha_utc": START,
        "mercado": "totals", "resultado": "under", "linea": 4.5,
        "cuota": 1.18, "capturado_utc": CAPTURE,
        "actualizado_utc": CAPTURE,
        "marca_tiempo_tipo": "CAPTURA_NO_ACTUALIZACION",
        "bookmaker": "Book A", "bookmaker_id": "a",
        "proveedor": "5DollarFootballAPI", "evento_id": "1234",
        "fuente": "https://5dollarfootballapi.com/",
    }
    out.update(overrides)
    return out


class Top3OddsTests(unittest.TestCase):
    def test_freeze_exact_price_and_retains_original_without_fabricating_history(self):
        original = pick()
        self.assertEqual(quote_needed_ids([original], [], NOW), {ID})
        prices = freeze_top3_quotes([original], {"cuotas": [quote()]}, [], NOW)
        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0]["cuota_decimal"], "1.1800")
        self.assertEqual(prices[0]["bookmaker"], "Book A")
        self.assertEqual(original.get("cuota_decimal"), None)
        self.assertEqual(quote_needed_ids([original], prices, NOW), set())
        changed = freeze_top3_quotes([original],
                   {"cuotas": [quote(cuota=9.5)]}, prices, NOW)
        self.assertEqual(changed, prices, "First observed price is immutable")
        self.assertTrue(all(field in prices[0] for field in FIELDS))

    def test_coverage_diagnoses_unsupported_without_implying_api_request(self):
        unsupported=pick("Doble oportunidad",{"tipo":"doble","pick":"X2"})
        compatible=pick()
        report=top3_odds_report([unsupported,compatible],[],[],NOW)
        x=report["cobertura_contratos"]
        self.assertEqual(x["Doble oportunidad"]["no_equivalentes"],1)
        self.assertEqual(x["Total goles"]["futuras_sin_captura"],1)
        self.assertEqual(x["Total goles"]["capturadas"],0)
        self.assertIn("Sin captura no confirma",report["cobertura_nota"])

    def test_reject_wrong_line_market_team_and_after_kickoff(self):
        original = pick()
        bad = [
            quote(linea=3.5), quote(mercado="corners"),
            quote(local="Otro"), quote(resultado="over"),
            quote(cuota=1.0), quote(proveedor="DESCONOCIDO"),
            quote(capturado_utc="2026-11-22T18:00:00+00:00"),
            quote(evento_id=""), quote(fuente="http://invalid.example"),
        ]
        self.assertEqual(freeze_top3_quotes([original], {"cuotas": bad}, [], NOW), [])

    def test_ignore_unsupported_markets_even_if_same_fixture(self):
        p = pick("Doble oportunidad", {"tipo": "doble", "pick": "1X"})
        self.assertEqual(quote_needed_ids([p], [], NOW), set())
        self.assertEqual(freeze_top3_quotes([p], {"cuotas": [quote()]}, [], NOW), [])
        p = pick("Goles equipo", {"tipo": "goles_equipo", "lado": "H", "linea": 0.5})
        self.assertEqual(freeze_top3_quotes([p], {"cuotas": [quote()]}, [], NOW), [])

    def test_only_settle_verified_and_exclude_overlap_with_additional(self):
        p = pick()
        prices = freeze_top3_quotes([p], {"cuotas": [quote()]}, [], NOW)
        waiting = settle_top3_quotes(prices, [dict(p, estado="PENDIENTE")], [], NOW)
        self.assertEqual(waiting[0]["estado"], "PENDIENTE")
        self.assertEqual(waiting[0]["retorno_simulado_unidad"], "")
        done = [dict(p, estado="FINALIZADO", resultado="1")]
        settled = settle_top3_quotes(prices, done, [], NOW)
        self.assertEqual(settled[0]["retorno_simulado_unidad"], "0.1800")
        report = top3_odds_report([p], prices, settled, NOW)
        self.assertEqual(report["global"]["liquidadas"], 1)
        self.assertEqual(report["global"]["beneficio_hipotetico_unidades"], 0.18)
        self.assertEqual(report["global"]["roi_hipotetico_pct"], 18)
        extra = dict(p, tipo_cuota="OFRECIDA_API_REGISTRADA", cuota_decimal="1.8")
        overlapping = settle_top3_quotes(prices, done, [extra], NOW)
        self.assertEqual(overlapping[0]["estado"], "SOLAPADA_ADICIONAL")
        self.assertEqual(overlapping[0]["retorno_simulado_unidad"], "")
        report = top3_odds_report([p], prices, overlapping, NOW)
        self.assertEqual(report["solapadas_adicional"], 1)
        self.assertEqual(report["global"]["liquidadas"], 0)

    def test_quote_is_not_accepted_before_original_model_was_archived(self):
        old = quote(capturado_utc="2026-11-20T11:00:00+00:00",
                    actualizado_utc="2026-11-20T11:00:00+00:00")
        self.assertEqual(freeze_top3_quotes([pick()], {"cuotas": [old]}, [], NOW), [])

    def test_both_automations_sync_latest_persisted_output_before_calls(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        for workflow in ("daily.yml", "odds-refresh.yml"):
            txt = (root / ".github" / "workflows" / workflow).read_text(
                encoding="utf-8")
            self.assertIn("git fetch origin main", txt)
            self.assertIn("git restore --source=origin/main --worktree -- output", txt)
        refresh = (root / "src" / "football_ai_lab" / "odds_refresh.py").read_text(
            encoding="utf-8")
        self.assertIn("additional=(tracked+", refresh)

    def test_hard_rolling_hour_free_quota_cannot_be_raised_by_vars(self):
        fixture = [{
            "id": ID, "liga": "LaLiga", "local": "Local",
            "visitante": "Visitante", "fecha_utc": START
        }]
        calls = []
        def empty(url, headers):
            calls.append(url)
            return {"success": 1, "data": []}
        data = get_five_odds(fixture, NOW, {
            "ENABLE_FREE_ODDS": "true",
            "FIVEDOLLAR_API_KEY": "TEST-NO-NETWORK",
            "FREE_ODDS_HOURLY_BUDGET": "999",
            "FREE_ODDS_MAX_FIXTURES": "8",
        }, empty)
        self.assertEqual(data["auditoria"]["limite_interno_solicitudes_hora"], 24)
        self.assertLessEqual(len(calls), 24)


if __name__ == "__main__":
    unittest.main()
