"""Fase 4: ningún backfill, una sola instantánea, liquidación y calibración."""
import copy
import json
import unittest
from datetime import date, datetime, timezone, timedelta

from football_ai_lab.future_market_audit import (
    FIELDS, CATEGORIES, archive_future_markets,
    settle_future_markets, audit_future_markets,
)

SAVED=datetime(2026,11,14,12,tzinfo=timezone.utc)
KICK=datetime(2026,11,15,13,tzinfo=timezone.utc)
FINISHED=datetime(2026,11,16,12,tzinfo=timezone.utc)
ID="SP2|202611151300|tenerife|ceuta"


def candidate(market,selection,p,level="MODELO_NO_CALIBRADO",**kw):
    return {"mercado":market,"seleccion":selection,"probabilidad":p,
            "cuota_justa":round(1/p,3),"origen":"Motor de pruebas",
            "nivel":level,**kw}


def fixture(saved=SAVED,kickoff=KICK):
    return {
        "id":ID,"liga":"Segunda División","local":"Tenerife","visitante":"Ceuta",
        "fecha_utc":kickoff.isoformat(),"calculado_utc":saved.isoformat(),
        "mercados":{
            "corners":[
                candidate("Córners totales","Más de 9,5 córners totales",.7,
                          "EXPLORATORIO_NO_VALIDADO",linea=9.5,direccion="mas",
                          posicion_top3=1),
                candidate("Córners totales","Menos de 11,5 córners totales",.62,
                          "EXPLORATORIO_NO_VALIDADO",linea=11.5,direccion="menos"),
            ],
            "double":[candidate("Doble oportunidad","1X: Tenerife o empate",.83)],
            "goals":[candidate("Total goles","Más de 1,5 goles",.67)],
            "fouls":[],
        }
    }


def history(with_corners=True):
    match={"date":date(2026,11,15),"home":"CD Tenerife","away":"AD Ceuta",
           "home_goals":2,"away_goals":0}
    if with_corners:
        match.update(home_corners=6,away_corners=4)
    return {"SP2":[match]}


