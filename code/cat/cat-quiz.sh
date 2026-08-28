#!/bin/bash
# 糖糖 · 英语单词小测验（小学三年级难度）
# 用法: ./cat-quiz.sh [个数=5]
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"

N="${1:-5}"
NAME="${TANGTANG_CHILD_NAME:-小朋友}"

WORDS=(
  "apple|苹果"
  "cat|猫"
  "dog|狗"
  "red|红色"
  "blue|蓝色"
  "book|书"
  "sun|太阳"
  "star|星星"
  "tree|树"
  "happy|开心"
  "water|水"
  "milk|牛奶"
  "school|学校"
  "friend|朋友"
  "green|绿色"
  "fish|鱼"
  "bird|鸟"
  "hand|手"
  "eye|眼睛"
  "cake|蛋糕"
)

say_en() { say -v Ting-Ting "$1"; }
speak_cn() { "$CAT_DIR/cat-say.sh" "$1" cute >/dev/null 2>&1; }

pick=()
while [ "${#pick[@]}" -lt "$N" ]; do
  i=$((RANDOM % ${#WORDS[@]}))
  w="${WORDS[$i]}"
  echo "$w" | grep -qx "$(printf '%s\n' "${pick[@]}")" && continue
  pick+=("$w")
done

say_en "Hello, let's play a word game."
speak_cn "${NAME}，糖糖来考你几个英语单词啦，准备好汪汪～"
sleep 1

n=1
for w in "${pick[@]}"; do
  en="${w%%|*}"; cn="${w##*|}"
  echo "[$n] 念英文: $en"
  say_en "$en"
  speak_cn "第${n}个，$en，${NAME}知道是什么意思吗？想想看汪汪～"
  echo "    -> 留4秒思考"
  sleep 4
  speak_cn "答案是：$cn。答对了吗？真棒汪汪～"
  echo "    -> 公布: $cn"
  sleep 1
  n=$((n+1))
done

say_en "Great job!"
speak_cn "今天考完啦，${NAME}好厉害，糖糖陪你玩真开心汪汪～"
exit 0
