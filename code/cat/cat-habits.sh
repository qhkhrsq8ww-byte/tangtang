#!/bin/bash
# 糖糖 · 本地习惯成长（客厅 Mac 规则更新，不训练模型）
# 用法见 cat-habits.py --help
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=cat-lib.sh
. "$SCRIPT_DIR/cat-lib.sh"
exec /usr/bin/python3 "$CAT_DIR/cat-habits.py" "$@"