class FutureArchiveTests(unittest.TestCase):
    def test_snapshot_all_lines_exactly_once_and_timestamps(self):
        initial=fixture()
        previous=copy.deepcopy(initial)
        rows,report=archive_future_markets([], [initial], SAVED)
        self.assertEqual(report["nuevos"],4)
        self.assertEqual(report["partidos_nuevos"],1)
        self.assertEqual({r["categoria"] for r in rows},{"corners","double","goals"})
        self.assertEqual(len({r["clave"] for r in rows}),4)
        self.assertTrue(all(r["archivado_utc"]==SAVED.isoformat() for r in rows))
        self.assertEqual(rows[0]["posicion_top3"],1)
        self.assertEqual(initial,previous)
        original=copy.deepcopy(rows)
        changed=fixture(saved=SAVED+timedelta(hours=1))
        changed["mercados"]["corners"][0]["probabilidad"]=.25
        changed["mercados"]["corners"].append(candidate(
            "Córners totales","Menos de 9,5 córners totales",.62,
            "EXPLORATORIO_NO_VALIDADO",linea=9.5,direccion="menos"))
        again,rep=archive_future_markets(rows,[changed],SAVED+timedelta(hours=1))
        self.assertEqual(rep["nuevos"],0)
        self.assertEqual(again,original)  # no mutación ni ampliación tardía

    def test_no_backfill_after_kickoff_or_invalid_export(self):
        after=fixture(saved=KICK+timedelta(minutes=1))
        rows,rep=archive_future_markets([], [after], FINISHED)
        self.assertEqual(rows,[])
        self.assertEqual(rep["nuevos"],0)
        stale=fixture(saved=SAVED)
        rows,_=archive_future_markets([], [stale],FINISHED)
        self.assertFalse(rows)  # nunca backfill aunque se hubiera calculado antes
        corrupted=fixture()
        corrupted["mercados"]["goals"][0]["cuota_justa"]=5.0
        corrupted["mercados"]["double"][0]["probabilidad"]=1.2
        rows,_=archive_future_markets([], [corrupted],SAVED)
        self.assertEqual(len(rows),2)

    def test_verified_goals_and_corners_and_calibration(self):
        frozen,_=archive_future_markets([], [fixture()],SAVED)
        completed=settle_future_markets(frozen,history(),FINISHED)
        self.assertEqual(len(completed),4)
        self.assertEqual({r["estado"] for r in completed},{"FINALIZADO"})
        decisions={r["seleccion"]:r["resultado"] for r in completed}
        self.assertEqual(decisions["Más de 9,5 córners totales"],"1")
        self.assertEqual(decisions["Menos de 11,5 córners totales"],"1")
        self.assertEqual(decisions["Más de 1,5 goles"],"1")
        self.assertEqual(decisions["1X: Tenerife o empate"],"1")
        audit=audit_future_markets(completed,FINISHED)
        self.assertEqual(audit["registradas"],4)
        self.assertEqual(audit["finalizadas"],4)
        self.assertEqual(audit["global"]["partidos_unicos"],1)
        self.assertEqual(audit["global"]["acierto_pct"],100)
        self.assertGreater(audit["global"]["brier"],0)
        self.assertGreater(audit["global"]["ece"],0)
        self.assertEqual(audit["global"]["evidencia"],"LIMITADA")
        self.assertEqual(audit["por_mercado"]["corners"]["muestra"],2)
        self.assertEqual(audit["por_mercado_liga"]["corners"]["Segunda División"]["muestra"],2)
        self.assertEqual(audit["por_mercado_calidad"]["corners"]["EXPLORATORIO_NO_VALIDADO"]["muestra"],2)
        self.assertEqual(sum(b["muestra"] for b in audit["global"]["calibracion"]),4)
        self.assertEqual({r["estado"] for r in frozen},{"PENDIENTE"})

    def test_missing_stats_not_loss_and_no_premature_settlement(self):
        frozen,_=archive_future_markets([], [fixture()],SAVED)
        before=settle_future_markets(frozen,history(),KICK+timedelta(minutes=25))
        self.assertTrue(all(r["estado"]=="PENDIENTE" for r in before))
        lacking=settle_future_markets(frozen,history(False),FINISHED)
        count=[r for r in lacking if r["categoria"]=="corners"]
        self.assertEqual({r["estado"] for r in count},{"ESTADISTICA_NO_DISPONIBLE"})
        audit=audit_future_markets(lacking,FINISHED)
        self.assertEqual(audit["sin_estadistica"],2)
        self.assertEqual(audit["finalizadas"],2)
        self.assertEqual(audit["por_mercado"]["corners"]["muestra"],0)
        self.assertIsNone(audit["por_mercado"]["corners"]["brier"])

    def test_pending_score_and_excluded_timestamp(self):
        frozen,_=archive_future_markets([], [fixture()],SAVED)
        noresult=settle_future_markets(frozen,{"SP2":[]},FINISHED)
        self.assertTrue(all(r["estado"]=="RESULTADO_NO_DISPONIBLE" for r in noresult))
        fraud=copy.deepcopy(frozen)
        fraud[0]["archivado_utc"]=(KICK+timedelta(minutes=10)).isoformat()
        result=settle_future_markets(fraud,history(),FINISHED)
        self.assertEqual(result[0]["estado"],"EXCLUIDO_FECHA_O_PROBABILIDAD")
        self.assertEqual(audit_future_markets(result,FINISHED)["excluidas"],1)

    def test_all_fields_serialize_and_no_unknown_market(self):
        row=fixture()
        row["mercados"]["fake"]=[candidate("Faltas totales","Más de 10,5",.9)]
        rows,_=archive_future_markets([], [row],SAVED)
        self.assertEqual(len(rows),4)
        self.assertTrue(set(FIELDS)<=set(rows[0]))
        self.assertIn("contrato",json.loads(json.dumps(rows[0])))
        self.assertEqual(audit_future_markets([],FINISHED)["global"]["evidencia"],"SIN_MUESTRA")


if __name__=="__main__":
    unittest.main()
