"""The Pages deployment publishes only the 17 public model feeds."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_feeds.py"
spec = importlib.util.spec_from_file_location("football_publish_feeds", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublishedFeedsTests(unittest.TestCase):
    def test_same_origin_snapshot_only_contains_allowlisted_sources(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            for name in module.FILES:
                (root / "output" / name).write_text(
                    "{}" if name.endswith(".json") else "id,liga\n1,LaLiga\n",
                    encoding="utf-8")
            (root / "output" / ".env").write_text(
                "FIVEDOLLAR_API_KEY=DO_NOT_PUBLISH", encoding="utf-8")
            (root / "output" / "private_key.txt").write_text(
                "SECRET", encoding="utf-8")
            copied = module.publish(root)
            self.assertEqual(set(copied), set(module.FILES))
            published = {p.name for p in (root / "site" / "published").iterdir()}
            self.assertEqual(published, set(module.FILES))
            self.assertNotIn(".env", published)
            self.assertNotIn("private_key.txt", published)

    def test_missing_public_feed_refuses_incomplete_deployment(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            with self.assertRaises(FileNotFoundError):
                module.publish(root)


if __name__ == "__main__":
    unittest.main()
