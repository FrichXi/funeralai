#!/usr/bin/env bash
set -euo pipefail

# 从共享核心 .agents/skills/funeral/ 单向同步到 .claude/skills/funeral/
# 排除 Codex 专用的 agents/ 目录（含 openai.yaml）

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SRC="$PROJECT_ROOT/.agents/skills/funeral/"
DST="$PROJECT_ROOT/.claude/skills/funeral/"

if [ ! -d "$SRC" ]; then
    echo "错误：源目录不存在 $SRC"
    exit 1
fi

# 确保目标目录存在
mkdir -p "$DST"

echo "同步: $SRC → $DST"
echo "排除: agents/ 目录"
echo ""

rsync -av --delete \
    --exclude='agents/' \
    "$SRC" "$DST"

echo ""
echo "同步完成。"
