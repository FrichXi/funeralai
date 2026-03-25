#!/usr/bin/env bash
set -euo pipefail

# 安装 funeral skill 到 Codex 目录:
#   共享核心 → ~/.agents/skills/funeral/
#   Codex slash wrapper → ~/.codex/prompts/funeralai.md

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SRC_SKILL="$PROJECT_ROOT/.agents/skills/funeral"
SRC_WRAPPER="$PROJECT_ROOT/.codex/prompts/funeralai.md"

DST_SKILL="$HOME/.agents/skills/funeral"
DST_WRAPPER="$HOME/.codex/prompts/funeralai.md"

# 检查源文件
if [ ! -d "$SRC_SKILL" ]; then
    echo "错误：共享核心目录不存在 $SRC_SKILL"
    exit 1
fi
if [ ! -f "$SRC_WRAPPER" ]; then
    echo "错误：Codex wrapper 不存在 $SRC_WRAPPER"
    exit 1
fi

# 安装共享核心
if [ -d "$DST_SKILL" ]; then
    echo "目标目录已存在: $DST_SKILL"
    read -rp "是否覆盖？(y/N) " confirm
    if [[ "$confirm" != [yY] ]]; then
        echo "跳过共享核心安装。"
    else
        rm -rf "$DST_SKILL"
        mkdir -p "$(dirname "$DST_SKILL")"
        cp -R "$SRC_SKILL" "$DST_SKILL"
        echo "共享核心已安装到 $DST_SKILL"
    fi
else
    mkdir -p "$(dirname "$DST_SKILL")"
    cp -R "$SRC_SKILL" "$DST_SKILL"
    echo "共享核心已安装到 $DST_SKILL"
fi

# 安装 Codex wrapper
if [ -f "$DST_WRAPPER" ]; then
    echo ""
    echo "Wrapper 已存在: $DST_WRAPPER"
    read -rp "是否覆盖？(y/N) " confirm
    if [[ "$confirm" != [yY] ]]; then
        echo "跳过 wrapper 安装。"
    else
        mkdir -p "$(dirname "$DST_WRAPPER")"
        cp "$SRC_WRAPPER" "$DST_WRAPPER"
        echo "Wrapper 已安装到 $DST_WRAPPER"
    fi
else
    mkdir -p "$(dirname "$DST_WRAPPER")"
    cp "$SRC_WRAPPER" "$DST_WRAPPER"
    echo "Wrapper 已安装到 $DST_WRAPPER"
fi

echo ""
echo "Codex 安装完成！"
echo "  共享核心: $DST_SKILL"
echo "  Wrapper:  $DST_WRAPPER"
echo ""
echo "使用方式:"
echo "  在 Codex 中通过 slash 命令调用 funeralai 分析"
