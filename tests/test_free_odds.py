"""Fuentes gratis: claves privadas, límites, equivalencias estrictas y trazabilidad."""
import json
import unittest
from datetime import datetime,timezone,timedelta

from football_ai_lab.free_odds import (
    FIVE_NAME,API_NAME,_api_values,_five_fixture_rows,get_five_odds,
    get_api_football_odds,collect_free_odds,
)
from football_ai_lab.real_odds import build_real_odds,compare_forecasts
NOW=datetime(2026,11,16,12,tzinfo=timezone.utc)
FDATE="2026-11-20T20:00:00Z"
FID="SP1|202611202000|ath bilbao|espanyol"
MATCH={"id":FID,"fecha_utc":FDATE,"liga":"LaLiga",
       "local":"Athletic Club","visitante":"Espanyol",
       "mercados":{
           "result":[{"seleccion":"Athletic Club gana","probabilidad":.56}],
           "goals":[{"seleccion":"Más de 2,5 goles","probabilidad":.60}],
           "corners":[{"seleccion":"Más de 9,5 córners totales","probabilidad":.62}],
           "yellow":[{"seleccion":"Más de 4,5 tarjetas amarillas totales","probabilidad":.60}],
           "btts":[{"seleccion":"Sí","probabilidad":.58}],
       }}
FIVE_ENV={"ENABLE_FREE_ODDS":"true","FIVEDOLLAR_API_KEY":"SECRET-FIVE"}
API_ENV={"ENABLE_API_FOOTBALL_ODDS":"true","API_FOOTBALL_KEY":"SECRET-FOOTBALL"}


def five_event(home="Athletic Club",away="Espanyol",league="La Liga"):
    return {"id":47001,"league":{"id":1234,"name":league},
            "teams":{"home":{"name":home},"away":{"name":away}},
            "kickoff_utc":FDATE,"status":"scheduled"}


def five_prices():
    return {"success":1,"data":{"fixture_id":47001,"bookmakers":[{
        "slug":"bet365","name":"Bet 365",
        "odds":{
           "1x2":{"closing":{"home":2.2,"draw":3.4,"away":3.6}},
           "goal_line":{"closing":{"line":2.5,"over":1.9,"under":1.95}},
           "corner_line":{"closing":{"line":9.5,"over":1.89,"under":1.89}},
           "card_line":{"closing":{"line":4.5,"over":1.88,"under":1.95}},
           "btts":{"closing":{"yes":1.82,"no":1.98}},
           "goal_line_fixed":[
             {"line":2.5,"closing":{"over":1.9,"under":1.95}},
             {"line":3.5,"closing":{"over":2.65,"under":1.45}}
           ]
        }}]}}


def five_fetcher(url,headers):
    if headers.get("Authorization")!="Bearer SECRET-FIVE":
        raise AssertionError("Wrong private header")
    if "/odds" in url:
        return five_prices()
    if "/fixtures?" in url:
        return {"success":1,"data":[five_event()]}
    raise AssertionError(url)


def api_fetcher(url,headers):
    if headers.get("x-apisports-key")!="SECRET-FOOTBALL":
        raise AssertionError("Wrong private header")
    if "/odds?" in url:
        return {"response":[{
            "fixture":{"id":18},"league":{"id":140},
            "update":"2026-11-16T11:00:00Z",
            "bookmakers":[{"id":7,"name":"Validado ES","bets":[
                {"name":"Total Yellow Cards","values":[
                    {"value":"Over 4.5","odd":"1.92"},
                    {"value":"Under 4.5","odd":"1.9"}]},
                {"name":"Total Corners","values":[
                    {"value":"Over 9.5","odd":"1.95"},
                    {"value":"Under 9.5","odd":"1.85"}]},
                {"name":"Total Cards","values":[
                    {"value":"Over 4.5","odd":"1.8"},
                    {"value":"Under 4.5","odd":"1.9"}]}
            ]}]
        }]}
    if "/fixtures?" in url:
        return {"response":[{
            "fixture":{"id":18,"date":FDATE},
            "league":{"id":140,"name":"La Liga"},
            "teams":{"home":{"name":"Athletic Club"},"away":{"name":"Espanyol"}}
        }]}
    raise AssertionError(url)


