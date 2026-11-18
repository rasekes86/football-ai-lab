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


class ProviderLeagueFallbackTests(unittest.TestCase):
    """Fixtures present on provider league endpoints must not be lost."""

    def test_premier_bundesliga_fallback_and_club_aliases(self):
        pair=[
            ("Premier League","Manchester City","Fulham",
             "English Premier League","Manchester City FC","Fulham FC",8101,81001),
            ("Bundesliga","Bayern Munich","FC Cologne",
             "German Bundesliga","FC Bayern München","1. FC Köln",8102,81002),
        ]
        fixtures=[
            {"id":f"{league}-{idx}","fecha_utc":FDATE,"liga":league,
             "local":home,"visitante":away}
            for idx,(league,home,away,_,_,_,_,_) in enumerate(pair)
        ]
        catalog=[{"id":leagueid,"name":provider_league}
                 for _,_,_,provider_league,_,_,_,leagueid in pair]
        events=[{"id":eventid,"league":{"name":provider_league},
                 "teams":{"home":{"name":provhome},"away":{"name":provaway}},
                 "kickoff_utc":FDATE}
                for _,_,_,provider_league,provhome,provaway,eventid,_ in pair]
        calls=[]
        def fetch(url,headers):
            calls.append(url)
            self.assertEqual(headers["Authorization"],"Bearer SECRET-FIVE")
            if "/leagues?" in url:
                return {"success":1,"data":catalog}
            if "/leagues/" in url and "/fixtures?" in url:
                ident=int(url.split("/leagues/")[1].split("/")[0])
                return {"success":1,"data":[ev for ev,entry in zip(events,catalog)
                                              if ident==entry["id"]]}
            if "/fixtures?" in url:return {"success":1,"data":[]}
            if "/odds" in url:
                eid=int(url.split("/fixtures/")[1].split("/")[0])
                payload=five_prices()
                payload["data"]["fixture_id"]=eid
                return payload
            raise AssertionError(url)
        result=get_five_odds(fixtures,NOW,FIVE_ENV,fetch)
        self.assertEqual(result["estado"],"CON_CUOTAS")
        audit=result["auditoria"]
        self.assertEqual(audit["eventos_emparejados"],2)
        self.assertEqual(set(audit["consultas_especificas_liga"]),{"E0","D1"})
        self.assertEqual(audit["cobertura_ligas"]["Premier League"]["estado"],"CON_CUOTAS")
        self.assertEqual(audit["cobertura_ligas"]["Bundesliga"]["estado"],"CON_CUOTAS")
        self.assertEqual({q["liga"] for q in result["cuotas"]},
                         {"Premier League","Bundesliga"})
        self.assertLessEqual(audit["consultas"],audit["maximo_consultas_por_ejecucion"])
        self.assertNotIn("SECRET-FIVE",json.dumps(result))

    def test_free_segunda_not_claimed_without_community_access(self):
        match={"id":"SP2-44","fecha_utc":FDATE,"liga":"Segunda División",
               "local":"FC Andorra","visitante":"Leganés"}
        def fetch(url,headers):
            if "/fixtures?" in url:return {"success":1,"data":[]}
            raise AssertionError("No Community Access: unexpected API request")
        data=get_five_odds([match],NOW,FIVE_ENV,fetch)
        coverage=data["auditoria"]["cobertura_ligas"]["Segunda División"]
        self.assertEqual(coverage["estado"],"NO_INCLUIDA_EN_FREE")
        self.assertEqual(data["auditoria"]["consultas"],1)

    def test_authorized_community_access_discovers_segunda(self):
        match={"id":"SP2-44","fecha_utc":FDATE,"liga":"Segunda División",
               "local":"FC Andorra","visitante":"Leganés"}
        event={"id":89001,"league":{"name":"Spain Segunda Division"},
               "teams":{"home":{"name":"FC Andorra"},
                        "away":{"name":"Leganés"}},"kickoff_utc":FDATE}
        calls=[]
        def fetch(url,headers):
            calls.append(url)
            if "/leagues?" in url and "country=ES" in url:
                return {"success":1,"data":[
                    {"id":902,"name":"Spain Segunda Division"}]}
            if "/leagues/902/fixtures?" in url:
                return {"success":1,"data":[event]}
            if "/fixtures?" in url:return {"success":1,"data":[]}
            if "/odds" in url:
                payload=five_prices()
                payload["data"]["fixture_id"]=event["id"]
                return payload
            raise AssertionError(url)
        env={**FIVE_ENV,"ENABLE_FIVE_SEGUNDA":"true"}
        data=get_five_odds([match],NOW,env,fetch)
        self.assertEqual(data["estado"],"CON_CUOTAS")
        self.assertEqual(data["auditoria"]["cobertura_ligas"]["Segunda División"]["estado"],
                         "CON_CUOTAS")
        self.assertTrue(any("/leagues/902/fixtures?" in c for c in calls))

    def test_second_page_is_used_only_when_provider_declares_more(self):
        match={"id":"E0-99","fecha_utc":FDATE,"liga":"Premier League",
               "local":"Manchester City","visitante":"Fulham"}
        event={"id":91001,"league":{"name":"Premier League"},
               "teams":{"home":{"name":"Manchester City"},
                        "away":{"name":"Fulham"}},"kickoff_utc":FDATE}
        called=[]
        def fetch(url,headers):
            called.append(url)
            if "/fixtures?" in url:
                if "&page=1" in url:
                    return {"success":1,"data":[],"pagination":{"has_more":True}}
                return {"success":1,"data":[event],"pagination":{"has_more":False}}
            if "/odds" in url:
                payload=five_prices()
                payload["data"]["fixture_id"]=event["id"]
                return payload
            raise AssertionError(url)
        data=get_five_odds([match],NOW,FIVE_ENV,fetch)
        self.assertEqual(data["auditoria"]["consultas"],3)
        self.assertEqual(data["auditoria"]["eventos_emparejados"],1)
        self.assertEqual(data["auditoria"]["cobertura_ligas"]["Premier League"]["estado"],
                         "CON_CUOTAS")
        self.assertTrue(any("page=2" in u for u in called))


