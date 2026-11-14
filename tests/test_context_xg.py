import json
import unittest
from datetime import datetime,timezone
from football_ai_lab.context_xg import completed_events,extract_xg,collect

NOW=datetime(2026,11,14,19,tzinfo=timezone.utc)
FIXTURE={"league":"SP1","event_id":"1234","fecha_utc":"2026-11-12T20:00:00+00:00",
         "local":"Real Madrid","visitante":"Celta Vigo"}

class Mock:
    def get_event_xg(self,*,event_id):
        return {"status":True,"data":{"source":"understat","teams":[
            {"qualifier":"home","team":{"name":"Real Madrid"},"xg":2.1},
            {"qualifier":"away","team":{"name":"Celta Vigo"},"xg":0.7}]}}

class HistoricalXGTests(unittest.TestCase):
    def test_completed_only(self):
        finished={"id":"1234","date":"2026-11-12T20:00:00Z",
                  "status":{"type":{"name":"STATUS_FINAL","completed":True}},
                  "competitions":[{"competitors":[
                     {"homeAway":"home","team":{"displayName":"Real Madrid"}},
                     {"homeAway":"away","team":{"displayName":"Celta Vigo"}}]}]}
        upcoming=dict(finished,id="999",status={"type":{"name":"STATUS_SCHEDULED"}})
        rows=completed_events(json.dumps({"events":[finished,upcoming]}).encode(),"SP1",NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["event_id"],"1234")
    def test_xg_requires_real_source_and_exact_teams(self):
        x=extract_xg(Mock().get_event_xg(event_id="1234"),FIXTURE)
        self.assertEqual(x["xg_local"],2.1)
        self.assertEqual(x["tipo"],"HISTORICO_FINALIZADO_NO_PRONOSTICO")
        other=Mock().get_event_xg(event_id="1234")
        other["data"]["teams"][0]["team"]["name"]="FC Barcelona"
        self.assertIsNone(extract_xg(other,FIXTURE))
    def test_mock_bounded_retrieval(self):
        event={"id":"1234","date":"2026-11-12T20:00:00Z",
               "status":{"type":{"name":"STATUS_FINAL","completed":True}},
               "competitions":[{"competitors":[
                   {"homeAway":"home","team":{"displayName":"Real Madrid"}},
                   {"homeAway":"away","team":{"displayName":"Celta Vigo"}}]}]}
        def read(url):return json.dumps({"events":[event]}).encode()
        result=collect(NOW,football=Mock(),reader=read)
        self.assertEqual(result["consultas_xg"],5)
        self.assertEqual(len(result["partidos"]),5)
if __name__=="__main__":
    unittest.main()
