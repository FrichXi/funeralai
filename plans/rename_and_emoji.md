# 改名 funeralai + 报告 emoji 风格

## 改动 1：skill 名字从 funeral 改为 funeralai

### 影响范围

**共享核心（事实源）**
- `.agents/skills/funeral/SKILL.md` — frontmatter `name: funeral` → `name: funeralai`

**Claude 镜像**
- `.claude/skills/funeral/SKILL.md` — 同步改 frontmatter

**Codex 包装层**
- `.codex/prompts/funeral.md` — 文件名改为 `funeralai.md`，内容中 `$funeral` → `$funeralai`

**Codex 元数据**
- `.agents/skills/funeral/agents/openai.yaml` — 如有 name 字段需同步

**安装脚本**
- `scripts/install_claude.sh` — 打印信息中 `/funeral` → `/funeralai`
- `scripts/install_codex.sh` — 打印信息中的命令名更新
- `scripts/install_all.sh` — 如有打印信息也更新

**同步脚本**
- `scripts/sync_skill.sh` — 无需改（路径不变，只是 frontmatter 里的 name 变了）

**README.md**
- 所有 `/funeral` 引用改为 `/funeralai`

**CLAUDE.md**
- 项目说明中的命令名引用

**已安装的全局 skill**
- `~/.claude/skills/funeral/SKILL.md` — frontmatter name 改为 funeralai
- 重新运行 install_claude.sh 覆盖安装

### 不改的

- 目录名保持 `funeral/`（项目名 funeral 不变，skill 注册名改为 funeralai）
- Python 参考实现 `funeralai/` 目录不动（本来就叫 funeralai）
- `plans/` 下的规划文件不追溯改

### 目录名是否也要改？

当前结构：`.agents/skills/funeral/`、`.claude/skills/funeral/`

有两个选择：
- **A：只改 frontmatter name，目录名不动** — 改动小，Claude Code 用 frontmatter name 注册命令，目录名不影响
- **B：目录也改成 funeralai** — 更一致，但改动范围大（脚本路径全要改）

建议选 A。Claude Code 的 slash 命令名取决于 SKILL.md 的 `name` 字段，不取决于目录名。Codex 同理。

---

## 改动 2：报告输出加入 emoji

### emoji 清单（从 CLI 项目 output.py 提取）

- 🤓 — 值得进一步看
- 😭 — 暂不建议投资
- 🤔 — 信息不足，不能判断
- 🚩 — 红旗/广告信号

### 改动位置

**SKILL.md 输出格式模板** — 在以下位置插入 emoji：

1. 投资建议行：`**🤓 值得进一步看**` / `**😭 暂不建议投资**` / `**🤔 信息不足，不能判断**`
2. 广告信号标题：`## 🚩 广告信号`
3. 报告标题可选加一个：`# 葬AI分析报告：[产品名]` 保持不变（标题不加 emoji，保持干净）

每份报告大约出现 3-4 个 emoji（投资建议 1 个 + 广告信号 0-1 个 + 证据表中红旗行可标 🚩），符合"4 个左右"的要求。

### 同步更新

- `.agents/skills/funeral/SKILL.md` — 改输出格式模板
- `.claude/skills/funeral/SKILL.md` — 同步
- `~/.claude/skills/funeral/SKILL.md` — 重新安装
- 三个 examples 文件 — 对应更新 emoji

---

## 执行顺序

1. 改 SKILL.md frontmatter name + 输出格式 emoji
2. 改 Codex wrapper 文件名和内容
3. 改安装脚本打印信息
4. 改 README.md
5. 改 CLAUDE.md
6. 运行 sync_skill.sh 同步到 Claude 镜像
7. 运行 install_claude.sh 重新安装到全局
8. 更新三个 examples 文件的 emoji
9. 验证 `/funeralai` 命令注册成功
