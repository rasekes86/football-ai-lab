"""Fase 8: solo cuotas reales prepartido con fuente, márgenes y contratos idénticos."""
import json
import unittest
from datetime import datetime, timezone, timedelta

from football_ai_lab.real_odds import (
    VERSION, build_real_odds, retrieve_odds, compare_forecasts,
    archive_snapshots, _book_quotes, _find_fixture, MAX_QUOTE_AGE
)

NOW=datetime(2026,11,16,12,tzinfo=timezone.utc)
START="2026-11-20T20:00:00Z"
H="Athletic Club"
A="Espanyol"
FID="SP1|202611202000|ath bilbao|espanyol"
API_KEY="FAKE-TOKEN-PRIVATE-123"
ENV={"ENABLE_REAL_ODDS":"true","THE_ODDS_API_KEY":API_KEY,"REAL_ODDS_LEAGUES":"SP1"}


def fixture():
    return {"id":FID,"liga":"LaLiga","local":H,"visitante":A,
            "fecha_utc":START,"mercados":{
                "result":[
                    {"mercado":"1X2","seleccion":H+" gana","probabilidad":.56,
                     "nivel":"MODELO_NO_CALIBRADO","posicion_top3":1},
                    {"mercado":"1X2","seleccion":"Empate","probabilidad":.25,
                     "nivel":"MODELO_NO_CALIBRADO"},
                    {"mercado":"1X2","seleccion":A+" gana","probabilidad":.19,
                     "nivel":"MODELO_NO_CALIBRADO"}],
                "goals":[
                    {"mercado":"Total goles","seleccion":"Más de 2,5 goles",
                     "probabilidad":.60,"nivel":"MODELO_NO_CALIBRADO"},
                    {"mercado":"Total goles","seleccion":"Menos de 3,5 goles",
                     "probabilidad":.73,"nivel":"MODELO_NO_CALIBRADO"},
                ],
                "corners":[{"mercado":"Córners totales","seleccion":"Más de 9,5 córners",
                            "probabilidad":.70,"linea":9.5}],
                "double":[{"mercado":"Doble oportunidad","seleccion":"1X: Athletic Club o empate",
                           "probabilidad":.75}],
            }}


def event(id="abc123",home=H,away=A,changed="2026-11-16T11:00:00Z",
          when=START,three=True,totals=True,league="soccer_spain_la_liga"):
    h2h=[{"name":home,"price":2.20},{"name":"Draw","price":3.40}]
    if three:h2h.append({"name":away,"price":3.60})
    markets=[{"key":"h2h","last_update":changed,"outcomes":h2h}]
    if totals:
        markets.append({"key":"totals","last_update":changed,"outcomes":[
            {"name":"Over","point":2.5,"price":1.92},
            {"name":"Under","point":2.5,"price":1.96},
            {"name":"Over","point":3.5,"price":3.4},
            {"name":"Under","point":3.5,"price":1.35},
        ]})
    return {"id":id,"sport_key":league,"commence_time":when,
            "home_team":home,"away_team":away,
            "bookmakers":[{"key":"mock_eu","title":"Casa de prueba",
                           "last_update":changed,"markets":markets}]}


def feed(events):
    return lambda url: json.dumps(events).encode("utf-8")


