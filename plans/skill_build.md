# Funeral Skill 双平台建设规划

## 目标

将葬AI产品分析框架封装为一个共享核心能力，并在 Claude Code 与 Codex 上都提供稳定、低摩擦的斜杠入口。

**目标体验**：
- Claude Code：安装后直接用 `/funeral <材料>`
- Codex：安装后直接用斜杠命令包装层调用共享 skill
- 两个平台共用同一套分析方法论、输出标准和参考材料，不做两份 prompt

**当前结论**：
- Claude Code 原生适合把 skill 暴露为 `/funeral`
- Codex 的 skill 本体更适合做共享能力层；如果要稳定提供斜杠调用，需要额外加一层 custom prompt 包装
- 因此最终交付不应是“一个 SKILL.md 生搬到两个平台”，而应是“一个核心 skill + 两个平台各自的薄包装”

---

## 核心架构决策：Prompt-Native

**继续选择 prompt-native 方案，不选 Python-backed 作为主交付。**

| 对比维度 | Prompt-Native（主方案） | Python-Backed |
|---------|----------------------|--------------|
| 安装门槛 | 零依赖或近零依赖 | 需要 Python 环境和依赖 |
| 平台兼容 | 容易做 Claude/Codex 双包装 | 环境差异更多 |
| API Key | 复用用户现有 AI 编码环境 | 往往要单独配置 |
| 维护成本 | 方法论主要靠 prompt 与参考文档维护 | 代码、依赖、provider 一起维护 |
| 目标体验 | 更适合做 slash command 工作流 | 更适合独立 CLI / 批处理 |

**核心思路**：
- 共享分析方法论、证据标准、追问逻辑、输出格式
- 共享核心 skill 只写跨平台稳定内容
- 平台差异通过 wrapper 和安装脚本解决，而不是把平台特性硬塞进共享 SKILL.md

**Python 分析层的角色**：
- 保留为参考实现
- 用于对照分析质量、批量分析、未来高级用法
- 不是双平台 skill 的运行时依赖

---

## 交付模型：共享核心 + 平台包装

### 1. 共享核心（唯一事实源）

共享核心负责：
- 葬AI四层分析框架
- 三档结论标准
- 广告检测标准
- 证据分类标准
- GitHub / Web / Local 三类目标的分析流程
- 追问策略
- Markdown 报告格式

共享核心必须遵守两条约束：
- 只使用跨平台稳妥的 frontmatter 和指令写法
- 不把 Claude-only 或 Codex-only 的调用机制写死在核心里

### 2. Claude Code 包装层

Claude 侧主交付采用**standalone skill**，目标是安装后直接得到：

```text
/funeral <材料>
```

Claude 包装层职责：
- 把共享核心放到 Claude 可发现的位置
- 保持命令名就是 `/funeral`
- 可选增加 Claude 专属增强，但不反向污染共享核心

### 3. Codex 包装层

Codex 侧分成两层：
- 核心 skill：提供真正的分析能力
- slash prompt wrapper：给用户提供稳定的斜杠调用入口

换句话说：
- skill 负责“会分析”
- prompt wrapper 负责“能用斜杠命令叫到它”

Codex 包装层职责：
- 将共享核心放到 `.agents/skills/funeral/`
- 提供一个 slash prompt，例如 `funeral.md`，由它去显式调用共享 skill
- 补上 `agents/openai.yaml`，让 Codex UI 和 skill 元数据完整

### 4. Claude Plugin 不是主交付

Claude Plugin 可以保留为可选分发形式，但**不是主路径**，原因很简单：
- plugin skill 会带命名空间
- 用户调用会变成 `/plugin-name:funeral`
- 这不满足“安装后直接 `/funeral`”这个目标

因此：
- 主路径：standalone skill 安装
- 次路径：plugin 分发，接受命名空间命令

---

## 项目结构

建议改为下面这套结构：

```text
funeral/
├── CLAUDE.md
├── README.md
├── LICENSE
│
├── .agents/
│   └── skills/
│       └── funeral/                    # 共享核心，作为 source of truth
│           ├── SKILL.md
│           ├── agents/
│           │   └── openai.yaml
│           ├── references/
│           │   └── framework.md
│           ├── prompts/
│           │   └── ask.md
│           └── examples/
│               ├── github_analysis.md
│               ├── web_analysis.md
│               └── article_analysis.md
│
├── .claude/
│   └── skills/
│       └── funeral/                    # 由脚本从共享核心同步
│           ├── SKILL.md
│           ├── references/
│           ├── prompts/
│           └── examples/
│
├── .codex/
│   └── prompts/
│       └── funeral.md                  # Codex 的 slash 包装层
│
├── scripts/
│   ├── sync_skill.sh                   # 同步共享核心到 Claude 包装层
│   ├── install_claude.sh              # 安装到 ~/.claude/skills/funeral
│   ├── install_codex.sh               # 安装到 ~/.agents/skills/funeral + ~/.codex/prompts/
│   └── install_all.sh                 # 一键全装
│
├── plugins/
│   └── claude-funeral/                # 可选，不是主路径
│       ├── .claude-plugin/
│       │   └── plugin.json
│       └── skills/
│           └── funeral/
│
├── funeralai/                         # Python 参考实现
│   ├── __init__.py
│   ├── analyzer.py
│   ├── reader.py
│   ├── inspector.py
│   ├── scraper.py
│   ├── questioner.py
│   ├── output.py
│   ├── config.py
│   ├── i18n.py
│   └── prompts/
│       └── *.md
│
└── plans/
    └── skill_build.md
```