class FreeOddsTest(unittest.TestCase):
    def test_disabled_does_not_make_any_http_call_or_publish_secrets(self):
        def forbidden(*args):
            raise AssertionError("HTTP called when disabled")
        x=collect_free_odds([MATCH],NOW,env={
            "FIVEDOLLAR_API_KEY":"SECRET-FIVE",
            "API_FOOTBALL_KEY":"SECRET-FOOTBALL"},
            five_fetcher=forbidden,api_fetcher=forbidden)
        self.assertEqual(x["estado"],"DESACTIVADO")
        self.assertFalse(x["cuotas"])
        self.assertNotIn("SECRET",json.dumps(x))
        missing=collect_free_odds([MATCH],NOW,env={
            "ENABLE_FREE_ODDS":"true","ENABLE_API_FOOTBALL_ODDS":"true"},
            five_fetcher=forbidden,api_fetcher=forbidden)
        self.assertEqual(missing["estado"],"SIN_CLAVE")

    def test_five_corners_goal_lines_market_margin_and_btts(self):
        data=get_five_odds([MATCH],NOW,FIVE_ENV,five_fetcher)
        self.assertEqual(data["estado"],"CON_CUOTAS")
        self.assertEqual(data["auditoria"]["consultas"],2)
        self.assertEqual(data["auditoria"]["partidos"],1)
        self.assertEqual({q["mercado"] for q in data["cuotas"]},
                         {"h2h","totals","corners","btts"})
        self.assertEqual(len(data["cuotas"]),11)
        corners=[x for x in data["cuotas"] if x["mercado"]=="corners"]
        self.assertEqual({x["resultado"] for x in corners},{"over","under"})
        self.assertEqual(corners[0]["linea"],9.5)
        self.assertEqual(corners[0]["proveedor"],FIVE_NAME)
        self.assertEqual(corners[0]["marca_tiempo_tipo"],"CAPTURA_NO_ACTUALIZACION")
        self.assertTrue(all(x["mercado"]!="yellow" for x in data["cuotas"]))
        self.assertNotIn("SECRET-FIVE",json.dumps(data))

    def test_five_does_not_map_wrong_league_or_swapped_team(self):
        def wrong_league(url,headers):
            if "/odds" in url:return five_prices()
            return {"success":1,"data":[five_event(league="Premier League")]}
        def swapped(url,headers):
            if "/odds" in url:return five_prices()
            return {"success":1,"data":[five_event(home="Espanyol",away="Athletic Club")]}
        self.assertFalse(get_five_odds([MATCH],NOW,FIVE_ENV,wrong_league)["cuotas"])
        self.assertFalse(get_five_odds([MATCH],NOW,FIVE_ENV,swapped)["cuotas"])
        older={**MATCH,"fecha_utc":"2026-11-15T20:00:00Z"}
        self.assertFalse(get_five_odds([older],NOW,FIVE_ENV,five_fetcher)["cuotas"])

    def test_five_refuses_asian_or_incomplete_lines(self):
        raw=five_prices()["data"]
        raw["bookmakers"][0]["odds"]["corner_line"]["closing"]["line"]=9.25
        raw["bookmakers"][0]["odds"]["goal_line"]["closing"]={"line":2.5,"over":1.7}
        raw["bookmakers"][0]["odds"]["goal_line_fixed"]=[]
        found=_five_fixture_rows(MATCH,47001,raw,NOW)
        self.assertFalse(any(x["mercado"]=="corners" for x in found))
        self.assertFalse(any(x["mercado"]=="totals" and x["linea"]==2.5 for x in found))

    def test_api_yellow_only_when_name_explicit_not_generic_cards(self):
        data=get_api_football_odds([MATCH],NOW,API_ENV,api_fetcher)
        self.assertEqual(data["estado"],"CON_CUOTAS")
        self.assertEqual({q["mercado"] for q in data["cuotas"]},{"yellow","corners"})
        yellows=[x for x in data["cuotas"] if x["mercado"]=="yellow"]
        self.assertEqual(len(yellows),2)
        self.assertEqual(yellows[0]["marca_tiempo_tipo"],"ACTUALIZACION_PROVEEDOR")
        self.assertEqual(yellows[0]["linea"],4.5)
        self.assertEqual(yellows[0]["proveedor"],API_NAME)
        self.assertNotIn("SECRET-FOOTBALL",json.dumps(data))
        self.assertEqual(_api_values({"name":"Total Cards","values":[
            {"value":"Over 4.5","odd":"1.9"},{"value":"Under 4.5","odd":"1.9"}]}),[])

    def test_combined_comparison_has_verified_corners_yellow_btts(self):
        quotes,compared,archive=build_real_odds(
            [MATCH],NOW,env={**FIVE_ENV,**API_ENV},
            five_fetcher=five_fetcher,api_fetcher=api_fetcher)
        self.assertEqual(quotes["estado"],"CON_CUOTAS")
        self.assertIn(FIVE_NAME,quotes["auditoria"]["proveedores_activos"])
        self.assertIn(API_NAME,quotes["auditoria"]["proveedores_activos"])
        categories={x["categoria"] for x in compared["comparaciones"]}
        self.assertEqual(categories,{"result","goals","corners","yellow","btts"})
        self.assertEqual(len(compared["comparaciones"])>=5,True)
        self.assertFalse(any(x["categoria"]=="yellow" and x["proveedor"]==FIVE_NAME
                             for x in compared["comparaciones"]))
        self.assertTrue(any(x["categoria"]=="yellow" and x["proveedor"]==API_NAME
                            for x in compared["comparaciones"]))
        self.assertEqual(len(archive["cuotas"]),len(quotes["cuotas"]))
        self.assertNotIn("SECRET",json.dumps([quotes,compared,archive]))

    def test_fallback_provider_unavailable_doesnt_erase_other_quotes(self):
        def broken(*args):raise RuntimeError("SECRET-FOOTBALL")
        raw=collect_free_odds([MATCH],NOW,env={**FIVE_ENV,**API_ENV},
                              five_fetcher=five_fetcher,api_fetcher=broken)
        self.assertEqual(raw["estado"],"PARCIAL")
        self.assertTrue(raw["cuotas"])
        self.assertNotIn("SECRET",json.dumps(raw))

    def test_request_limits_avoid_public_api_exhaustion(self):
        many=[dict(MATCH,id=f"p-{i}",fecha_utc=FDATE) for i in range(30)]
        calls=[]
        def empty(url,headers):
            calls.append(url)
            return {"success":1,"data":[]}
        d=get_five_odds(many,NOW,{**FIVE_ENV,"FREE_ODDS_MAX_FIXTURES":"3"},empty)
        self.assertLessEqual(d["auditoria"]["consultas"],5)
        self.assertFalse(d["cuotas"])


