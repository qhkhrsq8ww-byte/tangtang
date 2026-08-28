"""V10 TangTang pack: manifest, PNG+alpha, counts, gait uniqueness, Brain isolation."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.events.event import Event
from core.response.orchestrator import ResponseOrchestrator
from presentation.animation_controller import AnimationController
from presentation.asset_manifest import AssetManifest
from presentation.frame_renderer import FrameRenderer, PixelBuffer, composite_frame
from presentation.mapping import AnimationAction

V10 = ROOT / "assets" / "character" / "tangtang" / "v10"
PNG_SIG = b"\x89PNG\r\n\x1a\n"
REQUIRED_ANIMS = {
    "idle": 16,
    "listen": 12,
    "happy": 12,
    "walk": 12,
    "run": 12,
    "trot": 12,
    "sleep": 12,
    "get_up": 8,
}
SPEC_FIELDS = ("frames", "fps", "loop", "anchor", "width", "height")


def _ihdr(path: Path) -> tuple[int, int, int]:
    with path.open("rb") as fh:
        sig = fh.read(8)
        if sig != PNG_SIG:
            raise AssertionError(f"not a PNG: {path}")
        fh.read(4)
        ctype = fh.read(4)
        if ctype != b"IHDR":
            raise AssertionError(f"missing IHDR: {path}")
        width, height = struct.unpack(">II", fh.read(8))
        bit_depth = fh.read(1)[0]
        color_type = fh.read(1)[0]
        return width, height, color_type


def _hashes(paths: list[Path]) -> list[str]:
    return [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]


class TestV10Manifest(unittest.TestCase):
    def test_manifest_exists_and_lists_required_fields(self) -> None:
        path = V10 / "manifest.json"
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["character"], "tangtang")
        self.assertEqual(data["version"], "v10")
        anims = data["animations"]
        for name, count in REQUIRED_ANIMS.items():
            spec = anims[name]
            for field in SPEC_FIELDS:
                self.assertIn(field, spec, f"{name}.{field}")
            self.assertEqual(spec["frames"], count, name)
            self.assertEqual(spec["width"], 512)
            self.assertEqual(spec["height"], 512)
            self.assertIn("x", spec["anchor"])
            self.assertIn("y", spec["anchor"])
            self.assertGreaterEqual(int(spec["fps"]), 8)
            self.assertLessEqual(int(spec["fps"]), 30)
            self.assertEqual(len(spec["files"]), count)


class TestV10PngAssets(unittest.TestCase):
    def test_declared_files_exist(self) -> None:
        data = json.loads((V10 / "manifest.json").read_text(encoding="utf-8"))
        missing = []
        for name, spec in data["animations"].items():
            for rel in spec["files"]:
                if not (V10 / rel).is_file():
                    missing.append(rel)
        self.assertEqual(missing, [])

    def test_png_has_alpha_and_unified_size(self) -> None:
        data = json.loads((V10 / "manifest.json").read_text(encoding="utf-8"))
        for spec in data["animations"].values():
            for rel in spec["files"]:
                path = V10 / rel
                width, height, color_type = _ihdr(path)
                self.assertEqual((width, height), (512, 512), rel)
                # PNG color type 6 = RGBA
                self.assertEqual(color_type, 6, rel)

    def test_idle_is_sixteen_distinct_frames(self) -> None:
        files = sorted((V10 / "animations" / "idle").glob("idle_*.png"))
        self.assertEqual(len(files), 16)
        self.assertEqual([p.stem for p in files], [f"idle_{i:02d}" for i in range(1, 17)])
        hs = _hashes(files)
        self.assertEqual(len(set(hs)), 16, "idle must not be one still looped 16 times")

    def test_walk_is_twelve_distinct_gait_frames(self) -> None:
        files = sorted((V10 / "animations" / "walk").glob("walk_*.png"))
        self.assertEqual(len(files), 12)
        self.assertEqual([p.stem for p in files], [f"walk_{i:02d}" for i in range(1, 13)])
        hs = _hashes(files)
        self.assertEqual(len(set(hs)), 12, "walk must be a real 12-frame gait, distinct hashes")

    def test_run_is_twelve_distinct_gait_frames(self) -> None:
        files = sorted((V10 / "animations" / "run").glob("run_*.png"))
        self.assertEqual(len(files), 12)
        self.assertEqual([p.stem for p in files], [f"run_{i:02d}" for i in range(1, 13)])
        hs = _hashes(files)
        self.assertEqual(len(set(hs)), 12, "run must be a real 12-frame gait, distinct hashes")

    def test_listen_happy_trot_sleep_get_up_counts(self) -> None:
        for name, count in (("listen", 12), ("happy", 12), ("trot", 12), ("sleep", 12), ("get_up", 8)):
            files = sorted((V10 / "animations" / name).glob(f"{name}_*.png"))
            self.assertEqual(len(files), count, name)
            self.assertEqual(len(set(_hashes(files))), count, name)


class TestV10ControllerNoThrow(unittest.TestCase):
    def test_play_required_anims_does_not_throw(self) -> None:
        ctrl = AnimationController()
        renderer = FrameRenderer(AssetManifest(V10))
        for name in REQUIRED_ANIMS:
            clip = ctrl.play_safe(name)
            self.assertTrue(clip.frames or clip.fallback_used or clip.name in ("idle", name))
            paths = renderer.paths(name)
            self.assertGreaterEqual(len(paths), 1, name)

    def test_pause_resume_speed_crossfade(self) -> None:
        ctrl = AnimationController()
        ctrl.play("idle")
        paused = ctrl.pause()
        self.assertTrue(paused.paused)
        resumed = ctrl.resume()
        self.assertFalse(resumed.paused)
        self.assertEqual(ctrl.set_speed(1.5), 1.5)
        faded = ctrl.cross_fade("listen", 160)
        self.assertGreaterEqual(faded.fade_ms, 100)
        self.assertLessEqual(faded.fade_ms, 200)

    def test_tts_failure_does_not_stop_animation(self) -> None:
        ctrl = AnimationController()

        def boom():
            raise RuntimeError("tts down")

        result = ctrl.deliver_decoupled("happy", tts=boom)
        self.assertTrue(result["animation_ok"])
        self.assertFalse(result["tts_ok"])
        self.assertTrue(result["clip"].frames or result["clip"].fallback_used)

    def test_missing_frame_does_not_crash_brain(self) -> None:
        orch = ResponseOrchestrator(responder=lambda ctx: "汪汪～")
        action = orch.run(
            decision="SPEAK",
            context={"who": {"member_id": "child_9"}},
            action="walk",
        )
        self.assertEqual(action.text, "汪汪～")
        self.assertEqual(action.action, "walk")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "animations" / "idle").mkdir(parents=True)
            src = V10 / "animations" / "idle" / "idle_01.png"
            (dest / "animations" / "idle" / "idle_01.png").write_bytes(src.read_bytes())
            (dest / "manifest.json").write_text(
                json.dumps(
                    {
                        "fallback": "idle",
                        "animations": {
                            "idle": {
                                "frames": 1,
                                "fps": 12,
                                "loop": True,
                                "anchor": {"x": 0.5, "y": 0.957},
                                "width": 512,
                                "height": 512,
                                "files": ["animations/idle/idle_01.png"],
                            },
                            "walk": {
                                "frames": 12,
                                "fps": 12,
                                "loop": True,
                                "anchor": {"x": 0.5, "y": 0.957},
                                "width": 512,
                                "height": 512,
                                "files": [f"animations/walk/walk_{i:02d}.png" for i in range(1, 13)],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            renderer = FrameRenderer(AssetManifest(dest), dest)
            missing = renderer.path("walk", 4)
            self.assertTrue(missing.is_file())
            self.assertEqual(missing.name, "idle_01.png")
            ctrl = AnimationController(root=tmp)
            clip = ctrl.play_safe("walk")
            self.assertEqual(clip.name, "idle")
        # Brain still produces a PresentationAction after the missing-frame path
        again = orch.run(decision="SPEAK", context={"who": {"member_id": "mom"}}, action="idle")
        self.assertEqual(again.text, "汪汪～")

    def test_animation_action_from_brain_label(self) -> None:
        self.assertEqual(AnimationAction("walk").name, "walk")
        self.assertEqual(AnimationAction("跑步").name, "run")
        self.assertEqual(AnimationAction("飞天").name, "idle")


class TestV10NoGhosting(unittest.TestCase):
    def test_consecutive_paints_do_not_keep_previous_rgba(self) -> None:
        w = h = 4
        red = bytearray(w * h * 4)
        red[0:4] = bytes((255, 0, 0, 255))
        blue = bytearray(w * h * 4)
        blue[4:8] = bytes((0, 0, 255, 255))
        first = composite_frame(red, width=w, height=h)
        self.assertEqual(first.pixel(0, 0), (255, 0, 0, 255))
        second = composite_frame(blue, previous=bytes(red), fade_t=1.0, width=w, height=h)
        self.assertEqual(second.pixel(0, 0)[3], 0)
        self.assertEqual(second.pixel(1, 0)[2], 255)
        renderer = FrameRenderer(AssetManifest(V10), V10)
        renderer.buffer = PixelBuffer(w, h)
        renderer.paint(red)
        self.assertEqual(renderer.buffer.pixel(0, 0)[0], 255)
        renderer.paint(blue)
        self.assertEqual(renderer.buffer.pixel(0, 0)[3], 0)
        self.assertNotEqual(renderer.buffer.pixel(1, 0)[3], 0)

    def test_crossfade_caps_previous_opacity(self) -> None:
        w = h = 2
        prev = bytearray(w * h * 4)
        prev[0:4] = bytes((255, 255, 255, 255))
        nxt = bytearray(w * h * 4)
        nxt[4:8] = bytes((0, 0, 0, 255))
        buf = composite_frame(nxt, previous=bytes(prev), fade_t=0.5, width=w, height=h, fade_cap=0.4)
        self.assertLessEqual(buf.pixel(0, 0)[3], int(255 * 0.4) + 2)

    def test_walk_and_run_frames_are_single_subject(self) -> None:
        for name in ("walk", "run"):
            folder = V10 / "animations" / name
            for path in sorted(folder.glob(f"{name}_*.png")):
                runs = _subject_column_runs(path)
                self.assertEqual(len(runs), 1, f"{path.name} runs={runs}")
                width = runs[0][1] - runs[0][0] + 1
                self.assertLessEqual(width, 500, path.name)


def _subject_column_runs(
    path: Path, alpha_min: int = 40, min_col: int = 10, merge_gap: int = 18
) -> list[tuple[int, int]]:
    from PIL import Image

    im = Image.open(path).convert("RGBA")
    pix = im.load()
    width, height = im.size
    occupied = []
    for x in range(width):
        n = 0
        for y in range(height):
            if pix[x, y][3] >= alpha_min:
                n += 1
                if n >= min_col:
                    break
        occupied.append(n >= min_col)
    raw: list[tuple[int, int]] = []
    x = 0
    while x < width:
        if occupied[x]:
            x1 = x
            while x1 < width and occupied[x1]:
                x1 += 1
            raw.append((x, x1 - 1))
            x = x1
        else:
            x += 1
    if not raw:
        return []
    merged = [list(raw[0])]
    for a, b in raw[1:]:
        if a - merged[-1][1] <= merge_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(int(a), int(b)) for a, b in merged]


if __name__ == "__main__":
    unittest.main()
