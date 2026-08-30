#!/bin/bash
# ============================================================
# 糖糖 V3.1 · 隐私与运行时回归测试
# 执行：bash tests/test-v3.1-privacy.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."
PASS=0; FAIL=0; SKIP=0

check() { if [ "$1" -eq 0 ]; then echo "✅ PASS $2"; ((++PASS)); else echo "❌ FAIL $2"; ((++FAIL)); fi; }

echo "═════════════════════════════════════════════════════"
echo "糖糖 V3.1 · 隐私与运行时回归测试"
echo "═════════════════════════════════════════════════════"

# ---- 1. 语法检查 ----
echo "【语法】Python"
if /usr/bin/python3 -m py_compile code/cat/tangtang-privacy.py code/cat/tangtang-profile.py code/cat/cat-vp.py code/cat/cat-chat.py 2>/dev/null; then check 0 "Python 语法"; else check 1 "Python 语法"; fi

echo "【语法】Shell"
if find code/cat -name "*.sh" -exec bash -n {} \; 2>/dev/null; then check 0 "Shell 语法"; else check 1 "Shell 语法"; fi

echo "【语法】JSON"
if /usr/bin/python3 -m json.tool data/family.json > /dev/null 2>&1; then check 0 "JSON family.json"; else check 1 "JSON family.json"; fi

# ---- 2. 家庭人格与权限 ----
echo "【人格】五口之家（爷爷/奶奶/爸爸/洽洽/航航）"
for who in grandpa grandma dad qiaqia hanghang unknown; do
  out=$(/usr/bin/python3 code/cat/tangtang-profile.py --speaker "$who" 2>/dev/null || echo "{}")
  echo "$out" | grep -q '"member_id"' && check 0 "$who 解析" || check 1 "$who 解析"
done
for who in 爸爸 洽洽 航航 姐姐 弟弟; do
  out=$(/usr/bin/python3 code/cat/tangtang-profile.py --speaker "$who" 2>/dev/null || echo "{}")
  echo "$out" | grep -q '"member_id"' && check 0 "$who 别名解析" || check 1 "$who 别名解析"
done

echo "【权限】PRIVATE 成员原话不得落盘"
rm -rf /tmp/v31_priv_test && mkdir /tmp/v31_priv_test
TANGTANG_DATA_DIR=/tmp/v31_priv_test /usr/bin/python3 code/cat/cat-vp.py log child_9 "我今天被同学欺负了..." >/dev/null 2>&1
if grep -q "被同学欺负" /tmp/v31_priv_test/cat-habits.json 2>/dev/null; then check 1 "儿童原话泄漏"; else check 0 "儿童原话已拦截"; fi

echo "【权限】FAMILY 成员原话可进存储但不展示给 parent context"
TANGTANG_DATA_DIR=/tmp/v31_priv_test /usr/bin/python3 code/cat/cat-vp.py log dad "晚上加班到九点" >/dev/null 2>&1
grep -q "晚上加班到九点" /tmp/v31_priv_test/cat-habits.json 2>/dev/null && check 0 "成人原话保留" || check 1 "成人原话丢失"

echo "【权限】storage 级别验证"
for who in child_9 dad unknown; do
  expected="PRIVATE FAMILY PUBLIC"
  out=$(/usr/bin/python3 code/cat/tangtang-privacy.py --speaker "$who" 2>/dev/null | grep -o '"storage"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"')
  case "$who" in
    child_9) exp="PRIVATE" ;;
    dad) exp="FAMILY" ;;
    unknown) exp="PUBLIC" ;;
  esac
  [ "$out" = "$exp" ] && check 0 "$who storage=$exp" || check 1 "$who storage=$out (expected $exp)"
done

# ---- 3. 声纹链路 ----
echo "【声纹】建档/识别幂等"
rm -f code/cat/cat-voiceprints.json
rm -rf /tmp/v31_vp && mkdir -p /tmp/v31_vp
/usr/bin/python3 -c "
import struct, math, os
n=16000*0.5
with open('/tmp/vp_test.pcm','wb') as f:
    for i in range(int(n)):
        v=0.3*math.sin(2*math.pi*220*i/16000)
        f.write(struct.pack('<h',int(v*32767)))
" 2>/dev/null
if TANGTANG_DATA_DIR=/tmp/v31_vp /usr/bin/python3 code/cat/cat-vp.py enroll 测试人 /tmp/vp_test.pcm >/dev/null 2>&1; then check 0 "声纹建档"; else check 1 "声纹建档"; fi
if TANGTANG_DATA_DIR=/tmp/v31_vp /usr/bin/python3 code/cat/cat-vp.py identify /tmp/vp_test.pcm 2>/dev/null | grep -q "测试人"; then check 0 "声纹识别"; else check 1 "声纹识别"; fi
rm -f /tmp/vp_test.pcm code/cat/cat-voiceprints.json /tmp/v31_vp/cat-voiceprints.json

# ---- 4. 夜间静默 ----
echo "【静默】边界时间"
for h in 22:30 23:00 06:59 07:00; do
  out=$(/usr/bin/python3 code/cat/tangtang-quiet-hours.py --test-time "$h" 2>/dev/null | tail -1)
  case "$h" in 22:30|23:00|06:59) exp="quiet" ;; 07:00) exp="speak" ;; esac
  [ "$out" = "$exp" ] && check 0 "quiet @ $h" || check 1 "quiet @ $h = $out (expected $exp)"
done

# ---- 5. TTS ----
echo "【TTS】edge 链路"
/usr/bin/python3 code/cat/cat-tts-edge.py "测试语音" >/dev/null 2>&1 && [ -f /tmp/cat_tts.mp3 ] && check 0 "TTS edge" || check 1 "TTS edge"
rm -f /tmp/cat_tts.mp3

# ---- 6. 投影 ----
echo "【投影】连通性"
if curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://192.168.31.104:61949/ 2>/dev/null | grep -q "000"; then
  echo "⚠️  SKIP 投影不可达"; ((SKIP++))
else
  check 0 "投影连通"
fi

# ---- 7. 原有功能回归 ----
echo "【回归】cat-brain status"
TANGTANG_DATA_DIR=/tmp/v31_reg /usr/bin/python3 code/cat/cat-brain.py status >/dev/null 2>&1 && check $? "cat-brain status" || check $? "cat-brain status"

echo "【回归】cat-lib.sh 加载"
cd code/cat && bash -c '. ./cat-lib.sh && [ -n "$CAT_DIR" ]' 2>/dev/null && check 0 "cat-lib.sh" || check 1 "cat-lib.sh"
cd ../..

# ---- 8. 路径迁移脚本 ----
echo "【路径】迁移脚本可执行"
bash -n config/migrate-paths.sh && check 0 "迁移脚本语法" || check $? "迁移脚本语法"

# ---- 9. 密钥安全 ----
echo "【安全】真实 key 不在 git 跟踪文件"
if git ls-files | xargs grep -lE "T0569dRHcZNsxSCDlKeetCUS|8SW03t3SCPe1bqmELTPGOfUr2uPNQyyF" 2>/dev/null; then check 1 "真实 key 泄漏"; else check 0 "无真实 key 入库"; fi

# ---- 10. launchd 模板 ----
echo "【launchd】模板合法"
if plutil -lint config/com.tangtang.daemon.plist.example >/dev/null 2>&1; then check 0 "launchd plist"; else check 1 "launchd plist"; fi

echo ""
echo "═════════════════════════════════════════════════════"
echo "RESULT PASS=$PASS FAIL=$FAIL SKIP=$SKIP"
echo "═════════════════════════════════════════════════════"
[ "$FAIL" -eq 0 ]
