import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from football_ai_lab.postmatch_stats import (
    _parse_summary, _stat_map, enrich_statistics,
)
from football_ai_lab.postmatch_breakdown import build_breakdown
from football_ai_lab.market_prospective import settle

START = datetime(2026, 11, 15, 13, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
EVENT = "123456789"
HOME, AWAY = "CD Tenerife", "AD Ceuta FC"


def archived(market, selection, kind, stats=None, line=2.5):
    record = {
        "id": "SP2|202611151300|tenerife|ceuta",
        "clave": "SP2|202611151300|tenerife|ceuta|" + market + "|" + selection,
        "liga": "Segunda División", "local": "Tenerife", "visitante": "Ceuta",
        "fecha_utc": START.isoformat(),
        "archivado_utc": (START-timedelta(hours=15)).isoformat(),
        "mercado": market, "seleccion": selection,
        "probabilidad": "0.65", "cuota_justa": "1.54",
        "contrato": json.dumps(
            {"tipo":"conteo","metrica":stats,"linea":line,"direccion":kind}
            if stats else {"tipo":"total","linea":line,"direccion":"Menos"}),
    }
    return record


def scoreboard(home=HOME, away=AWAY, hg=2, ag=0, completed=True, event_id=EVENT):
    return {"events": [{
        "id": event_id, "date": START.isoformat(),
        "status": {"type": {"name": "STATUS_FULL_TIME", "completed": completed}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"displayName": home}, "score": str(hg)},
            {"homeAway": "away", "team": {"displayName": away}, "score": str(ag)},
        ]}],
    }]}


def summary(shots_home=13, shots_away=9):
    def t(team, shots, target, corners, yellow, red):
        return {"team": {"displayName": team}, "statistics": [
            {"name": "totalShots", "displayValue": str(shots)},
            {"name": "shotsOnTarget", "displayValue": str(target)},
            {"name": "cornerKicks", "displayValue": str(corners)},
            {"name": "yellowCards", "displayValue": str(yellow)},
            {"name": "redCards", "displayValue": str(red)},
            {"name": "fouls", "displayValue": "12"},
        ]}
    return {"header": {"competitions": [{"id":EVENT, "competitors": [
        {"team": {"displayName": HOME}}, {"team": {"displayName": AWAY}}
    ]}]},
        "boxscore": {"teams": [t(HOME,shots_home,5,6,3,0),
                               t(AWAY,shots_away,3,4,2,1)]}}


class PostmatchTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            archived("Tiros totales","Más de 20,5 tiros", "mas", "shots",20.5),
            archived("Córners totales","Más de 9,5 córners", "mas", "corners",9.5),
            archived("Tarjetas amarillas totales","Más de 4,5 amarillas","mas","yellow",4.5),
            archived("Tiros a puerta totales","Más de 7,5 tiros a puerta","mas","on_target",7.5),
            archived("Total goles","Menos de 2,5 goles","",None),
        ]
        self.games = {"SP2":[{"date": date(2026,11,15),"home":"CD Tenerife",
                              "away":"AD Ceuta FC","home_goals":2,"away_goals":0}]}

    def provider(self, url, sb=None, box=None):
        if "/scoreboard" in url:
            return json.dumps(sb if sb is not None else scoreboard()).encode()
        if "/summary" in url:
            return json.dumps(box if box is not None else summary()).encode()
        raise AssertionError(url)

    def test_four_statistics_and_goal_settled_5_of_5(self):
        with tempfile.TemporaryDirectory() as root:
            cache=Path(root)/"audit.json"
            updated, audit, payload=enrich_statistics(
                self.games,self.rows,NOW,cache,fetcher=self.provider)
            self.assertEqual(audit["objetivos_conteo"],1)
            self.assertEqual(audit["completos"],1)
            self.assertEqual(audit["objetivos_detalle"][0]["motivo"],"COMPLETO")
            self.assertEqual(audit["objetivos_detalle"][0]["campos_ausentes"],[])
            self.assertEqual(audit["incompletos_por_motivo"]["ESTADISTICAS_INCOMPLETAS"],0)
            self.assertEqual(audit["scoreboards_consultados"],1)
            self.assertEqual(audit["summaries_consultados"],1)
            self.assertEqual(audit["campos_recuperados"],12)
            self.assertEqual(audit["partidos_con_faltas"],1)
            original=self.games["SP2"][0]
            self.assertNotIn("home_corners",original)
            settled=settle(self.rows,updated,NOW)
            self.assertEqual([r["estado"] for r in settled],["FINALIZADO"]*5)
            self.assertEqual([r["resultado"] for r in settled],["1"]*5)
            doc=build_breakdown(settled,updated,NOW,audit)
            first=doc["partidos"][0]
            self.assertEqual(first["evaluadas"],5)
            self.assertEqual(first["estadisticas"]["corners"]["total"],10)
            self.assertEqual(first["estadisticas"]["fouls"]["total"],24)
            self.assertIn("6 local + 4 visitante = 10",
                          first["selecciones"][1]["explicacion"])
            self.assertIn("summary?event=",first["estadisticas"]["shots"]["fuentes"][0])
            # La persistencia permite reusar datos sin llamadas externas.
            cache.write_text(json.dumps(payload),encoding="utf-8")
            def no_network(url):
                raise AssertionError("No debería necesitar consultar ESPN")
            second, check, _=enrich_statistics(self.games,self.rows,NOW,cache,
                                                fetcher=no_network)
            self.assertEqual(check["completos"],1)
            self.assertEqual(check["scoreboards_consultados"],0)

    def test_no_after_match_bets_or_future(self):
        future=archived("Córners totales","Más de 9,5","mas","corners",9.5)
        future["archivado_utc"]=(START+timedelta(minutes=1)).isoformat()
        updated,audit,_=enrich_statistics(self.games,[future],NOW,
             cache_path=Path("/tmp/nonexistent-football-stats.json"),
             fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)))
        self.assertEqual(audit["objetivos_conteo"],0)
        before=START+timedelta(hours=1)
        updated,audit,_=enrich_statistics(self.games,self.rows,before,
            cache_path=Path("/tmp/nonexistent-football-stats.json"),
            fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)))
        self.assertEqual(audit["objetivos_conteo"],0)

    def test_wrong_score_cannot_contribute(self):
        with tempfile.TemporaryDirectory() as root:
            out,audit,_=enrich_statistics(self.games,self.rows,NOW,Path(root)/"missing",
                fetcher=lambda url:self.provider(url,sb=scoreboard(hg=5,ag=0)))
            self.assertEqual(audit["conflictos_marcador"],1)
            self.assertEqual(audit["completos"],0)
            self.assertEqual(audit["objetivos_detalle"][0]["motivo"],"ESTADISTICAS_INCOMPLETAS")
            self.assertIn("home_shots", audit["objetivos_detalle"][0]["campos_ausentes"])
            self.assertEqual(settle(self.rows,out,NOW)[0]["estado"],
                             "ESTADISTICA_NO_DISPONIBLE")

    def test_wrong_teams_cannot_contribute_and_no_leak_into_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            bad_summary=summary()
            bad_summary["boxscore"]["teams"][1]["team"]["displayName"]="Atlético de Madrid"
            out,audit,_=enrich_statistics(self.games,self.rows,NOW,Path(root)/"missing",
                fetcher=lambda url:self.provider(url,box=bad_summary))
            self.assertEqual(audit["completos"],0)
            self.assertEqual(out["SP2"][0].get("away_corners"),None)

    def test_missing_is_not_zero_and_zero_is_valid(self):
        self.assertNotIn("yellow",_stat_map([{"name":"yellowCards","displayValue":"0/5"}]))
        self.assertEqual(_stat_map([{"name":"yellowCards","value":0}])["yellow"],0)
        self.assertEqual(_stat_map([{"name":"fouls","value":"12"}])["fouls"],12)
        self.assertNotIn("fouls", _stat_map([
            {"name":"fouls","value":"12"}, {"name":"totalFouls","value":"13"}]))
        data=summary()
        del data["boxscore"]["teams"][0]["statistics"][2]
        self.assertNotIn("home_corners",_parse_summary(data,"SP2",HOME,AWAY,EVENT))

    def test_csv_field_priority_and_partial_metrics(self):
        history={"SP2":[dict(self.games["SP2"][0],home_shots=15,away_shots=12,
            home_corners=8,away_corners=None)]}
        with tempfile.TemporaryDirectory() as root:
            out,audit,_=enrich_statistics(history,self.rows,NOW,Path(root)/"missing",
                fetcher=self.provider)
            self.assertEqual(out["SP2"][0]["home_shots"],15)
            self.assertEqual(out["SP2"][0]["away_shots"],12)
            self.assertEqual(out["SP2"][0]["home_corners"],8)
            self.assertEqual(out["SP2"][0]["away_corners"],4)
            self.assertEqual(audit["completos"],1)

    def test_scoreboard_unfinished_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            out,audit,_=enrich_statistics(self.games,self.rows,NOW,Path(root)/"missing",
                fetcher=lambda url:self.provider(url,sb=scoreboard(completed=False)))
            self.assertEqual(audit["summaries_consultados"],0)
            self.assertEqual(audit["completos"],0)

    def test_six_leagues_and_kickoff_timezone_no_crossing(self):
        from football_ai_lab.sources import LEAGUES
        self.assertEqual(len(LEAGUES),6)
        late=archived("Córners totales","Más de 9,5","mas","corners",9.5)
        late["fecha_utc"]="2026-11-15T23:30:00+00:00"
        later=NOW+timedelta(hours=10)
        with tempfile.TemporaryDirectory() as root:
            out,audit,_=enrich_statistics(self.games,[late],later,Path(root)/"missing",
               fetcher=self.provider)
            self.assertEqual(audit["completos"],0)


if __name__=="__main__":
    unittest.main()
