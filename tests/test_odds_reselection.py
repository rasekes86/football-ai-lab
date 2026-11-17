"""La revisión excepcional preserva evidencia, Top 3 y partidos terminados."""
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from football_ai_lab.odds_reselection import plan_revisions

NOW=datetime(2026,11,17,22,tzinfo=timezone.utc)
SNAPSHOT=NOW-timedelta(hours=4)
KICK=(NOW+timedelta(days=3)).isoformat()


def old(ident="A",kind="OFRECIDA_API_REGISTRADA",p=.52,sel="Menos de 2,5 goles",status="PENDIENTE"):
    return {"id":ident,"clave":ident+"|"+sel,"local":"Equipo A",
        "visitante":"Equipo B","liga":"LaLiga","fecha_utc":KICK,
        "tipo_cuota":kind,"estado":status,"probabilidad":str(p),
        "seleccion":sel,"cuota_decimal":"2.500"}


def match(ident="A"):
    return {"id":ident,"local":"Equipo A","visitante":"Equipo B",
        "liga":"LaLiga","fecha_utc":KICK,"calculado_utc":NOW.isoformat()}


def proposal(p=.735):
    return {"id":"A","clave":"A|Menos de 3,5 goles","probabilidad":f"{p:.6f}",
            "seleccion":"Menos de 3,5 goles","fecha_cuota_utc":SNAPSHOT.isoformat(),
            "archivado_utc":SNAPSHOT.isoformat(),"cuota_decimal":"1.615",
            "estado":"PENDIENTE"}


class ReselectionTests(unittest.TestCase):
    def test_highest_probability_replaces_old_pending_and_audits_original(self):
        with patch("football_ai_lab.odds_reselection._compared_candidates",
                   return_value=[proposal()]) as candidates:
            changes,audit=plan_revisions(
                [old()],[match()],{"capturado_utc":SNAPSHOT.isoformat()},
                [],NOW)
        self.assertEqual(set(changes),{"A"})
        self.assertEqual(audit[0]["anterior"]["seleccion"],"Menos de 2,5 goles")
        self.assertEqual(changes["A"]["archivado_utc"],NOW.isoformat())
        self.assertEqual(changes["A"]["fecha_cuota_utc"],SNAPSHOT.isoformat())
        # Se consulta la captura antigua, no se pretende usar un precio actual.
        self.assertEqual(candidates.call_args.args[2],SNAPSHOT)

    def test_no_change_when_same_pick_or_lower_probability(self):
        for candidate in [proposal(.50),{**proposal(.735),"clave":old()["clave"]}]:
            with self.subTest(candidate=candidate),patch(
                "football_ai_lab.odds_reselection._compared_candidates",
                return_value=[candidate]):
                changes,_=plan_revisions(
                    [old()],[match()],{"capturado_utc":SNAPSHOT.isoformat()},[],NOW)
                self.assertFalse(changes)

    def test_no_postmatch_or_unverified_manual_revisions(self):
        with patch("football_ai_lab.odds_reselection._compared_candidates",
                   return_value=[proposal()]):
            changes,_=plan_revisions(
                [old(kind="INDICATIVA_NO_VERIFICADA"),
                 old(ident="B",status="FINALIZADO")],
                [match("A"),match("B")],
                {"capturado_utc":SNAPSHOT.isoformat()},[],NOW)
        self.assertFalse(changes)

    def test_reject_comparison_after_request_or_older_than_a_week(self):
        with self.assertRaises(ValueError):
            plan_revisions([old()],[match()],
                           {"capturado_utc":(NOW+timedelta(hours=1)).isoformat()},
                           [],NOW)
        with self.assertRaises(ValueError):
            plan_revisions([old()],[match()],
                           {"capturado_utc":(NOW-timedelta(days=8)).isoformat()},
                           [],NOW)


if __name__=="__main__":
    unittest.main()