这套结构的关键点：
- `.agents/skills/funeral/` 是共享核心和事实源
- `.claude/skills/funeral/` 是镜像，不自己发明另一套 prompt
- `.codex/prompts/funeral.md` 只做 slash 入口，不复制分析框架

---

## 共享核心 Skill 设计

### Frontmatter 原则

共享核心的 `SKILL.md` 只保留跨平台稳定字段：

```yaml
---
name: funeral
description: 用葬AI分析框架审视产品、项目、网页或文章的真实状况。适用于 GitHub 仓库、产品官网、项目介绍和本地材料分析，输出一份基于材料证据的结构化判断报告。
---
```

**不要**在共享核心里依赖这些平台特性：
- Claude 专属 frontmatter 字段
- Codex 专属策略字段
- 某个平台专有的命令占位符语义
- 写死的工具名

如果需要平台增强：
- Claude 增强放在 Claude 包装层
- Codex 增强放在 `agents/openai.yaml` 或 custom prompt wrapper

### 输入契约

共享核心不要假设调用一定来自某个平台的 `$ARGUMENTS` 机制，而应写成：
- 从当前用户消息中提取目标材料
- 目标可能是 GitHub URL、网页 URL、文件路径、粘贴文本、项目描述
- 如果材料为空，先要求用户提供目标

这样一来：
- Claude `/funeral xxx` 可直接工作
- Codex slash wrapper 把参数转发给共享 skill 时也能工作
- 用户手动显式调用 skill 时仍能工作

### 工具契约

共享核心不要写成：
- “必须用 WebFetch”
- “必须用 Bash”
- “必须用 Read”

应改成能力描述：
- 如果可用，使用网页读取能力抓取网页
- 如果可用，使用 shell / git / gh 等命令做 GitHub 实查
- 如果可用，读取本地文件内容
- 如果关键工具缺失，明确降级并告诉用户缺什么

### 分析流程

共享核心保留三步：

1. 提取
2. 追问
3. 判断

但表达方式要从“prompt 拼装”改成“代理工作流说明”：
- 先识别材料类型
- 再做最小必要的实查
- 记录事实、推断、缺口、红旗
- 向用户追问一手体验
- 最后按四层框架输出报告

### 输出格式

共享核心继续输出 Markdown 报告，不输出 JSON。结构保留：
- 判断
- 投资建议
- 产品实况
- 关键证据
- 广告信号
- 信息完整度

---

## 平台包装设计

### Claude Code：直接 `/funeral`

Claude 的主路径：
- 安装共享核心到 `~/.claude/skills/funeral/`
- 用户直接运行 `/funeral <材料>`

实现方式：
- 仓库内保留 `.claude/skills/funeral/` 镜像
- 通过 `scripts/sync_skill.sh` 从共享核心同步
- 安装脚本负责复制到用户目录

### Codex：slash wrapper + 共享 skill

Codex 的主路径：
- 安装共享核心到 `~/.agents/skills/funeral/`
- 安装自定义 prompt 到 `~/.codex/prompts/funeral.md`
- 用户通过 slash prompt 调起它

Codex wrapper 的职责非常薄，只做三件事：
- 接收 slash 参数
- 显式调用共享 `funeral` skill
- 把参数作为分析目标转发

Codex wrapper 的内容应该尽量短，例如：

```markdown
Use $funeral to analyze the target below.

Target:
$ARGUMENTS

If no target is provided, ask the user what to analyze.
```

这样设计的好处：
- slash 入口和分析逻辑解耦
- 共享 skill 更新时，不需要重写 Codex 包装层
- Codex 未来如果原生支持更直接的 skill slash 调用，只要删掉 wrapper 即可

### Codex 元数据：`agents/openai.yaml`

为 Codex 补上：
- `display_name`
- `short_description`
- `default_prompt`
- 必要时的 invocation policy

建议初期设置为保守：
- 先保证显式调用稳定
- 隐式触发是否开启，等测试后再定

---

## 安装体验设计

### 主目标

仓库发布后，用户应通过下面的方式完成安装：

```bash
./scripts/install_claude.sh
./scripts/install_codex.sh
./scripts/install_all.sh
```

### Claude 安装结果

安装完成后，用户得到：

```text
/funeral <材料>
```

### Codex 安装结果

安装完成后，用户得到：
- 共享 `funeral` skill
- 对应的 slash prompt 入口

