<p align="center">
  <img src="assets/logo.png" alt="葬AI" width="400">
</p>

<p align="center">用葬AI分析框架审视产品真伪，Claude Code 和 Codex 双平台可用。</p>

## 安装

```bash
git clone https://github.com/FrichXi/funeralai.git
cd funeralai
./install.sh
```

安装后直接用：

```
/funeralai <材料>
```

零依赖：不需要 Python、pip、API key，复用你已有的 AI 编码环境。

> 脚本会自动检测你的环境，安装 Claude Code 和/或 Codex 的 skill。也可以单独装：`./scripts/install_claude.sh` 或 `./scripts/install_codex.sh`。

## 核心理念

**吹牛逼可以，但你要有一个过得去的产品。**

四层分析框架：

| 层级 | 问题 |
|------|------|
| 第零层（实查） | 代码/产品实际跑通了吗？宣称 vs 实际能做到的 |
| 第一层 | 有人在用吗？核心功能稳定吗？是真需求还是补贴驱动？ |
| 第二层 | 长板有多长？竞争壁垒在哪？用户会留下来吗？ |
| 第三层 | 吹的和做的差多远？叙事膨胀程度、营销密度、创始人信号 vs 产品实质 |

三档结论：**整挺好** / **吹牛逼呢** / **整不明白**

判断完全基于提交的材料内容，不基于对公司的已有认知。

## 使用方式

### Claude Code

```
/funeralai https://github.com/xxx/yyy        # GitHub 仓库分析
/funeralai https://example.com                # 网页/产品分析
/funeralai path/to/article.md                 # 本地文件分析
/funeralai                                    # 空参数，会追问你要分析什么
```

### Codex

```
/funeralai https://github.com/xxx/yyy        # 同样支持
```

## 支持的分析目标

- **GitHub 仓库 URL** — 代码实查 + 结构化分析
- **网页 URL** — 产品体验实查 + 分析
- **本地文件**（`.md` / `.txt` / `.pdf`）— 材料分析
- **粘贴文本** — 直接分析

## 项目结构

```
.agents/skills/funeral/    共享核心（唯一事实源）
.claude/skills/funeral/    Claude Code 镜像（由 sync 脚本维护）
.codex/prompts/            Codex 包装层
scripts/                   安装与同步脚本
funeralai/                 Python 参考实现（原始 CLI 版本）
```

## 常见问题

**`/funeralai` 命令没出现？**
检查安装脚本是否正确执行，确认 skill 文件已复制到对应平台的 skills 目录。

**GitHub 仓库分析需要什么？**
需要安装 [gh CLI](https://cli.github.com/)，用于拉取仓库信息和代码。

**网页抓取失败？**
部分网站有反爬限制，分析器会要求你手动粘贴页面内容。

## Python 参考实现

`funeralai/` 目录是原始 CLI 版本（`pip install funeralai`），Skill 版本不依赖 Python，复用用户已有的 AI 编码环境。Python 版保留用于对照分析质量和批量分析场景。

> 注意：Python 版的 PDF 读取依赖 pymupdf（AGPL-3.0），如果你通过 pip 安装 Python 版本请留意 license 兼容性。Skill 版本不受影响。

## License

[MIT](LICENSE)
