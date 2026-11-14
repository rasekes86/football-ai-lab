import os
import unittest
from datetime import date,datetime,timedelta,timezone
from football_ai_lab.ensemble import predict
from football_ai_lab.elo import elo_predict
from football_ai_lab.backtest import run_backtest,brier,logloss
from football_ai_lab.odds import fair_from_decimals,get_optional_quotes,find_quote,build_market_rows
from football_ai_lab.pipeline import forecast

def matches(n=550):
    teams=["Arsenal","Chelsea","Liverpool","Everton"]
    start=date(2024,1,1)
    return [{"date":start+timedelta(days=i),"home":teams[i%4],
             "away":teams[(i+1+(i//4)%3)%4] if teams[(i+1+(i//4)%3)%4]!=teams[i%4] else teams[(i+1)%4],
             "home_goals":(i*7)%4,"away_goals":(i*3+1)%3} for i in range(n)]

class AdvancedTests(unittest.TestCase):
    def test_elo_distribution(self):
        p=elo_predict(matches(),"Arsenal","Chelsea",date(2026,1,1))
        self.assertIsNotNone(p)
        self.assertAlmostEqual(sum(p[x] for x in ("home","draw","away")),1,places=9)
    def test_consensus_no_future_data(self):
        rows=matches()
        cutoff=date(2025,6,1)
        a=predict(rows,"Arsenal","Chelsea",cutoff)
        altered=rows+[{"date":date(2027,1,1),"home":"Arsenal","away":"Chelsea","home_goals":70,"away_goals":0}]
        b=predict(altered,"Arsenal","Chelsea",cutoff)
        self.assertIsNotNone(a)
        self.assertEqual(a,b)
        self.assertAlmostEqual(sum(a[k] for k in ("home","draw","away")),1.,places=9)
    def test_walk_forward(self):
        rows,summary=run_backtest({"E0":matches()}, {"E0":("Premier League","eng.1")},max_games=10)
        self.assertGreater(len(rows),0)
        self.assertTrue(all(r["tipo"]=="BACKTEST_RETROSPECTIVO" for r in rows))
        self.assertEqual(summary["Premier League"]["muestra"],len(rows))
        self.assertTrue(0<=summary["Premier League"]["brier_modelo"]<=1)
    def test_scores(self):
        self.assertAlmostEqual(brier([1,0,0],"H"),0)
        self.assertAlmostEqual(logloss([1,0,0],"H"),0)
        self.assertGreater(brier([0,0,1],"H"),0)
    def test_de_vig(self):
        fair,margin=fair_from_decimals((2.1,3.3,3.5))
        self.assertAlmostEqual(sum(fair),1,places=8)
        self.assertGreater(margin,0)
        with self.assertRaises(ValueError):
            fair_from_decimals((1.,2.,3.))
    def test_no_billing_without_key(self):
        before=os.environ.pop("THE_ODDS_API_KEY",None)
        try: self.assertEqual(get_optional_quotes(["SP1"]),{})
        finally:
            if before is not None:os.environ["THE_ODDS_API_KEY"]=before
    def test_market_quote_freshness(self):
        now=datetime(2026,11,14,12,tzinfo=timezone.utc)
        p={"id":"abc","fecha_utc":"2026-11-20T20:00:00+00:00",
           "liga":"LaLiga","local":"Athletic Club","visitante":"Espanyol",
           "prob_local":"0.4","prob_empate":"0.3","prob_visitante":"0.3"}
        event={"home_team":"Athletic Club","away_team":"Espanyol",
               "commence_time":p["fecha_utc"],
               "bookmakers":[{"title":"Prueba","markets":[{"key":"h2h","last_update":"2026-11-14T11:59:00Z",
                       "outcomes":[{"name":"Athletic Club","price":2.1},
                                   {"name":"Draw","price":3.3},
                                   {"name":"Espanyol","price":3.5}]}]}]}
        q=find_quote(p,[event],now)
        self.assertIsNotNone(q)
        self.assertEqual(build_market_rows([p],{"SP1":[event]},now)[0]["estado"],"COMPARACIÓN_SIN_VALIDAR")
        self.assertIsNone(find_quote(p,[event],now+timedelta(days=1)))
    def test_forecast_compatibility(self):
        now=datetime(2026,11,14,12,tzinfo=timezone.utc)
        f={"league":"E0","kickoff":now+timedelta(days=4),"home":"Arsenal","away":"Chelsea"}
        result,rejected=forecast({"E0":matches()},[f],now)
        self.assertEqual(rejected,[])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["tipo"],"REAL")
        self.assertIn("peso_elo",result[0])

if __name__=="__main__":
    unittest.main()
