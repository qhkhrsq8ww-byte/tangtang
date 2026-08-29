"""LLM / core must not grow DB, shell, TTS, projection, or Kafka clients."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORE = ROOT / "core"
FORBIDDEN = (
    "import sqlite3",
    "from sqlite3",
    "import psycopg",
    "import redis",
    "import kafka",
    "from kafka",
    "os.system(",
    "subprocess.Popen",
    "import openai",
    "from openai",
    "play_audio",
    "cat-tts",
    "cat-screen",
)


class TestCoreHasNoForbiddenClients(unittest.TestCase):
    def test_core_has_no_llm_io_sinks(self):
        hits = []
        for path in CORE.rglob("*.py"):
            src = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN:
                if needle in src:
                    hits.append(f"{path.relative_to(ROOT)}:{needle}")
        self.assertEqual(hits, [])

    def test_family_json_not_rewritten_this_branch(self):
        family = (ROOT / "data" / "family.json").read_text(encoding="utf-8")
        self.assertIn('"display_name": "洽洽"', family)
        self.assertIn('"display_name": "航航"', family)
        self.assertIn('"member_id": "qiaqia"', family)
        self.assertIn('"member_id": "hanghang"', family)
        self.assertIn('"姐姐"', family)
        self.assertIn('"弟弟"', family)
        from core.identity.resolver import IdentityResolver
        r = IdentityResolver()
        self.assertEqual(r.resolve({"label": "姐姐"}), "qiaqia")
        self.assertEqual(r.resolve({"label": "弟弟"}), "hanghang")


if __name__ == "__main__":
    unittest.main()
