"""Regresión de presupuesto/rotación sin red, claves ni reloj real."""
from datetime import datetime, timedelta, timezone
import unittest

from football_ai_lab.odds_scheduler import RequestLedger,due_matches
from football_ai_lab.odds_refresh import merge_followup
from football_ai_lab.real_odds import build_real_odds

NOW=datetime(2026,11,17,12,tzinfo=timezone.utc)


def match(ident):
    return {"id":ident,"fecha_utc":(NOW+timedelta(days=2)).isoformat()}


class Tests(unittest.TestCase):
    def test_rotate_unseen_first(self):
        state={"fixtures":{
            "recent":{"consultado_utc":(NOW-timedelta(hours=1)).isoformat(),"con_cuotas":True},
            "old":{"consultado_utc":(NOW-timedelta(hours=5)).isoformat(),"con_cuotas":True},
            "empty":{"consultado_utc":(NOW-timedelta(hours=3)).isoformat(),"con_cuotas":False},
        }}
        due,skipped=due_matches([match(x) for x in ("recent","empty","old","new")],state,NOW)
        self.assertEqual([x["id"] for x in due],["new","old","empty"])
        self.assertEqual(skipped,1)

    def test_hourly_budget_persists(self):
        ledger=RequestLedger({},NOW)
        self.assertTrue(all(ledger.take() for _ in range(48)))
        self.assertFalse(ledger.take())
        self.assertEqual(RequestLedger(ledger.export(),NOW+timedelta(minutes=30)).remaining(),0)
        self.assertEqual(RequestLedger(ledger.export(),NOW+timedelta(hours=1,seconds=1)).remaining(),48)

    def test_recent_priced_skipped_then_refreshed(self):
        ledger=RequestLedger({},NOW)
        ledger.mark("a",True)
        self.assertEqual(due_matches([match("a")],ledger.export(),NOW+timedelta(hours=1))[0],[])
        self.assertEqual(len(due_matches([match("a")],ledger.export(),NOW+timedelta(hours=4))[0]),1)

    def test_frozen_additional_never_queries_bookmaker(self):
        fixture=match("frozen")
        called=[]
        def forbid(url,headers):
            called.append(url)
            raise AssertionError("No se debe recotizar una adicional ya congelada")
        price,comparisons,history=build_real_odds(
            [fixture],NOW,
            env={"ENABLE_FREE_ODDS":"true","FIVEDOLLAR_API_KEY":"FAKE"},
            five_fetcher=forbid,excluded_ids={"frozen"})
        self.assertEqual(called,[])
        self.assertEqual(price["auditoria"]["partidos_con_adicional_omitidos"],1)
        self.assertEqual(price["cuotas"],[])

    def test_settled_results_never_overwritten(self):
        rows=merge_followup([{"clave":"A","estado":"FINALIZADO","resultado":"1"}],
            [{"clave":"A","estado":"PENDIENTE","resultado":""},
             {"clave":"B","estado":"PENDIENTE","resultado":""}])
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["resultado"],"1")


if __name__=="__main__":
    unittest.main()
