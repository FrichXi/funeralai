#!/usr/bin/env bash
set -euo pipefail

# funeralai 一键安装
# 自动检测环境，安装 Claude Code 和/或 Codex 的 skill

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

installed=0

# Claude Code
if command -v claude &>/dev/null || [ -d "$HOME/.claude" ]; then
    echo "=== 检测到 Claude Code，安装 skill ==="
    echo ""
    "$SCRIPT_DIR/scripts/install_claude.sh"
    installed=1
    echo ""
fi

# Codex
if command -v codex &>/dev/null || [ -d "$HOME/.codex" ]; then
    echo "=== 检测到 Codex，安装 skill ==="
    echo ""
    "$SCRIPT_DIR/scripts/install_codex.sh"
    installed=1
    echo ""
fi

# 都没检测到，默认装 Claude Code（最常见）
if [ "$installed" -eq 0 ]; then
    echo "未检测到 Claude Code 或 Codex，默认安装 Claude Code skill。"
    echo ""
    "$SCRIPT_DIR/scripts/install_claude.sh"
    echo ""
fi

echo "安装完成。在 Claude Code 中输入 /funeralai <材料> 开始分析。"
