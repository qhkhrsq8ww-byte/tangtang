"""Secret scan of the tree + a light git-history pass. Never print a full secret."""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Live-looking material. Placeholders (empty quotes, __MANAGED__) are allowed.
LIVE_PATTERNS = (
    ("aws_akia", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("openai_sk", re.compile(r"sk-[A-Za-z0-9]{24,}")),
    ("slack_xox", re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}")),
    ("pem", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----")),
)

SKIP_DIRS = {".git", "__pycache__", "node_modules", "backups"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".mp3", ".pyc", ".svg", ".woff"}
TEXT_SUFFIXES = {
    ".py", ".sh", ".js", ".mjs", ".json", ".md", ".txt", ".example",
    ".yml", ".yaml", ".plist", ".html", ".env", ".cfg", ".ini",
}


def _redact(match: str) -> str:
    if len(match) <= 4:
        return "***"
    return match[:4] + "***"


def _scan_text(path: Path, text: str) -> list[str]:
    hits = []
    for kind, pat in LIVE_PATTERNS:
        for found in pat.finditer(text):
            raw = found.group(0)
            # Placeholders / docs
            if "MANAGED" in raw or "EXAMPLE" in raw or "YOUR_" in raw:
                continue
            hits.append(f"{path.relative_to(ROOT)}:{kind}:prefix={_redact(raw)}")
    return hits


class TestSecretScanTree(unittest.TestCase):
    def test_no_live_keys_in_runtime_tree(self):
        hits: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
                ".env.example", "crontab.example",
            }:
                if path.name.startswith("."):
                    pass
                else:
                    continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            hits.extend(_scan_text(path, text))
        self.assertEqual(hits, [], f"live-looking secrets (redacted): {hits}")


class TestSecretScanGitHistory(unittest.TestCase):
    def test_no_live_keys_in_recent_history(self):
        """Light `git log -G` scan. Reports kind+prefix only, never the full secret."""
        pattern = r"AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{24,}|BEGIN RSA PRIVATE KEY"
        try:
            proc = subprocess.run(
                [
                    "git", "log", "-p", "--all", "-G", pattern,
                    "--pretty=format:commit %h",
                    "-n", "40",
                    "--", "*.py", "*.sh", "*.json", "*.example", "*.env", "*.md",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            self.fail(f"git history scan failed to run: {type(exc).__name__}")
        body = proc.stdout or ""
        hits = []
        for kind, pat in LIVE_PATTERNS:
            for found in pat.finditer(body):
                raw = found.group(0)
                if "MANAGED" in raw:
                    continue
                hits.append(f"history:{kind}:prefix={_redact(raw)}")
        self.assertEqual(hits, [], f"git history live-looking secrets (redacted): {hits}")


class TestSecretScanEmptyUnknown(unittest.TestCase):
    def test_empty_file_ok(self):
        self.assertEqual(_scan_text(ROOT / "README.md", ""), [])

    def test_placeholder_not_reported(self):
        text = 'QCLAW_LLM_API_KEY="__QCLAW_AUTH_GATEWAY_MANAGED__"\nBAIDU_STT_API_KEY=""\n'
        self.assertEqual(_scan_text(ROOT / ".env.example", text), [])


if __name__ == "__main__":
    unittest.main()
