# 补充问题生成 / Supplementary Question Generation

你会收到一份 JSON，包含信息缺口（gaps）、红旗（red_flags）和语言标识（lang）。

**根据 lang 字段决定输出语言：**
- `"zh"` → 用中文提问
- `"en"` → 用英文提问

注意：以下方向的问题**已经问过了**，不要重复：
- 是否亲手用过、核心功能能不能跑通、使用场景、频次、是否会继续用 / Whether they've used it, core functionality, use case, frequency, retention
- 亮点和槽点 / Highlights and pain points
- 宣传与实际的差距 / Marketing vs reality gap

你要做的是：针对具体的 gaps 和 red_flags，生成**更细节的补充追问**。

要求：
- 越具体越好，问到可验证的细节
- 一句话一个问题，语气直接，不客套
- 最多 2 个问题
- 输出纯 JSON 数组，不要其他内容

中文示例：
```json
["导出功能你试过吗？能导出什么格式？", "它说支持多人协作，你有和别人一起用过吗？"]
```

English example:
```json
["Have you tried the export feature? What formats does it support?", "They claim multi-user collaboration — have you actually used it with others?"]
```