if __name__=="__main__":unittest.main()


class BalancedFiveLeagueQuotaTest(unittest.TestCase):
    def test_free_cap_distributes_over_five_major_leagues(self):
        """El primer lote no debe expulsar Premier/Bundesliga del presupuesto."""
        ligas=[
            ("LaLiga","La Liga"),("Premier League","Premier League"),
            ("Bundesliga","Bundesliga"),("Serie A","Serie A"),
            ("Ligue 1","Ligue 1"),
        ]
        fixtures=[]
        events=[]
        for league_no,(label,provider_label) in enumerate(ligas):
            for game_no in range(4):
                event_id=5100+league_no*10+game_no
                home=f"Home {league_no} {game_no}"
                away=f"Away {league_no} {game_no}"
                fixtures.append({
                    "id":f"{label}-{game_no}","liga":label,
                    "fecha_utc":FDATE,"local":home,"visitante":away})
                events.append({
                    "id":event_id,"league":{"name":provider_label},
                    "teams":{"home":{"name":home},"away":{"name":away}},
                    "kickoff_utc":FDATE
                })
        requests=[]
        def fetcher(url,headers):
            self.assertEqual(headers["Authorization"],"Bearer SECRET-FIVE")
            requests.append(url)
            if "/fixtures?" in url:
                return {"success":1,"data":events}
            event_id=int(url.split("/fixtures/")[1].split("/")[0])
            payload=five_prices()
            payload["data"]["fixture_id"]=event_id
            return payload

        data=get_five_odds(fixtures,NOW,FIVE_ENV,fetcher)
        self.assertEqual(data["estado"],"CON_CUOTAS")
        self.assertEqual(data["auditoria"]["partidos"],14)
        self.assertEqual(data["auditoria"]["consultas"],15)
        self.assertEqual(data["auditoria"]["eventos_emparejados"],20)
        self.assertEqual(set(data["auditoria"]["ligas_seleccionadas"]),
                         set(label for label,_ in ligas))
        self.assertTrue(all(data["auditoria"]["partidos_por_liga"][label]>=2
                            for label,_ in ligas))
        self.assertEqual(len([u for u in requests if "/odds" in u]),14)
        self.assertNotIn("SECRET-FIVE",json.dumps(data))
