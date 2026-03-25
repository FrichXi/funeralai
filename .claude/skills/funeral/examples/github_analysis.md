# 葬AI分析报告：DevForge

## 判断

31k stars 买不来一行测试代码 🤡 声称"all-in-one developer platform"，代码仓库拆开一看：25% 是代码，剩下全是 markdown 文档和 prompt 模板。这不是平台，这是一个精心包装的 prompt 文档集，README 写得比产品本身还用心。

## 投资建议

**😭 吹牛逼呢**

## 产品实况

DevForge 自称是面向全栈开发者的一站式平台，支持"从原型到部署的完整工作流"。实际上它是一组 prompt 模板用 CLI 串起来的工具，核心逻辑不超过 800 行 Python，剩下的全是文档和配置文件。把 prompt 打包叫产品没问题，但把 prompt 打包叫 platform 就是在考验投资人的阅读能力 😤

**代码实查**：代码占比 25%，零测试文件，89% 提交来自同一人，README 声称的功能覆盖度与代码实际能力严重不符。

## 关键证据

| # | 证据 | 原文/数据 | 类型 |
|---|------|----------|------|
| 1 | 代码占比极低，大部分内容是文档 | 实查：总文件 147 个，代码文件 (.py) 仅 23 个，占总行数 25%；.md 文件 89 个，占 61% | code_inspection |
| 2 | 零测试文件，无 CI 配置 | 实查：未检测到任何 test_*.py 或 *_test.py 文件，无 .github/workflows 目录 | code_inspection |
| 3 | 单人项目伪装团队交付 | 实查：贡献者 7 人，其中 devforge-ceo 贡献 89% 提交，其余 6 人合计 11%（多为文档修正） | code_inspection |
| 4 | 代码采样显示核心是 prompt 转发 | 实查采样 cli/commands/generate.py：核心函数 28 行，其中 22 行是读取 prompt 模板 + 调用 OpenAI API | code_inspection |
| 5 | Stars 数量与产品实质不匹配 | GitHub: 31.2k stars, 但 issues 仅 43 个（其中 38 个是 feature request），PR 合并数 12 | risk |
| 6 | README 声称与仓库现实矛盾 | README: "支持 12 种语言的代码生成、自动化测试、一键部署"；实查：仅有 Python prompt 模板，无测试模块，无部署脚本 | risk |

## 广告信号

无（材料为 GitHub 仓库实查，非推广内容）

## 信息完整度

**high**

代码仓库实查覆盖完整，信息充分支撑判断。缺少用户侧使用反馈，但第零层证据已足够明确。
