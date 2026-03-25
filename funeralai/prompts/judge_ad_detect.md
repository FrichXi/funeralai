# 广告检测

判断这份材料是不是广告/软文，以及是否涉及可评估的具体产品。

只做分类，不做产品分析。

## 广告/软文特征

以下特征 = 广告/软文：
- 通篇夸，一个缺点都没提
- 满嘴"颠覆""引领""全球首个"，但没有一句话说产品具体怎么用
- 通稿结构：讲趋势 → 引出产品 → 展望未来
- "用户反馈"过于完美
- 作者明显没亲手用过，在转述官方话术
- 网站本身就是营销页：纯 landing page，没有产品入口、文档、定价页，全是热词和 CTA 按钮

## 不可评估判断

没有在评价具体产品（行业观察、方法论、趋势分析、整活、专访但没评价产品好坏）→ non_evaluable。

注意：产品网站 + 体验实查报告 = evaluable。网站内容本身就是产品描述。

## 输出格式

严格按以下 JSON 格式输出，不要输出任何 JSON 之外的内容：

```json
{
  "article_type": "evaluable / non_evaluable / advertorial",
  "advertorial_confidence": "high / medium / low / null",
  "advertorial_signals": ["信号1", "信号2"]
}
```

- evaluable: 材料涉及可评价的具体产品
- non_evaluable: 不涉及产品评价（advertorial_confidence 为 null，advertorial_signals 为空）
- advertorial: 广告/软文（仍然可评估，但标注推广信息可信度打折）