class ConservativeCoverageFixesTests(unittest.TestCase):
    def test_verified_celta_alias_never_matches_celta_fortuna(self):
        from football_ai_lab.free_odds import _same_team
        self.assertTrue(_same_team("Celta Vigo","Real Club Celta de Vigo"))
        self.assertTrue(_same_team("RC Celta","Celta de Vigo"))
        self.assertFalse(_same_team("RC Celta Fortuna","Real Club Celta de Vigo"))

    def test_season_suffixed_league_preserves_division(self):
        from football_ai_lab.free_odds import _league_code
        self.assertEqual(_league_code("Spanish La Liga 2026/2027"),"SP1")
        self.assertEqual(_league_code("Germany Bundesliga I 2026-27"),"D1")
        self.assertIsNone(_league_code("Germany Bundesliga II 2026-27"))

    def test_midnight_border_does_not_need_an_extra_calendar_request(self):
        from urllib.parse import urlsplit,parse_qs
        kickoff="2026-11-20T00:45:00Z"
        provider="2026-11-19T23:45:00Z"
        match={**MATCH,"id":"midnight","fecha_utc":kickoff}
        event={**five_event(),"kickoff_utc":provider}
        calls=[]
        def fetch(url,headers):
            calls.append(url)
            if "/fixtures?" in url:
                qs=parse_qs(urlsplit(url).query)
                when=int(datetime.fromisoformat(provider.replace("Z","+00:00")).timestamp())
                inside=int(qs["start_time"][0])<=when<int(qs["end_time"][0])
                return {"success":1,"data":[event] if inside else []}
            if "/odds" in url:return five_prices()
            raise AssertionError(url)
        result=get_five_odds([match],NOW,FIVE_ENV,fetch)
        self.assertEqual(result["estado"],"CON_CUOTAS")
        self.assertEqual(result["auditoria"]["consultas"],2)
        self.assertTrue(result["cuotas"])
        self.assertEqual(len([u for u in calls if "/fixtures?" in u]),1)

    def test_calendar_window_never_exceeds_one_day_even_for_both_extremes(self):
        from urllib.parse import urlsplit,parse_qs
        # 28-hour windows previously caused invalid_time_window (HTTP 400).
        # Two same-day fixtures near both extremes cannot fit both ±2h,
        # so preserve the original UTC day, without sending a second request.
        games=[
            {**MATCH,"id":"early","fecha_utc":"2026-11-20T00:20:00Z"},
            {**MATCH,"id":"late","fecha_utc":"2026-11-20T23:40:00Z"},
        ]
        windows=[]
        def strict_provider(url,headers):
            if "/fixtures?" in url:
                qs=parse_qs(urlsplit(url).query)
                start,end=(int(qs[k][0]) for k in ("start_time","end_time"))
                windows.append((start,end))
                if end-start>86400:
                    raise RuntimeError("invalid_time_window")
                return {"success":1,"data":[]}
            raise AssertionError(url)
        result=get_five_odds(games,NOW,FIVE_ENV,strict_provider)
        self.assertEqual(windows and len(windows),1)
        self.assertEqual(windows[0][1]-windows[0][0],86400)
        self.assertEqual(result["auditoria"]["errores"],0)
        self.assertEqual(result["auditoria"]["consultas"],1)
        self.assertEqual(result["estado"],"SIN_COINCIDENCIAS")

    def test_calendar_midnight_shift_is_also_bounded_to_24_hours(self):
        from urllib.parse import urlsplit,parse_qs
        match={**MATCH,"id":"near-midnight",
               "fecha_utc":"2026-11-20T00:45:00Z"}
        event={**five_event(),"kickoff_utc":"2026-11-19T23:45:00Z"}
        windows=[]
        def strict_provider(url,headers):
            if "/fixtures?" in url:
                qs=parse_qs(urlsplit(url).query)
                start,end=(int(qs[k][0]) for k in ("start_time","end_time"))
                windows.append((start,end))
                self.assertEqual(end-start,86400)
                return {"success":1,"data":[event]}
            if "/odds" in url:return five_prices()
            raise AssertionError(url)
        result=get_five_odds([match],NOW,FIVE_ENV,strict_provider)
        self.assertEqual(result["estado"],"CON_CUOTAS")
        self.assertEqual(result["auditoria"]["errores"],0)
        self.assertEqual(result["auditoria"]["consultas"],2)
        self.assertEqual(len(windows),1)
        midnight=datetime(2026,11,20,tzinfo=timezone.utc).timestamp()
        self.assertLess(windows[0][0],midnight)

    def test_calendar_kickoff_conflict_does_not_attach_odds_and_is_diagnosed(self):
        event={**five_event(),"kickoff_utc":"2026-11-20T16:00:00Z"}
        calls=[]
        def fetch(url,headers):
            calls.append(url)
            if "/fixtures?" in url:return {"success":1,"data":[event]}
            raise AssertionError("No se debe consultar cuota con hora incompatible")
        result=get_five_odds([MATCH],NOW,FIVE_ENV,fetch)
        audit=result["auditoria"]
        self.assertEqual(result["cuotas"],[])
        self.assertEqual(audit["consultas"],1)
        self.assertEqual(audit["cobertura_ligas"]["LaLiga"]["motivos_descartados"].get(
            "mismos_equipos_hora_incompatible"),1)
        self.assertEqual(audit["partidos_sin_evento_verificado"],1)
        self.assertEqual(result["estado_consultas"]["fixtures"][FID]["motivo_consulta"],
                         "SIN_EVENTO_VERIFICADO")

    def test_provider_error_does_not_mark_unmatched_or_mutate_history(self):
        def broken(url,headers):
            raise RuntimeError("Proveedor fuera de servicio")
        result=get_five_odds([MATCH],NOW,FIVE_ENV,broken)
        self.assertGreater(result["auditoria"]["errores"],0)
        self.assertEqual(result["auditoria"]["partidos_sin_evento_verificado"],0)
        self.assertNotIn(FID,result["estado_consultas"]["fixtures"])


