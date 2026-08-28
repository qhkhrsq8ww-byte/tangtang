"""V10 character PNGs: readable, unified size, stable anchor, declared fps/loop."""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ASSET = ROOT / "assets" / "character" / "tangtang"
PNG_SIG = b"\x89PNG\r\n\x1a\n"
REQUIRED_FIELDS = (
    "animation_name",
    "frame_count",
    "fps",
    "loop",
    "anchor",
    "preferred_state",
    "fallback_state",
)
SPEC_COUNTS = {
    "idle": 8,
    "blink": 6,
    "listen": 8,
    "happy": 8,
    "encourage": 8,
    "sad": 8,
    "walk": 12,
    "run": 12,
    "sit": 8,
    "lie": 8,
    "sleep": 8,
}


def png_ihdr(path: Path) -> tuple[int, int, int]:
    with path.open("rb") as fh:
        sig = fh.read(8)
        if sig != PNG_SIG:
            raise AssertionError(f"not a PNG: {path}")
        _length = fh.read(4)
        ctype = fh.read(4)
        if ctype != b"IHDR":
            raise AssertionError(f"missing IHDR: {path}")
        width, height = struct.unpack(">II", fh.read(8))
        bit_depth = fh.read(1)[0]
        return width, height, bit_depth


class TestMetadata(unittest.TestCase):
    def test_metadata_has_required_fields(self) -> None:
        meta = json.loads((ASSET / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["expected_png_count"], 368)
        self.assertEqual(meta["projection"]["character"], [512, 512])
        self.assertEqual(meta["projection"]["canvas"], [1920, 1080])
        self.assertEqual(meta["projection"]["anchor"], {"x": 0.5, "y": 1.0})
        self.assertEqual(meta["projection"]["scale"], 1.0)
        anims = meta["animations"]
        for name, count in SPEC_COUNTS.items():
            spec = anims[name]
            for field in REQUIRED_FIELDS:
                self.assertIn(field, spec, f"{name}.{field}")
            self.assertEqual(spec["frame_count"], count, name)
            self.assertEqual(spec["anchor"], {"x": 0.5, "y": 1.0})
            self.assertLessEqual(int(spec["fps"]), 12)
            if name == "sleep":
                self.assertLessEqual(int(spec["fps"]), 4)
                self.assertTrue(spec["loop"])
            if name in ("walk", "run"):
                self.assertTrue(spec["loop"])
                self.assertTrue(spec["continuous"])
                self.assertGreaterEqual(int(spec["min_playable"]), 8)


class TestPngReadableAndSized(unittest.TestCase):
    def test_all_pngs_readable(self) -> None:
        pngs = list(ASSET.rglob("*.png"))
        self.assertGreaterEqual(len(pngs), 1)
        for path in pngs:
            with path.open("rb") as fh:
                self.assertEqual(fh.read(8), PNG_SIG, path)

    def test_character_frames_unified_512(self) -> None:
        skip = {"TangTang-V10-character-design-sheet.png", "living_room_cream.png"}
        for path in ASSET.rglob("*.png"):
            if path.name in skip:
                continue
            rel = path.relative_to(ASSET).as_posix()
            width, height, _depth = png_ihdr(path)
            if "/256/" in f"/{rel}":
                self.assertEqual((width, height), (256, 256), rel)
            elif "/128/" in f"/{rel}":
                self.assertEqual((width, height), (128, 128), rel)
            else:
                self.assertEqual((width, height), (512, 512), rel)

    def test_walk_has_twelve_continuous_files(self) -> None:
        files = sorted((ASSET / "walk").glob("*.png"))
        self.assertEqual(len(files), 12)
        self.assertEqual([p.stem for p in files], [f"{i:02d}" for i in range(12)])

    def test_run_has_at_least_eight_continuous_files(self) -> None:
        files = sorted((ASSET / "run").glob("*.png"))
        self.assertGreaterEqual(len(files), 8)
        self.assertEqual([p.stem for p in files], [f"{i:02d}" for i in range(len(files))])

    def test_base_five_angles_and_eight_expressions(self) -> None:
        for name in ("front", "three_quarter_left", "side_left", "back", "three_quarter_right"):
            self.assertTrue((ASSET / "base" / f"{name}.png").is_file(), name)
        for name in ("default", "happy", "blink", "tilt", "encourage", "expectant", "sad", "sleepy"):
            self.assertTrue((ASSET / "expressions" / f"{name}.png").is_file(), name)

    def test_design_sheet_present(self) -> None:
        self.assertTrue((ASSET / "TangTang-V10-character-design-sheet.png").is_file())

    def test_png_count_is_documented_short_of_368(self) -> None:
        count = len(list(ASSET.rglob("*.png")))
        meta = json.loads((ASSET / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["expected_png_count"], 368)
        # Honest inventory: do not invent filler pixels to hit 368.
        self.assertLess(count, 368)
        self.assertGreater(count, 100)


if __name__ == "__main__":
    unittest.main()
