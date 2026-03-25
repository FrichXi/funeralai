"""Interactive Q&A: collect firsthand user experience as core evidence for analysis.

Core questions (always asked) map to the three-layer judge framework:
  Layer 1 — 有人在用吗？ / Is anyone actually using it?
  Layer 2 — 长板有多长？ / How strong is the strength?
  Layer 3 — 吹的和做的差多远？ / Marketing vs reality gap?

Supplementary questions (LLM-generated from gaps/red_flags) fill specific holes
that core questions don't cover.

Language is auto-detected from the input text: Chinese questions for Chinese
material, English questions for everything else.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ASK_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "ask.md"

# ── Language detection ─────────────────────────────────────────────────────

def _detect_lang(text: str) -> str:
    """Detect language from text. Returns 'zh' or 'en'.

    Uses CJK character ratio: if >10% of non-whitespace chars are CJK → Chinese.
    """
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return "zh"
    cjk = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    return "zh" if cjk / len(chars) > 0.1 else "en"


# ── Core questions: always asked, aligned with the three-layer framework ────

_CORE_QUESTIONS_ZH = [
    # Layer 1: 有人在用吗？
    {
        "question": "你亲手用过这个产品吗？核心功能跑通了吗？在什么场景用的，会继续用吗？",
        "layer": 1,
        "tag": "usage",
    },
    # Layer 2: 长板有多长？
    {
        "question": "有没有让你眼前一亮的地方？或者觉得扯淡的地方？",
        "layer": 2,
        "tag": "highlight",
    },
    # Layer 3: 吹的和做的差多远？
    {
        "question": "它宣传的和你实际用到的，差距大吗？",
        "layer": 3,
        "tag": "reality_gap",
    },
]

_CORE_QUESTIONS_EN = [
    # Layer 1: Is anyone actually using it?
    {
        "question": "Have you used this product yourself? Does the core feature work? What's your use case, and will you keep using it?",
        "layer": 1,
        "tag": "usage",
    },
    # Layer 2: How strong is the strength?
    {
        "question": "Anything that impressed you? Or anything that felt like BS?",
        "layer": 2,
        "tag": "highlight",
    },
    # Layer 3: Marketing vs reality gap?
    {
        "question": "How big is the gap between what they advertise and what you actually got?",
        "layer": 3,
        "tag": "reality_gap",
    },
]

_CORE_QUESTIONS = {"zh": _CORE_QUESTIONS_ZH, "en": _CORE_QUESTIONS_EN}

# UI strings per language
_UI = {
    "zh": {
        "header": "──── 使用体验调查 (回车跳过, q 结束) ────",
        "target": "  分析对象: {}",
        "non_tty": "提示: 非交互终端，跳过问答环节",
        "judge_title": "## 提交者一手体验（由提交者本人口述，非材料原文）",
        "judge_intro": (
            "以下是提交者对产品的亲身使用反馈。"
            "这是判断「有没有人在用」的直接证据，权重高于材料中的间接转述。"
        ),
        "layer_prefix": {1: "【使用实况】", 2: "【长板/短板】", 3: "【宣传vs现实】"},
        "default_prefix": "【补充】",
        "supplement_fail": "提示: 生成补充问题失败 ({})",
    },
    "en": {
        "header": "──── User Experience Survey (Enter to skip, q to quit) ────",
        "target": "  Analyzing: {}",
        "non_tty": "Note: non-interactive terminal, skipping Q&A",
        "judge_title": "## Submitter's Firsthand Experience (oral testimony, not from the source material)",
        "judge_intro": (
            "The following is the submitter's direct feedback on using the product. "
            "This is direct evidence for whether anyone is actually using it, "
            "and carries more weight than secondhand accounts in the material."
        ),
        "layer_prefix": {1: "[Usage]", 2: "[Strengths/Weaknesses]", 3: "[Marketing vs Reality]"},
        "default_prefix": "[Supplementary]",
        "supplement_fail": "Note: failed to generate supplementary questions ({})",
    },
}


# ── Supplementary question generation ──────────────────────────────────────

def _generate_supplementary(
    gaps: list[str],
    red_flags: list[str],
    provider_name: str,
    api_key: str,
    lang: str = "zh",
    model: str | None = None,
    max_questions: int = 2,
) -> list[str]:
    """Turn extraction gaps + red flags into targeted follow-up questions.

    Returns empty list on failure — never blocks analysis.
    """
    if not gaps and not red_flags:
        return []

    try:
        from funeralai.analyzer import call_llm, load_prompt, parse_json

        prompt = load_prompt(_ASK_PROMPT_PATH)
        user_input = json.dumps(
            {"gaps": gaps, "red_flags": red_flags, "lang": lang},
            ensure_ascii=False,
        )
        raw = call_llm(
            provider_name, prompt, user_input, api_key, model, max_tokens=512
        )
        questions = parse_json(raw)
        if isinstance(questions, list):
            return [str(q) for q in questions[:max_questions]]
    except Exception as e:
        from funeralai.analyzer import _progress
        _progress(_UI[lang]["supplement_fail"].format(e))

    return []


# ── Public API ─────────────────────────────────────────────────────────────

def build_questions(
    text: str = "",
    gaps: list[str] | None = None,
    red_flags: list[str] | None = None,
    provider_name: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    max_supplementary: int = 2,
) -> tuple[list[dict], str]:
    """Build the full question list: core questions first, then supplementary.

    Returns (questions, lang) where questions is a list of
    {"question": str, "layer": int|None, "tag": str} and lang is "zh" or "en".
    """
    lang = _detect_lang(text)
    questions = [dict(q) for q in _CORE_QUESTIONS[lang]]

    if (gaps or red_flags) and provider_name and api_key:
        extras = _generate_supplementary(
            gaps=gaps or [],
            red_flags=red_flags or [],
            provider_name=provider_name,
            api_key=api_key,
            lang=lang,
            model=model,
            max_questions=max_supplementary,
        )
        for q in extras:
            questions.append({
                "question": q,
                "layer": None,
                "tag": "supplementary",
            })

    return questions, lang


def collect_answers(
    questions: list[dict],
    product_name: str | None = None,
    lang: str = "zh",
) -> list[dict]:
    """Ask questions interactively via stdin/stderr.

    - Empty enter = skip question
    - 'q' = stop asking
    - Non-TTY (pipe) = skip all, return empty list

    Returns list of {"question", "answer", "layer", "tag"} for answered
    questions only.
    """
    ui = _UI[lang]

    if not sys.stdin.isatty():
        from funeralai.analyzer import _progress
        _progress(ui["non_tty"])
        return []

    if not questions:
        return []

    print(file=sys.stderr)
    print(ui["header"], file=sys.stderr)
    if product_name:
        print(ui["target"].format(product_name), file=sys.stderr)
    print(file=sys.stderr, flush=True)

    answers: list[dict] = []
    for i, qinfo in enumerate(questions):
        q = qinfo["question"]
        print(
            f"  [{i + 1}/{len(questions)}] {q}",
            file=sys.stderr, flush=True,
        )
        try:
            reply = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            break

        if reply.lower() == "q":
            break
        if reply:
            answers.append({
                "question": q,
                "answer": reply,
                "layer": qinfo.get("layer"),
                "tag": qinfo.get("tag"),
            })

    print(file=sys.stderr, flush=True)
    return answers


def format_answers_for_judge(answers: list[dict], lang: str = "zh") -> str:
    """Format collected answers as structured evidence for the judge.

    Returns empty string if no answers.
    """
    if not answers:
        return ""

    ui = _UI[lang]
    lines = [ui["judge_title"], "", ui["judge_intro"], ""]
    layer_prefix = ui["layer_prefix"]
    default_prefix = ui["default_prefix"]

    for a in answers:
        prefix = layer_prefix.get(a.get("layer"), default_prefix)
        lines.append(f"- {prefix} 「{a['question']}」: \"{a['answer']}\"")

    return "\n".join(lines)
