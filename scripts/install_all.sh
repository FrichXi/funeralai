#!/usr/bin/env bash
set -euo pipefail

# 一键安装 Claude + Codex

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== 安装 Claude Code Skill ==="
echo ""
"$SCRIPT_DIR/install_claude.sh"

echo ""
echo "=== 安装 Codex Skill ==="
echo ""
"$SCRIPT_DIR/install_codex.sh"

echo ""
echo "=== 全部安装完成 ==="
