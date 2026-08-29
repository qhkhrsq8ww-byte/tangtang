#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenClaw 田间报告：只写标签，推到 GitHub。不写听写、原话、音频路径。"""
from __future__ import print_function

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

CAT_DIR = os.path.dirname(os.path.abspath(__file__))
if CAT_DIR not in sys.path:
    sys.path.insert(0, CAT_DIR)

SCHEMA_VERSION = 1
STEP_IDS = ("ask", "english", "move", "rest")
SCENES = ("joined", "oppose", "silent", "defer", "wont", "unclear", "skip")
SCENE_ALIAS = {
    "timeout": "silent",
    "perfunctory": "silent",
    "stop": "skip",
    "stop_today": "skip",
    "muted": "skip",
    "cool": "skip",
    "adult_interrupt": "skip",
    "joined_soft": "joined",
    "none": "skip",
}
FORBIDDEN_KEYS = (
    "transcript",
    "text",
    "stt",
    "utterance",
    "quote",
    "pcm",
    "words",
    "audio",
    "wav",
    "mp3",
)
FORBIDDEN_KEY_RE = re.compile(
    r"(transcript|utterance|(^|_)(stt|quote|pcm|words)(_|$)|(^|_)text$)",
    re.I,
)
CJK_RE = re.compile(r"[\u3400-\u9fff]")
PHONE_RE = re.compile(r"(?:\+?86)?1[3-9]\d{9}|\d{3,4}-\d{8}")
AUDIO_RE = re.compile(r"\.(wav|mp3|pcm|m4a|aac)(\b|$)|tangtang_turn|/tmp/.*\.(pcm|wav)", re.I)
# 糖糖已知短模板（报告默认不写入；仅作消毒白名单）
KNOWN_TEMPLATES = (
    "糖糖在客厅听你说一句。不说也没关系。",
    "linux-no-mic",
    "darwin-default",
    "linux-none",
    "hwcheck-no-record",
    "ffmpeg-missing",
    "working tree dirty, wrote file, skipped push",
)


def shanghai_now():
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=8)))


def shanghai_date(now=None):
    fake = (os.environ.get("TANGTANG_FAKE_TODAY") or "").strip()
    if fake:
        return fake
    return (now or shanghai_now()).strftime("%Y-%m-%d")


def isoformat_sh(now=None):
    now = now or shanghai_now()
    s = now.isoformat(timespec="seconds")
    return s


