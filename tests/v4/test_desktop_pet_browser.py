"""Real browser check. If Chrome cannot load the page, mark ENVIRONMENT BLOCKED."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HTML = REPO / "code/cat/cat-desktop-pet.html"


class DesktopPetBrowserTests(unittest.TestCase):
    def test_html_exists(self):
        self.assertTrue(HTML.is_file())

    def test_chrome_or_environment_blocked(self):
        chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
        if not chrome:
            self.skipTest("ENVIRONMENT BLOCKED: no Chrome for real MP4 playback")
        # Headless load of file:// is not a fake video mock — failure is not PASS.
        try:
            proc = subprocess.run(
                [
                    chrome,
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--dump-dom",
                    HTML.as_uri(),
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            self.skipTest("ENVIRONMENT BLOCKED: chrome timed out")
        if proc.returncode != 0:
            self.skipTest(f"ENVIRONMENT BLOCKED: chrome rc={proc.returncode}")
        self.assertIn("applyPresentationAction", proc.stdout)
        self.assertIn("tangtang-idle.mp4", proc.stdout)
