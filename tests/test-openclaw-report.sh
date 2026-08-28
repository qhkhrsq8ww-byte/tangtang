#!/bin/bash
# OpenClaw 田间报告：夹具标签、dry-run、--now 不等 14:00、消毒器拒 transcript
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CAT="$ROOT/code/cat"
# shellcheck source=../code/cat/cat-lib.sh
. "$CAT/cat-lib.sh"

fail=0
ok() { echo "ok  $1"; }
bad() { echo "fail  $1"; fail=1; }

export TANGTANG_TTS=0
export TANGTANG_TURN_STT=0
export TANGTANG_TURN_LLM=0
export TANGTANG_TODAY_GAP=0
export TANGTANG_FAKE_TODAY=2026-08-28
export TANGTANG_FAKE_TIME=10:00
export CAT_CHILD_HOME=1

bash -n "$CAT/cat-openclaw.sh" || bad "bash -n cat-openclaw.sh"
bash -n "$CAT/cat.sh" || bad "bash -n cat.sh"
bash -n "$CAT/cat-openclaw-report.py" 2>/dev/null || true

# 1) 夹具 silent+joined，无 transcript 键
fix="$("$CAT/cat-openclaw-report.py" fixture hanghang 2>/dev/null)" || { bad "fixture exit"; fix="{}"; }
echo "$fix" | /usr/bin/python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d["schema_version"]==1
assert d["who"]=="hanghang"
assert d["rest_day"] is True
scenes=sorted(s["scene"] for s in d["steps"])
assert "joined" in scenes and "silent" in scenes, scenes
assert len(d["steps"])==4
keys=[]
def walk(o):
    if isinstance(o, dict):
        keys.extend(o.keys())
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(d)
forb=("transcript","text","stt","utterance","quote")
hit=[k for k in keys if k.lower() in forb]
assert not hit, hit
blob=json.dumps(d)
assert "transcript" not in blob
print("counts", d["counts"])
' || bad "fixture labels/keys"
ok "fixture silent+joined no transcript"

# 2) sanitizer 拒绝植入的 transcript
planted="$(mktemp "${TMPDIR:-/tmp}/oc-planted.XXXXXX.json")"
good="$(mktemp "${TMPDIR:-/tmp}/oc-good.XXXXXX.json")"
printf '%s\n' "$fix" > "$good"
/usr/bin/python3 - "$good" "$planted" <<'PY'
import json,sys
d=json.load(open(sys.argv[1], encoding="utf-8"))
d["transcript"]="小朋友今天不想学英语了你不要再叫我了好不好"
json.dump(d, open(sys.argv[2],"w"), ensure_ascii=False)
PY
if /usr/bin/python3 "$CAT/cat-openclaw-report.py" sanitize "$planted" >/dev/null 2>&1; then
  bad "sanitizer accepted transcript"
else
  ok "sanitizer rejects transcript"
fi
rm -f "$planted" "$good"

# python selftest
/usr/bin/python3 "$CAT/cat-openclaw-report.py" selftest || bad "py selftest"
ok "py selftest"

# 3) --dry-run 退出 0，stdout 是合法 JSON
dry="$(TANGTANG_TTS=0 TANGTANG_TODAY_GAP=0 TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=10:00 \
  "$CAT/cat.sh" openclaw --dry-run hanghang 2>/dev/null)" || { bad "dry-run exit"; dry=""; }
echo "$dry" | /usr/bin/python3 -c '
import json,sys
raw=sys.stdin.read()
start=raw.find("{")
assert start>=0, raw[:200]
d=json.loads(raw[start:])
assert d["schema_version"]==1
assert "transcript" not in json.dumps(d)
assert len(d["steps"])==4
' || bad "dry-run json"
ok "dry-run exit 0"

# 4) Linux --now 不等 14:00（20 秒内结束）
start=$(date +%s)
if command -v timeout >/dev/null 2>&1; then
  timeout 20 env TANGTANG_TTS=0 TANGTANG_TODAY_GAP=0 TANGTANG_FAKE_TODAY=2026-08-28 \
    TANGTANG_FAKE_TIME=10:00 "$CAT/cat.sh" openclaw --now --dry-run hanghang >/tmp/oc-now.out 2>/tmp/oc-now.err \
    || bad "now dry-run timeout/exit"
else
  TANGTANG_TTS=0 TANGTANG_TODAY_GAP=0 TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=10:00 \
    "$CAT/cat.sh" openclaw --now --dry-run hanghang >/tmp/oc-now.out 2>/tmp/oc-now.err \
    || bad "now dry-run exit"
fi
end=$(date +%s)
elapsed=$((end - start))
if [ "$elapsed" -ge 19 ]; then
  bad "--now hung (${elapsed}s) waiting for 14:00"
else
  ok "--now finished in ${elapsed}s (no 14:00 wait)"
fi
grep -q "等到" /tmp/oc-now.err && grep -q "14:00" /tmp/oc-now.err && bad "waited for 14:00"
/usr/bin/python3 -c '
import json
raw=open("/tmp/oc-now.out",encoding="utf-8").read()
start=raw.find("{")
assert start>=0
d=json.loads(raw[start:])
assert d["schema_version"]==1
assert d["host"] in ("Linux","Darwin","unknown")
' || bad "now json"
ok "--now json"

# preview 不开麦、不 push
prev="$(TANGTANG_FAKE_TODAY=2026-08-28 TANGTANG_FAKE_TIME=10:00 \
  "$CAT/cat.sh" openclaw --preview hanghang 2>&1)" || bad "preview exit"
echo "$prev" | grep -q "开麦 " && bad "preview opened mic"
echo "$prev" | grep -q "preview 不写报告" || bad "preview should skip write"
ok "preview no mic no write"

feat="$("$CAT/cat.sh" features 2>&1)"
echo "$feat" | grep -q "./cat.sh openclaw --now --submit" || bad "features missing openclaw submit"
ok "features lists openclaw"

if [ "$fail" = "0" ]; then
  echo "test-openclaw-report ok"
  exit 0
fi
echo "test-openclaw-report failed"
exit 1
