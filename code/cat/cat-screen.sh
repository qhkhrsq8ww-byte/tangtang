#!/bin/bash
# 兼容旧名：一键上投影（等同 ./cat.sh -s）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/cat.sh" -s "$@"
