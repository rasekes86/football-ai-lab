"""Promoted-team fixtures must be visible without post-kickoff prediction."""
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from football_ai_lab.fixture_catalog import archive, fixture_id
from football_ai_lab.sources import parse_espn_events

def event(state, number, start, home, away):
    return {
        "id":number,"date":start.isoformat(),
        "status":{"type":{"name":state}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"displayName":home}},
            {"homeAway":"away","team":{"displayName":away}}
        ]}]
    }

class FixtureCatalogTests(unittest.TestCase):
    def test_germany_six_matches_even_if_two_already_started(self):
        now=datetime.now(timezone.utc)
        past=now-timedelta(hours=2)
        future=now+timedelta(days=2)
        events={"events":[
            event("STATUS_IN_PROGRESS","1",past,"Bayer Leverkusen","SC Paderborn 07"),
            event("STATUS_FINAL","2",past,"SV Elversberg","SC Freiburg"),
            event("STATUS_SCHEDULED","3",future,"Schalke 04","VfB Stuttgart")
        ]}
        payload=json.dumps(events).encode()
        fixtures=parse_espn_events(payload,"D1",date.today(),include_started=True)
        self.assertEqual(len(fixtures),3)
        self.assertEqual(len(parse_espn_events(payload,"D1",date.today())),1)
        saved=archive([],fixtures,now)
        self.assertEqual(len(saved),3)
        self.assertEqual({x["local"] for x in saved},
                         {"Bayer Leverkusen","SV Elversberg","Schalke 04"})
        self.assertTrue(all(x["pronostico_disponible_al_registrar"]=="NO" for x in saved))
        self.assertEqual(archive(saved,fixtures,now+timedelta(days=4),
                                 {x["id"] for x in saved}),saved)

    def test_cancelled_events_not_in_calendar(self):
        later=datetime.now(timezone.utc)+timedelta(days=2)
        for status in ("STATUS_CANCELED","STATUS_POSTPONED","STATUS_ABANDONED"):
            b=json.dumps({"events":[event(status,"0",later,"A","B")]}).encode()
            self.assertEqual(parse_espn_events(b,"D1",date.today(),True),[])

    def test_same_id_as_original_prediction(self):
        f={"league":"D1","kickoff":datetime(2026,11,21,14,30,tzinfo=timezone.utc),
           "home":"Bayer Leverkusen","away":"SC Paderborn 07"}
        self.assertEqual(fixture_id(f),"D1|202611211430|leverkusen|paderborn")

if __name__=="__main__":unittest.main()