class RealOddsTests(unittest.TestCase):
    def test_disabled_by_default_never_contacts_api_or_leaks_secrets(self):
        def forbid(url):raise AssertionError(url)
        row,cmp,arch=build_real_odds([fixture()],NOW,env={
            "THE_ODDS_API_KEY":API_KEY},fetcher=forbid)
        self.assertEqual(row["estado"],"DESACTIVADO")
        self.assertEqual(row["cuotas"],[])
        self.assertEqual(cmp["comparaciones"],[])
        self.assertEqual(arch["cuotas"],[])
        self.assertNotIn(API_KEY,json.dumps([row,cmp,arch]))
        no_key=retrieve_odds([fixture()],NOW,env={
            "ENABLE_REAL_ODDS":"true"},fetcher=forbid)
        self.assertEqual(no_key["estado"],"SIN_CLAVE")

    def test_match_1x2_totals_price_margin_ev_source_and_no_double(self):
        row,cmp,arch=build_real_odds([fixture()],NOW,env=ENV,
                                      fetcher=feed([event()]))
        self.assertEqual(row["estado"],"CON_CUOTAS")
        self.assertEqual(row["auditoria"]["cuotas_validadas"],7)
        self.assertEqual(row["auditoria"]["estimacion_creditos_maximos"],2)
        self.assertEqual(row["auditoria"]["partidos_cruzados"],1)
        self.assertEqual(len(cmp["comparaciones"]),5)
        self.assertEqual({x["categoria"] for x in cmp["comparaciones"]},{"result","goals"})
        home=next(x for x in cmp["comparaciones"] if x["seleccion"]==H+" gana")
        self.assertEqual(home["cuota_real"],2.2)
        self.assertEqual(home["probabilidad_modelo"],.56)
        self.assertAlmostEqual(home["ev_teorico_unidad"],.232,places=6)
        self.assertGreater(home["margen_casa"],0)
        self.assertLess(home["p_mercado_sin_margen"],home["p_implicita"])
        self.assertEqual(home["bookmaker"],"Casa de prueba")
        self.assertEqual(home["proveedor"],"The Odds API V4")
        self.assertNotIn(API_KEY,json.dumps([row,cmp,arch]))
        self.assertEqual(arch["observaciones_nuevas"],7)
        self.assertEqual(len(arch["cuotas"]),7)

    def test_provider_league_team_direction_and_time_must_match(self):
        for changed in ["2026-11-14T09:00:00Z","2026-11-20T20:01:00Z",
                        "2026-11-16T14:00:00Z"]:
            out=retrieve_odds([fixture()],NOW,env=ENV,
                              fetcher=feed([event(changed=changed)]))
            self.assertEqual(out["cuotas"],[],changed)
        different=retrieve_odds([fixture()],NOW,env=ENV,
                         fetcher=feed([event(home="Real Madrid")]))
        self.assertFalse(different["cuotas"])
        swapped=retrieve_odds([fixture()],NOW,env=ENV,
                         fetcher=feed([event(home=A,away=H)]))
        self.assertFalse(swapped["cuotas"])
        wrong_league=retrieve_odds([fixture()],NOW,env=ENV,
                           fetcher=feed([event(league="soccer_epl")]))
        self.assertFalse(wrong_league["cuotas"])
        time=retrieve_odds([fixture()],NOW,env=ENV,
                    fetcher=feed([event(when="2026-11-21T06:00:00Z")]))
        self.assertFalse(time["cuotas"])
        duplicated=retrieve_odds([fixture(),dict(fixture())],NOW,env=ENV,
                           fetcher=feed([event()]))
        self.assertFalse(duplicated["cuotas"])

    def test_incomplete_bookmaker_market_does_not_create_false_margin(self):
        bad=retrieve_odds([fixture()],NOW,env=ENV,
                          fetcher=feed([event(three=False,totals=False)]))
        self.assertEqual(bad["cuotas"],[])
        event2=event()
        event2["bookmakers"][0]["markets"][0]["outcomes"][0]["price"]=1.0
        result=retrieve_odds([fixture()],NOW,env=ENV,fetcher=feed([event2]))
        self.assertTrue(all(x["mercado"]=="totals" for x in result["cuotas"]))

    def test_no_substitute_different_line_or_unsupported_count_market(self):
        source=retrieve_odds([fixture()],NOW,env=ENV,fetcher=feed([event()]))
        false_fixture=fixture()
        false_fixture["mercados"]["goals"][0]["seleccion"]="Más de 3,5 goles"
        false_fixture["mercados"]["goals"].append({
            "seleccion":"Más de 8,5 goles","probabilidad":.76})
        compared=compare_forecasts([false_fixture],source,NOW)
        self.assertEqual(len(compared["comparaciones"]),5)
        self.assertTrue(all(x["categoria"] in ("goals","result")
                            for x in compared["comparaciones"]))
        self.assertFalse(any(x["seleccion"]=="Más de 8,5 goles"
                             for x in compared["comparaciones"]))

    def test_stale_json_cannot_be_presented_as_current(self):
        row=retrieve_odds([fixture()],NOW,env=ENV,fetcher=feed([event()]))
        future=NOW+timedelta(hours=30)
        compared=compare_forecasts([fixture()],row,future)
        self.assertEqual(compared["comparaciones"],[])
        self.assertEqual(compared["auditoria"]["precios_comparados"],0)

    def test_failed_api_is_safe_and_does_not_relabel_old_quote_as_current(self):
        first,cmp,arch=build_real_odds([fixture()],NOW,env=ENV,
                                      fetcher=feed([event()]))
        def api_fail(url):raise RuntimeError("TOKEN="+API_KEY)
        next_quotes,compared,archived=build_real_odds(
            [fixture()],NOW+timedelta(hours=1),
            existing=arch,env=ENV,fetcher=api_fail)
        self.assertEqual(next_quotes["estado"],"PARCIAL")
        self.assertEqual(next_quotes["cuotas"],[])
        self.assertEqual(compared["comparaciones"],[])
        self.assertEqual(len(archived["cuotas"]),7)
        self.assertEqual(archived["observaciones_nuevas"],0)
        self.assertNotIn(API_KEY,json.dumps([next_quotes,compared,archived]))

    def test_archive_first_observation_and_no_historical_fabrication(self):
        first,_,archive=build_real_odds([fixture()],NOW,env=ENV,
                                       fetcher=feed([event()]))
        newest=event(changed="2026-11-16T12:10:00Z")
        newest["bookmakers"][0]["markets"][0]["outcomes"][0]["price"]=2.6
        second,_,other=build_real_odds([fixture()],NOW+timedelta(minutes=20),
            existing=archive,env=ENV,fetcher=feed([newest]))
        self.assertEqual(other["observaciones_nuevas"],0)
        h=[x for x in other["cuotas"] if x["mercado"]=="h2h" and x["resultado"]=="1"]
        self.assertEqual(h[0]["cuota"],2.2) # immutable first of day

    def test_six_leagues_budget_and_selected_league(self):
        self.assertEqual(len(LEAGUE_SPORTS := {
            "SP1":"soccer_spain_la_liga","SP2":"soccer_spain_segunda_division",
            "E0":"soccer_epl","D1":"soccer_germany_bundesliga",
            "I1":"soccer_italy_serie_a","F1":"soccer_france_ligue_one"}),6)
        urls=[]
        def captured(url):
            urls.append(url)
            return b"[]"
        result=retrieve_odds([fixture()],NOW,env={
            **ENV,"REAL_ODDS_LEAGUES":"SP1,SP2,E0,D1,I1,F1"},fetcher=captured)
        self.assertEqual(result["auditoria"]["estimacion_creditos_maximos"],12)
        self.assertEqual(len(urls),6)
        self.assertTrue(all("regions=eu" in x for x in urls))

if __name__=="__main__":
    unittest.main()
