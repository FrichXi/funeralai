#!/usr/bin/env bash
set -euo pipefail

# 安装 funeral skill 到 Claude Code 全局 skill 目录 ~/.claude/skills/funeral/

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SRC="$PROJECT_ROOT/.claude/skills/funeral"
DST="$HOME/.claude/skills/funeral"

# 检查源目录
if [ ! -d "$SRC" ]; then
    echo "错误：源目录不存在 $SRC"
    echo "请先运行 scripts/sync_skill.sh 生成 Claude 镜像。"
    exit 1
fi

# 检查目标是否已存在
if [ -d "$DST" ]; then
    echo "目标目录已存在: $DST"
    read -rp "是否覆盖？(y/N) " confirm
    if [[ "$confirm" != [yY] ]]; then
        echo "已取消。"
        exit 0
    fi
    rm -rf "$DST"
fi

mkdir -p "$(dirname "$DST")"
cp -R "$SRC" "$DST"

echo ""
echo "安装成功！"
echo "  位置: $DST"
echo ""
echo "使用方式:"
echo "  在 Claude Code 中输入 /funeralai <材料>"
