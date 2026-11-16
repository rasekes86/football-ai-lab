import json
import tempfile
import unittest
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_crests.py"
spec = spec_from_file_location("build_crests", SCRIPT)
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


class CrestTests(unittest.TestCase):
    def test_exact_aliases_and_fallback_without_misidentification(self):
        clubs = [
            {"names": ["CD Tenerife", "Tenerife"], "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/1.png"},
            {"names": ["Celta Vigo", "Celta"], "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/2.png"},
            {"names": ["Celta Fortuna", "Celta B"], "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/3.png"},
        ]
        found = mod.assign_crests({"Tenerife", "RC Celta Fortuna", "Celta Vigo", "Teneriffa"}, clubs)
        self.assertEqual(len(found), 3)
        self.assertIn("/3.png", found["RC Celta Fortuna"])
        self.assertIn("/2.png", found["Celta Vigo"])
        self.assertNotIn("Teneriffa", found)

    def test_ambiguous_names_remain_without_logo(self):
        clubs = [
            {"names":["Same FC"],"logo":"https://a.espncdn.com/i/teamlogos/soccer/500/5.png"},
            {"names":["Same FC"],"logo":"https://a.espncdn.com/i/teamlogos/soccer/500/6.png"},
        ]
        self.assertEqual(mod.assign_crests({"Same FC"}, clubs), {})

    def test_six_leagues_and_espn_url_check(self):
        self.assertEqual(len(mod.LEAGUES), 6)
        data={"sports":[{"leagues":[{"teams":[
            {"team":{"displayName":"Cádiz CF","logos":[
                {"href":"https://a.espncdn.com/i/teamlogos/soccer/500/8.png"}
            ]}},
            {"team":{"displayName":"Evil club","logo":"https://example.com/not-trusted.svg"}},
        ]}]}]}
        result=mod.club_records(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["names"][0], "Cádiz CF")

    def test_generated_manifest_for_all_match_locations(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"historico_predicciones.csv").write_text(
                "liga,local,visitante\nSegunda División,Tenerife,Ceuta\n",encoding="utf-8")
            fake={"sports":[{"leagues":[{"teams":[
                {"team":{"displayName":"CD Tenerife","logo":"https://a.espncdn.com/i/teamlogos/soccer/500/1.png"}},
                {"team":{"displayName":"AD Ceuta","logo":"https://a.espncdn.com/i/teamlogos/soccer/500/9.png"}},
            ]}]}]}
            target=root/"site"/"crests.json"
            payload=mod.build(root,target,fetcher=lambda url:fake)
            self.assertEqual(len(payload["teams"]), 2)
            self.assertIn("Segunda División|Tenerife",payload["teams"])
            self.assertIn("Segunda División|Ceuta",payload["teams"])
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["version"],1)


if __name__ == "__main__":
    unittest.main()