class OfficialBundesligaNamingTests(unittest.TestCase):
    """La Bundesliga I publicada por el proveedor no debe perderse en la API."""

    @staticmethod
    def _fixture():
        return {
            "id": "D1|202611201930|bayern|cologne",
            "fecha_utc": "2026-11-20T19:30:00Z",
            "liga": "Bundesliga",
            "local": "Bayern Munich",
            "visitante": "FC Cologne",
        }

    @staticmethod
    def _event():
        return {
            "id": 721993,
            "league": {"id": 686337048, "name": "Germany Bundesliga I"},
            "teams": {
                "home": {"name": "Bayern Munich"},
                "away": {"name": "1. FC Köln"},
            },
            "kickoff_utc": "2026-11-20T19:30:00Z",
            "status": "scheduled",
        }

    def test_official_name_is_recognized_and_second_division_is_not(self):
        from football_ai_lab.free_odds import _league_code
        self.assertEqual(_league_code("Germany Bundesliga I"), "D1")
        self.assertEqual(_league_code("German Bundesliga I"), "D1")
        self.assertIsNone(_league_code("Germany Bundesliga II"))
        self.assertIsNone(_league_code("Germany 2. Bundesliga"))

    def test_free_daily_window_prices_bundesliga_i_without_extra_requests(self):
        event = self._event()
        calls = []

        def fetch(url,headers):
            calls.append(url)
            self.assertEqual(headers["Authorization"], "Bearer SECRET-FIVE")
            if "/fixtures?" in url:
                return {"success": 1, "data": [event]}
            if f"/fixtures/{event['id']}/odds" in url:
                payload = five_prices()
                payload["data"]["fixture_id"] = event["id"]
                return payload
            raise AssertionError("No extra API endpoints expected")

        result = get_five_odds([self._fixture()], NOW, FIVE_ENV, fetch)
        audit = result["auditoria"]
        self.assertEqual(result["estado"], "CON_CUOTAS")
        self.assertEqual(audit["cobertura_ligas"]["Bundesliga"]["estado"], "CON_CUOTAS")
        self.assertEqual(audit["cobertura_ligas"]["Bundesliga"]["eventos_proveedor"], 1)
        self.assertEqual(audit["partidos_por_liga"]["Bundesliga"], 1)
        self.assertEqual(audit["consultas"], 2)
        self.assertEqual({q["liga"] for q in result["cuotas"]}, {"Bundesliga"})
        self.assertFalse(any("/leagues?" in url for url in calls))
        self.assertNotIn("SECRET-FIVE", json.dumps(result))

    def test_bundesliga_catalog_fallback_uses_unambiguous_canonical_id(self):
        event = self._event()
        calls = []

        def fetch(url,headers):
            calls.append(url)
            if "/leagues?" in url:
                self.assertIn("country=DE", url)
                return {"success": 1, "data": [
                    {"id": 686337048, "name": "Germany Bundesliga I"},
                    {"id": 686337049, "name": "Germany Bundesliga II"},
                ]}
            if "/leagues/686337048/fixtures?" in url:
                return {"success": 1, "data": [event]}
            if "/fixtures?" in url:
                return {"success": 1, "data": []}
            if f"/fixtures/{event['id']}/odds" in url:
                payload = five_prices()
                payload["data"]["fixture_id"] = event["id"]
                return payload
            raise AssertionError("Unknown API endpoint")

        result = get_five_odds([self._fixture()], NOW, FIVE_ENV, fetch)
        audit = result["auditoria"]
        self.assertEqual(result["estado"], "CON_CUOTAS")
        self.assertEqual(audit["cobertura_ligas"]["Bundesliga"]["estado"], "CON_CUOTAS")
        self.assertEqual(audit["consultas_especificas_liga"], ["D1"])
        self.assertEqual(audit["ligas_catalogo_detectadas"], ["D1"])
        self.assertEqual(audit["errores"], 0)
        self.assertLessEqual(audit["consultas"], audit["maximo_consultas_por_ejecucion"])
        self.assertFalse(any("/leagues/686337049/fixtures" in url for url in calls))
        self.assertEqual({q["liga"] for q in result["cuotas"]}, {"Bundesliga"})