def repo_root(start=None):
    here = os.path.abspath(start or os.path.join(CAT_DIR, "..", ".."))
    cur = here
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, ".git")) or os.path.isfile(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return here


def git_out(repo, args, timeout=20):
    try:
        p = subprocess.run(
            ["git"] + list(args),
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            universal_newlines=True,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def git_meta(repo=None):
    repo = repo or repo_root()
    rc, head, _ = git_out(repo, ["rev-parse", "HEAD"])
    if rc != 0:
        head = ""
    rc, branch, _ = git_out(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0:
        branch = ""
    return head, branch, repo


def which_ok(name):
    return bool(shutil.which(name))


def ffmpeg_bin():
    bundled = os.path.join(CAT_DIR, "bin", "ffmpeg")
    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled
    return shutil.which("ffmpeg") or ""


def host_name():
    plat = sys.platform
    if plat == "darwin":
        return "Darwin"
    if plat.startswith("linux"):
        return "Linux"
    if plat.startswith("win"):
        return "Windows"
    return "unknown"


def hwcheck():
    host = host_name()
    ff = ffmpeg_bin()
    sox = which_ok("sox") or which_ok("rec")
    say = which_ok("say")
    ffmpeg = bool(ff)
    avf = host == "Darwin" and ffmpeg
    if host == "Darwin":
        default_output = "darwin-default"
        notes = "hwcheck-no-record"
        record_ok = False
    else:
        default_output = "linux-none"
        notes = "linux-no-mic"
        record_ok = False
        avf = False
    if not ffmpeg:
        notes = "ffmpeg-missing"
    return {
        "os": host,
        "sox": bool(sox),
        "ffmpeg": bool(ffmpeg),
        "say": bool(say),
        "avfoundation_mic": bool(avf),
        "default_output": default_output,
        "record_ok": bool(record_ok),
        "notes": notes,
    }


def normalize_scene(raw):
    s = (raw or "").strip().lower()
    s = SCENE_ALIAS.get(s, s)
    if s in SCENES:
        return s
    return "skip"


def persona_for(who):
    if who == "qiaqia":
        return "friend"
    return "play"


def empty_counts():
    return {k: 0 for k in SCENES}


def count_scenes(steps):
    counts = empty_counts()
    for row in steps:
        scene = normalize_scene(row.get("scene"))
        counts[scene] = counts.get(scene, 0) + 1
    return counts


def make_step(step_id, scheduled_hour, ran_at, spoke, window_opened, scene, persona, reply_spoke):
    return {
        "id": step_id if step_id in STEP_IDS else "ask",
        "scheduled_hour": int(scheduled_hour),
        "ran_at": ran_at or "",
        "spoke": bool(spoke),
        "window_opened": bool(window_opened),
        "scene": normalize_scene(scene),
        "persona": persona if persona in ("play", "friend", "elder") else "play",
        "reply_spoke": bool(reply_spoke),
    }


def fixture_steps(who="hanghang", now=None):
    """silent + joined 标签夹具，不含听写。"""
    now = now or shanghai_now()
    ran = isoformat_sh(now)
    persona = persona_for(who)
    hour = int(os.environ.get("TANGTANG_OPENCLAW_HOUR") or "14")
    scenes = ("silent", "joined", "silent", "skip")
    out = []
    for i, sid in enumerate(STEP_IDS):
        scene = scenes[i]
        opened = scene != "skip"
        out.append(
            make_step(
                sid, hour, ran, False, opened, scene, persona, scene == "joined",
            )
        )
    return out


def walk_keys(obj, acc=None):
    acc = acc if acc is not None else []
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.append(str(k))
            walk_keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            walk_keys(v, acc)
    return acc


def walk_strings(obj, acc=None):
    acc = acc if acc is not None else []
    if isinstance(obj, dict):
        for v in obj.values():
            walk_strings(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            walk_strings(v, acc)
    elif isinstance(obj, str):
        acc.append(obj)
    return acc


def cjk_count(s):
    return len(CJK_RE.findall(s or ""))


def is_known_template(s):
    t = (s or "").strip()
    if t in KNOWN_TEMPLATES:
        return True
    for k in KNOWN_TEMPLATES:
        if k and k in t and cjk_count(t) <= cjk_count(k) + 4:
            return True
    return False


def sanitize_err(obj):
    """Return list of error strings. Empty = ok."""
    errs = []
    for key in walk_keys(obj):
        low = key.lower()
        if low in FORBIDDEN_KEYS or FORBIDDEN_KEY_RE.search(key):
            errs.append("forbidden key: %s" % key)
    for s in walk_strings(obj):
        if PHONE_RE.search(s or ""):
            errs.append("phone-like string")
        if AUDIO_RE.search(s or ""):
            errs.append("audio path")
        if cjk_count(s) > 40 and not is_known_template(s):
            errs.append("long cjk (possible child sentence)")
    return errs


def sanitize_or_die(obj, label="report"):
    errs = sanitize_err(obj)
    if errs:
        sys.stderr.write("sanitize fail %s: %s\n" % (label, "; ".join(errs[:8])))
        sys.exit(2)
    return obj


def clip_fail(text, n=200):
    s = re.sub(r"\s+", " ", (text or "")).strip()
    s = PHONE_RE.sub("[redacted]", s)
    s = AUDIO_RE.sub("[audio]", s)
    if cjk_count(s) > 40:
        s = "stderr-clipped"
    return s[:n]


def build_report(who="hanghang", rest_day=True, hw=None, steps=None, failures=None, now=None):
    now = now or shanghai_now()
    who = "qiaqia" if who in ("qiaqia", "洽洽") else "hanghang"
    head, branch, _repo = git_meta()
    steps = steps or fixture_steps(who, now)
    cleaned = []
    for row in steps:
        cleaned.append(
            make_step(
                row.get("id"),
                row.get("scheduled_hour") or 14,
                row.get("ran_at") or isoformat_sh(now),
                row.get("spoke"),
                row.get("window_opened"),
                row.get("scene"),
                row.get("persona") or persona_for(who),
                row.get("reply_spoke"),
            )
        )
    if len(cleaned) < 4:
        hour = int(os.environ.get("TANGTANG_OPENCLAW_HOUR") or "14")
        have = {r["id"] for r in cleaned}
        for sid in STEP_IDS:
            if sid not in have:
                cleaned.append(
                    make_step(sid, hour, isoformat_sh(now), False, False, "skip", persona_for(who), False)
                )
        order = {s: i for i, s in enumerate(STEP_IDS)}
        cleaned.sort(key=lambda r: order.get(r["id"], 9))
        cleaned = cleaned[:4]
    fails = []
    for f in failures or []:
        if not isinstance(f, dict):
            continue
        fails.append(
            {
                "command": str(f.get("command") or "unknown")[:80],
                "stderr": clip_fail(f.get("stderr") or ""),
            }
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_sh(now),
        "host": host_name(),
        "git_head": head,
        "branch": branch,
        "who": who,
        "rest_day": bool(rest_day),
        "hwcheck": hw or hwcheck(),
        "steps": cleaned,
        "counts": count_scenes(cleaned),
        "failures": fails,
    }
    return sanitize_or_die(report)


def render_txt(report):
    lines = []
    lines.append("OpenClaw 田间报告 %s" % (report.get("generated_at") or "")[:10])
    lines.append("host=%s who=%s rest_day=%s branch=%s" % (
        report.get("host"), report.get("who"), report.get("rest_day"), report.get("branch"),
    ))
    hw = report.get("hwcheck") or {}
    lines.append(
        "hwcheck os=%s sox=%s ffmpeg=%s say=%s mic=%s out=%s rec=%s notes=%s"
        % (
            hw.get("os"), hw.get("sox"), hw.get("ffmpeg"), hw.get("say"),
            hw.get("avfoundation_mic"), hw.get("default_output"),
            hw.get("record_ok"), hw.get("notes"),
        )
    )
    for row in report.get("steps") or []:
        lines.append(
            "%s hour=%s scene=%s spoke=%s window=%s reply=%s"
            % (
                row.get("id"), row.get("scheduled_hour"), row.get("scene"),
                row.get("spoke"), row.get("window_opened"), row.get("reply_spoke"),
            )
        )
    c = report.get("counts") or {}
    lines.append("counts " + " ".join("%s=%s" % (k, c.get(k, 0)) for k in SCENES))
    nfail = len(report.get("failures") or [])
    lines.append("failures=%s" % nfail)
    lines.append("报告里只许标签，不许小朋友原话。")
    return "\n".join(lines) + "\n"


def report_paths(day=None, repo=None):
    repo = repo or repo_root()
    day = day or shanghai_date()
    folder = os.path.join(repo, "reports", "openclaw")
    return (
        os.path.join(folder, "%s.json" % day),
        os.path.join(folder, "%s.txt" % day),
        folder,
        day,
        repo,
    )


def local_copy_path(day=None):
    try:
        from tangtang_paths import data_dir

        root = data_dir()
    except Exception:
        root = os.environ.get("TANGTANG_DATA_DIR") or ""
        if not root:
            return ""
    day = day or shanghai_date()
    return os.path.join(root, "openclaw-%s.json" % day)


def write_report(report, repo=None, also_txt=True, also_local=True):
    json_path, txt_path, folder, day, repo = report_paths(
        day=shanghai_date(), repo=repo
    )
    os.makedirs(folder, exist_ok=True)
    sanitize_or_die(report, json_path)
    tmp = json_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, json_path)
    if also_txt:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(render_txt(report))
    local = ""
    if also_local:
        local = local_copy_path(day)
        if local:
            try:
                os.makedirs(os.path.dirname(local), exist_ok=True)
                shutil.copy2(json_path, local)
            except OSError:
                local = ""
    return json_path, txt_path if also_txt else "", local


def porcelain_unrelated(repo, keep):
    rc, out, err = git_out(repo, ["status", "--porcelain", "--untracked-files=normal"])
    if rc != 0:
        return ["git-status-failed"]
    keep_abs = set(os.path.abspath(p) for p in keep if p)
    dirty = []
    for line in (out or "").splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[-1]
        abs_p = os.path.abspath(os.path.join(repo, path))
        if abs_p in keep_abs:
            continue
        # ignore reports/openclaw dir itself if empty placeholder
        if path.rstrip("/") in ("reports/openclaw", "reports"):
            continue
        dirty.append(path)
    return dirty


def field_branch_name(day):
    return "cursor/openclaw-field-%s-449b" % day.replace("-", "")


def ensure_field_branch(repo, day):
    name = field_branch_name(day)
    rc, cur, _ = git_out(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    if rc == 0 and cur == name:
        return name, True
    rc, _, err = git_out(repo, ["checkout", name])
    if rc == 0:
        return name, True
    rc, _, err = git_out(repo, ["checkout", "-b", name])
    if rc != 0:
        sys.stderr.write("git checkout -b %s failed: %s\n" % (name, err))
        return name, False
    return name, True


def origin_ok(repo):
    rc, out, _ = git_out(repo, ["remote", "get-url", "origin"])
    if rc != 0 or not out:
        return False
    return "github.com" in out or out.startswith("git@") or "origin" in out


def gh_create_pr(repo, branch, day, body):
    title = "OpenClaw 田间报告 %s" % day
    try:
        p = subprocess.run(
            [
                "gh", "pr", "create", "--draft",
                "--title", title,
                "--body", body,
                "--head", branch,
            ],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=40,
            universal_newlines=True,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    if p.returncode != 0:
        return False, (p.stderr or p.stdout or "gh failed").strip()
    return True, (p.stdout or "").strip()


def push_existing(allow_dirty=True):
    json_path, txt_path, _folder, day, repo = report_paths()
    if not os.path.isfile(json_path):
        sys.stderr.write("no report file %s\n" % json_path)
        return 1
    with open(json_path, encoding="utf-8") as f:
        report = json.load(f)
    sanitize_or_die(report, json_path)
    submit_report(report, allow_dirty=allow_dirty, do_push=True)
    return 0


def submit_report(report, allow_dirty=False, do_push=True):
    """Write JSON, optionally commit+push only that file. Never force-push."""
    json_path, txt_path, local = write_report(report)
    repo = repo_root()
    day = shanghai_date()
    keep = [json_path, txt_path]
    dirty = porcelain_unrelated(repo, keep)
    result = {
        "json": json_path,
        "txt": txt_path,
        "local": local,
        "pushed": False,
        "branch": "",
        "pr": "",
        "skipped": "",
    }
    if not do_push:
        return result
    if not origin_ok(repo):
        result["skipped"] = "no origin remote"
        print("no origin remote, wrote file, skipped push")
        return result
    if dirty and not allow_dirty:
        result["skipped"] = "working tree dirty, wrote file, skipped push"
        print("working tree dirty, wrote file, skipped push")
        for p in dirty[:8]:
            print("  dirty:", p)
        return result
    name, ok = ensure_field_branch(repo, day)
    result["branch"] = name
    if not ok:
        result["skipped"] = "branch checkout failed, wrote file, skipped push"
        print(result["skipped"])
        return result
    paths = ["reports/openclaw/%s.json" % day]
    if txt_path and os.path.isfile(txt_path):
        paths.append("reports/openclaw/%s.txt" % day)
    for rel in paths:
        rc, _, err = git_out(repo, ["add", "--", rel])
        if rc != 0:
            result["skipped"] = "git add failed: %s" % err
            print(result["skipped"])
            return result
    # refuse if git tries to include audio
    rc, staged, _ = git_out(repo, ["diff", "--cached", "--name-only"])
    for line in (staged or "").splitlines():
        if AUDIO_RE.search(line) or line.endswith(".wav") or line.endswith(".mp3"):
            git_out(repo, ["reset", "HEAD", "--", line])
            result["skipped"] = "refused audio file"
            print(result["skipped"])
            return result
        if "ledger" in line or "transcript" in line:
            git_out(repo, ["reset", "HEAD", "--", line])
            result["skipped"] = "refused ledger/transcript"
            print(result["skipped"])
            return result
    msg = "chore: openclaw field report %s" % day
    rc, _, err = git_out(repo, ["commit", "-m", msg])
    if rc != 0:
        if "nothing to commit" in (err or "") or "nothing to commit" in _:
            print("nothing to commit (report already on branch)")
        else:
            result["skipped"] = "git commit failed: %s" % err
            print(result["skipped"])
            return result
    rc, out, err = git_out(repo, ["push", "-u", "origin", name], timeout=60)
    if rc != 0:
        result["skipped"] = "git push failed (no force): %s" % (err or out)
        print(result["skipped"])
        print("branch", name)
        return result
    result["pushed"] = True
    print("pushed", name)
    body = ""
    if txt_path and os.path.isfile(txt_path):
        with open(txt_path, encoding="utf-8") as f:
            body = f.read()
    ok, pr = gh_create_pr(repo, name, day, body or msg)
    if ok:
        result["pr"] = pr
        print(pr)
    else:
        print("gh pr create skipped:", pr)
        print("branch", name)
        print("cloud: git fetch origin %s" % name)
    return result


def load_steps_file(path):
    if not path or not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("steps"), list):
        return data["steps"]
    return []


def parse_turn_log(text):
    """Map cat-turn / today logs to enum labels. Never keep speech."""
    scene = "skip"
    window_opened = False
    reply_spoke = False
    for line in (text or "").splitlines():
        if re.search(r"开麦 [0-9]+s", line):
            window_opened = True
        if "[turn]" in line:
            low = line.lower()
            for token in ("joined", "oppose", "silent", "defer", "wont", "unclear", "skip"):
                if token in low:
                    scene = token
            if "回一句" in line and "joined" in low:
                reply_spoke = True
        if "跳过听窗" in line or "无麦环境" in line or "preview 不开麦" in line:
            window_opened = False
            if scene not in SCENES or scene == "skip":
                scene = "skip"
    if window_opened and scene == "skip":
        scene = "silent"
    return normalize_scene(scene), window_opened, reply_spoke


def steps_from_today_log(text, who="hanghang", hour=14, spoke=False):
    """Split today/openclaw stdout by step labels; keep enums only."""
    persona = persona_for(who)
    ran = isoformat_sh()
    labels = (
        ("ask", "问糖糖"),
        ("english", "学英语"),
        ("move", "锻炼身体"),
        ("rest", "注意休息"),
    )
    chunks = {k: "" for k, _ in labels}
    cur = None
    for line in (text or "").splitlines():
        hit = None
        for sid, lab in labels:
            if re.search(r"^\s*\d+\.\s+" + re.escape(lab), line) or re.search(
                r"\[openclaw\] step " + re.escape(sid) + r"\b", line
            ):
                hit = sid
                break
        if hit:
            cur = hit
            chunks[cur] += "\n"
            continue
        if cur:
            chunks[cur] += line + "\n"
    rows = []
    for sid, _lab in labels:
        scene, opened, reply = parse_turn_log(chunks.get(sid) or "")
        rows.append(
            make_step(sid, hour, ran, spoke, opened, scene, persona, reply)
        )
    return rows


def _selftest():
    who = "hanghang"
    steps = fixture_steps(who)
    scenes = [s["scene"] for s in steps]
    assert "silent" in scenes and "joined" in scenes, scenes
    report = build_report(who=who, rest_day=True, hw=hwcheck(), steps=steps, failures=[])
    assert report["schema_version"] == 1
    assert report["who"] == "hanghang"
    assert report["rest_day"] is True
    keys = set(walk_keys(report))
    for bad in FORBIDDEN_KEYS:
        assert bad not in keys, bad
    dumped = json.dumps(report, ensure_ascii=False)
    assert "transcript" not in dumped
    assert "utterance" not in dumped
    planted = dict(report)
    planted["transcript"] = "我不要听糖糖说话了啦啦啦"
    assert sanitize_err(planted), "sanitizer must reject transcript"
    long_cjk = dict(report)
    long_cjk["hwcheck"] = dict(report["hwcheck"])
    long_cjk["hwcheck"]["notes"] = "小朋友" * 20
    assert sanitize_err(long_cjk), "sanitizer must reject long cjk"
    ok, _ = 0, sanitize_err(report)
    assert not _, _
    tmp = os.path.join(
        os.environ.get("TMPDIR") or "/tmp", "openclaw-sanitize-test.json"
    )
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(planted, f, ensure_ascii=False)
    print("cat-openclaw-report.py selftest ok")
    return 0


def main(argv):
    argv = list(argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "usage: hwcheck | fixture | build | sanitize FILE | write | submit "
            "| selftest | txt"
        )
        return 0
    cmd = argv[0]
    who = "hanghang"
    rest_day = True
    dry = False
    allow_dirty = False
    submit = False
    steps_file = ""
    rest_env = os.environ.get("TANGTANG_REST_DAY", "")
    if rest_env in ("0", "false", "no"):
        rest_day = False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("--who",) and i + 1 < len(argv):
            who = argv[i + 1]
            i += 2
            continue
        if a in ("hanghang", "qiaqia"):
            who = a
            i += 1
            continue
        if a == "--steps-file" and i + 1 < len(argv):
            steps_file = argv[i + 1]
            i += 2
            continue
        if a in ("--dry-run", "-n"):
            dry = True
            i += 1
            continue
        if a == "--allow-dirty":
            allow_dirty = True
            i += 1
            continue
        if a == "--submit":
            submit = True
            i += 1
            continue
        if a == "--no-rest-day":
            rest_day = False
            i += 1
            continue
        i += 1
    who = "qiaqia" if who in ("qiaqia", "洽洽") else "hanghang"

    if cmd in ("selftest", "--selftest"):
        return _selftest()
    if cmd in ("push-existing", "resubmit"):
        return push_existing(allow_dirty=True)
    if cmd == "hwcheck":
        json.dump(hwcheck(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    if cmd == "sanitize":
        path = argv[1] if len(argv) > 1 else ""
        if not path:
            sys.stderr.write("sanitize FILE\n")
            return 1
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        errs = sanitize_err(data)
        if errs:
            sys.stderr.write("sanitize fail: %s\n" % "; ".join(errs))
            return 2
        print("sanitize ok")
        return 0
    if cmd == "parse-log":
        text = sys.stdin.read()
        scene, opened, reply = parse_turn_log(text)
        json.dump(
            {"scene": scene, "window_opened": opened, "reply_spoke": reply},
            sys.stdout,
        )
        sys.stdout.write("\n")
        return 0
    if cmd == "ingest-log":
        log_path = ""
        out_path = ""
        j = 1
        while j < len(argv):
            if argv[j] == "--log" and j + 1 < len(argv):
                log_path = argv[j + 1]
                j += 2
                continue
            if argv[j] == "--out" and j + 1 < len(argv):
                out_path = argv[j + 1]
                j += 2
                continue
            j += 1
        if log_path:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        else:
            text = sys.stdin.read()
        hour = int(os.environ.get("TANGTANG_OPENCLAW_HOUR") or "14")
        spoke = (os.environ.get("TANGTANG_TTS") or "1") != "0" and host_name() == "Darwin"
        rows = steps_from_today_log(text, who=who, hour=hour, spoke=spoke)
        blob = json.dumps(rows, ensure_ascii=False)
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(blob)
                f.write("\n")
        else:
            sys.stdout.write(blob + "\n")
        return 0
    steps = load_steps_file(steps_file) if steps_file else None
    if cmd == "fixture":
        steps = fixture_steps(who)
        report = build_report(who=who, rest_day=rest_day, steps=steps)
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    if cmd in ("build", "write", "submit", "txt", "dry-run"):
        if cmd == "dry-run":
            dry = True
        if steps is None:
            steps = fixture_steps(who) if cmd == "fixture" else load_steps_file(
                os.environ.get("TANGTANG_OPENCLAW_STEPS") or ""
            )
        failures = []
        fail_file = os.environ.get("TANGTANG_OPENCLAW_FAILURES") or ""
        if fail_file and os.path.isfile(fail_file):
            try:
                failures = json.load(open(fail_file, encoding="utf-8")) or []
            except (OSError, json.JSONDecodeError):
                failures = []
        report = build_report(
            who=who, rest_day=rest_day, hw=hwcheck(), steps=steps or fixture_steps(who),
            failures=failures,
        )
        if dry or cmd == "dry-run":
            json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0
        if cmd == "txt":
            sys.stdout.write(render_txt(report))
            return 0
        if cmd == "build":
            json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0
        if cmd == "write" and not submit:
            jp, tp, loc = write_report(report)
            print(jp)
            if tp:
                print(tp)
            return 0
        if cmd == "submit" or submit:
            submit_report(report, allow_dirty=allow_dirty, do_push=True)
            return 0
    sys.stderr.write("unknown cmd %s\n" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
