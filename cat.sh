#!/bin/bash
# 仓库根入口 → code/cat/cat.sh
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/code/cat/cat.sh" "$@"
