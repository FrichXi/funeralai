# Funeral Skill

## 核心目的

将葬AI的产品分析框架封装为可分发的 Claude Code / Codex 双平台能力，让任何人都能通过稳定的斜杠入口调用结构化的产品真伪分析。

**一句话**：共享核心负责分析，平台包装负责 slash 入口。Claude 目标是 `/funeralai <材料>`，Codex 目标是安装后也能通过斜杠入口调用同一个核心能力。

## 核心理念

**吹牛逼可以，但你要有一个过得去的产品。**

分析框架四层：
- **第零层**（实查）：代码/产品实际跑通了吗？宣称 vs 实际能做到的
- **第一层**：有人在用吗？核心功能稳定吗？是真需求还是补贴驱动？
- **第二层**：长板有多长？竞争壁垒在哪？用户会留下来吗？
- **第三层**：吹的和做的差多远？叙事膨胀程度、营销密度、创始人信号 vs 产品实质

三档结论：整挺好 / 吹牛逼呢 / 整不明白

铁律：**判断完全基于提交的材料内容，不基于对公司的已有认知。**

## 项目来源

分析层从原始 funeralai CLI 项目完整迁移而来。CLI 版本是 Python 包（`pip install funeralai`），skill 版本主打纯 prompt + 轻量安装脚本，无需把 Python 作为用户侧运行时依赖。

## 分发目标

- 开源到 GitHub
- 用户 clone 后用安装脚本完成安装
- 支持 Claude Code 的直接 slash 命令入口
- 支持 Codex 的 slash 包装入口 + 共享 skill
- 零依赖安装：不需要 Python、pip、API key（复用用户已有的 AI 编码环境）
- 共享核心不维护两份分析 prompt

## 分析层文件清单（已迁移）

- `funeralai/analyzer.py` — 分析引擎（extract → ask → parallel judge）
- `funeralai/reader.py` — 文件读取（.md/.txt/.pdf）
- `funeralai/inspector.py` — GitHub 仓库实查
- `funeralai/scraper.py` — 网页实查
- `funeralai/questioner.py` — 一手体验采集
- `funeralai/output.py` — 终端彩色报告 + JSON
- `funeralai/config.py` — API key / provider 持久化
- `funeralai/i18n.py` — 中英文 UI 适配
- `funeralai/prompts/*.md` — 12 个 prompt 模板

## 约定

- 分析框架不再调优。核心价值在于结构化分析视角，不在精确预测。
- Skill 版本优先做「prompt-native」方案：将分析方法论直接嵌入共享 skill，让 Claude/Codex 自身执行分析，不依赖外部 LLM 调用。
- 共享核心只保留跨平台稳定写法；平台差异由 Claude/Codex 各自的包装层与安装脚本处理。
- Claude Plugin 可以作为附加分发形式，但不是主路径，因为它不保证直接 `/funeralai`。
- 做大改动前先更新规划文件，确认方向再动手。