README 必须明确写清：
- slash 命令名是什么
- 它背后调用的是共享 `funeral` skill
- 如果用户不想走 slash，也可以直接显式提及 skill

### 不再把手工复制作为主文档路径

手工复制可以保留，但不应该是主推荐方式。主推荐方式应该是安装脚本，因为：
- 少一步用户犯错
- 路径不会写反
- 可以同时处理 Claude / Codex 的不同目录

---

## 实施阶段

### Phase 1：共享核心落地

**目标**：先把分析框架整理成一个真正跨平台的共享核心 skill

1. 编写共享核心 `SKILL.md`
   - 从 12 个 prompt 模板中提炼核心方法论
   - 删除平台耦合写法
   - 改成“从用户消息提取目标”的输入契约
   - 改成能力级工具描述
   - 定义最终 Markdown 报告格式

2. 编写 `references/framework.md`
   - 合并 `judge_verdict.md`
   - 合并 `judge_ad_detect.md`
   - 合并 `judge_evidence.md`
   - 合并 `judge_summary.md`
   - 提炼为共享参考文档

3. 编写 `prompts/ask.md`
   - 保留 3 个核心问题
   - 保留 gaps / red_flags 的补充追问逻辑

4. 编写 `agents/openai.yaml`
   - 设置 Codex 显示名与简述
   - 补默认 prompt
   - 决定是否允许隐式触发

### Phase 2：平台包装

**目标**：让两个平台都出现稳定的 slash 入口

5. 建立 Claude 包装层
   - 生成 `.claude/skills/funeral/`
   - 确保命令入口是 `/funeral`

6. 建立 Codex 包装层
   - 编写 `.codex/prompts/funeral.md`
   - 确保它显式调用共享 `funeral` skill
   - 验证 slash 调用后参数能被正确转发

7. 编写同步脚本
   - `scripts/sync_skill.sh`
   - 保证 Claude 镜像与共享核心不漂移

### Phase 3：安装与文档

**目标**：让用户真的能装、装完真的能调

8. 编写安装脚本
   - `scripts/install_claude.sh`
   - `scripts/install_codex.sh`
   - `scripts/install_all.sh`

9. 编写 README
   - 一句话介绍
   - Claude 安装步骤
   - Codex 安装步骤
   - 两个平台各自的 slash 调用示例
   - 常见失败场景与排查
   - Python 参考实现说明

10. 添加 LICENSE

### Phase 4：验证与调优

**目标**：先验平台行为，再调分析质量

11. Claude 验证
   - `/funeral <GitHub URL>`
   - `/funeral <网页 URL>`
   - `/funeral <文件路径>`
   - `/funeral` 空参数追问

12. Codex 验证
   - slash wrapper 能正常出现
   - slash wrapper 能正确调用共享 skill
   - GitHub / Web / Local 三类目标都能走通
   - 关键工具缺失时能正确降级

13. 分析质量调优
   - 对比 Python 版本结果
   - 调 prompt 措辞
   - 校准广告检测和结论风格

14. 可选：Claude Plugin 打包
   - 仅作为附加分发方式
   - README 明确它会使用 namespaced 命令，不是 `/funeral`

---

## 关键设计决策

### 决策 1：共享核心不直接绑定 slash 调用机制

slash 调用是平台体验层，不是分析逻辑层。

所以：
- 核心 skill 负责分析
- Claude skill 负责 `/funeral`
- Codex prompt wrapper 负责 slash 入口

### 决策 2：不把 Claude Plugin 作为主路径

因为它天然会引入命名空间，不满足主目标。

### 决策 3：共享核心只用最小 frontmatter

共享核心只依赖：
- `name`
- `description`

其他平台能力放到 wrapper 或平台元数据里解决。

### 决策 4：Codex 要“skill + prompt”双件套

只装 skill 不足以给用户稳定的 slash 入口。

如果目标是“安装后就能用斜杠命令”，就必须把 Codex prompt wrapper 视作正式产物，而不是测试辅助文件。

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 共享核心又慢慢长回平台特化 prompt | 严格限制核心 frontmatter 与工具假设，只允许 wrapper 层做平台增强 |
| Claude 与 Codex 目录内容漂移 | 用 `scripts/sync_skill.sh` 单向同步 |
| Codex slash 包装层和共享 skill 参数契约不一致 | 统一改成“从用户消息提取目标”，wrapper 只负责转发 |
| `gh` CLI 不可用导致 GitHub 分析变脆 | skill 明确降级策略，并在 README 写清楚 |
| 网页抓取能力因平台不同而不稳定 | skill 写能力级降级逻辑，必要时要求用户贴内容 |
| 用户不知道两个平台的 slash 命令名字不同 | README 开头就并列写清 Claude 与 Codex 入口 |

---

## 不做的事

- 不做多模型投票
- 不做批量分析
- 不做 TUI
- 不把 Python 参考实现变成运行时依赖
- 不以 Claude Plugin 作为唯一安装方式
- 不追求“一份原样 SKILL.md 直接同时充当两个平台的完整 UX 层”
