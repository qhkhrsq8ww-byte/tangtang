#!/bin/bash
# 糖糖 · 考航航英语单词（小学三年级难度）
# 用法: ./cat-quiz.sh [个数=5]
# 流程: 念英文(系统嗓,发音准) → 让航航猜 → 公布中文(甜嗓)
CAT_DIR="$(dirname "$0")"
N="${1:-5}"

# 三年级简单词库（英文|中文）
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
# 随机抽 N 个不重复
pick=()
while [ "${#pick[@]}" -lt "$N" ]; do
  i=$((RANDOM % ${#WORDS[@]}))
  w="${WORDS[$i]}"
  echo "$w" | grep -qx "$(printf '%s\n' "${pick[@]}")" && continue
  pick+=("$w")
done

say_en "Hello Hanghang, let's play a word game."
speak_cn "航航，糖糖来考你几个英语单词啦，准备好喵～"
sleep 1

n=1
for w in "${pick[@]}"; do
  en="${w%%|*}"; cn="${w##*|}"
  echo "[$n] 念英文: $en"
  say_en "$en"
  speak_cn "第$n个，$en，航航知道是什么意思吗？想想看喵～"
  echo "    -> 留4秒给航航想"
  sleep 4   # 给航航思考/口头回答的时间
  speak_cn "答案是：$cn。航航答对了吗？真棒喵～"
  echo "    -> 公布: $cn"
  sleep 1
  n=$((n+1))
done

say_en "Great job Hanghang!"
speak_cn "今天考完啦，航航好厉害，糖糖陪你玩真开心喵～"
exit 0
