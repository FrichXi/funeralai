"""Core analysis engine: load prompt, call LLM, parse result.

Pipeline: extract → ask → parallel judge (4 concurrent calls).
  1. Extract: pull structured facts from the material (no judgment)
  2. Ask: collect firsthand user experience (interactive mode)
  3. Judge: 4 parallel LLM calls (ad detect, summary, evidence, verdict), assembled into one result
"""

from __future__ import annotations

import functools
import json
import os
import random
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable


def _progress(msg: str) -> None:
    """Print a progress message to stderr unless FUNERALAI_QUIET is set."""
    if not os.environ.get("FUNERALAI_QUIET"):
        print(msg, file=sys.stderr, flush=True)


_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Extract prompts (one per pipeline)
_EXTRACT_PATHS = {
    1: _PROMPTS_DIR / "extract_local.md",
    2: _PROMPTS_DIR / "extract_github.md",
    3: _PROMPTS_DIR / "extract_web.md",
}

# Parallel judge prompts (shared across all pipelines, pipeline context injected via input)
_JUDGE_PROMPTS = {
    "ad_detect": _PROMPTS_DIR / "judge_ad_detect.md",
    "summary": _PROMPTS_DIR / "judge_summary.md",
    "evidence": _PROMPTS_DIR / "judge_evidence.md",
    "verdict": _PROMPTS_DIR / "judge_verdict.md",
}

# Max tokens per parallel judge call
_JUDGE_MAX_TOKENS = {
    "ad_detect": 512,
    "summary": 1024,
    "evidence": 4096,
    "verdict": 2048,
}

_PIPELINE_NAMES = {1: "local", 2: "github", 3: "web"}

_DEFAULT_RECOMMENDATION = "整不明白"

# Field subsets for trimmed judge inputs
_AD_DETECT_FIELDS = (
    "material_type", "author_attitude", "attitude_signals",
    "facts", "opinions", "key_quotes",
)
_SUMMARY_FIELDS = (
    "products", "facts", "gaps", "claim_vs_reality",
    "product_evidence", "code_evidence",
)

# Provider configurations.
# type="openai" means OpenAI-compatible API (works with openai SDK).
# type="anthropic" uses the native Anthropic SDK.
PROVIDERS = {
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-6",
        "type": "anthropic",
        "base_url": None,
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "type": "openai",
        "base_url": None,
    },
    "gemini": {
        "env_key": "GEMINI_API_KEY",
        "default_model": "gemini-3.1-pro-preview",
        "type": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
    "kimi": {
        "env_key": "MOONSHOT_API_KEY",
        "default_model": "kimi-k2.5",
        "type": "openai",
        "base_url": "https://api.moonshot.ai/v1",
    },
    "minimax": {
        "env_key": "MINIMAX_API_KEY",
        "default_model": "MiniMax-M2.7",
        "type": "openai",
        "base_url": "https://api.minimax.chat/v1",
    },
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "type": "openai",
        "base_url": "https://api.deepseek.com",
    },
    "zhipu": {
        "env_key": "ZHIPU_API_KEY",
        "default_model": "glm-4.7",
        "type": "openai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "qwen": {
        "env_key": "DASHSCOPE_API_KEY",
        "default_model": "qwen-plus",
        "type": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
}


@functools.lru_cache(maxsize=None)
def load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_json(text: str) -> dict | list | None:
    """Extract JSON from LLM response, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try finding JSON object or array
        for open_ch, close_ch in [("{", "}"), ("[", "]")]:
            start = text.find(open_ch)
            end = text.rfind(close_ch) + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    continue
        return None


def _pick_key(raw: str) -> str:
    """Handle comma-separated API keys by picking one at random."""
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return random.choice(keys) if keys else raw


def _call_anthropic(
    system_prompt: str,
    user_content: str,
    api_key: str,
    model: str | None = None,
    max_tokens: int = 2000,
) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "使用 Anthropic API 需要安装 anthropic:\n"
            "  pip install funeralai[anthropic]"
        )

    client = anthropic.Anthropic(api_key=api_key, timeout=120.0)
    response = client.messages.create(
        model=model or "claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


def _call_openai_compat(
    system_prompt: str,
    user_content: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
    max_tokens: int = 2000,
) -> str:
    try:
        import openai
    except ImportError:
        raise ImportError(
            "使用 OpenAI 兼容 API 需要安装 openai:\n"
            "  pip install funeralai[openai]"
        )

    client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=120.0,
    )
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content


def _resolve_provider(
    provider: str | None = None,
    api_key: str | None = None,
) -> tuple[str, str]:
    """Determine which provider to use and return (provider_name, api_key)."""
    # Explicit provider specified
    if provider:
        provider = provider.lower()
        if provider not in PROVIDERS:
            available = ", ".join(PROVIDERS.keys())
            raise RuntimeError(f"不支持的 provider: {provider}\n支持: {available}")
        cfg = PROVIDERS[provider]
        key = api_key or os.environ.get(cfg["env_key"], "")
        if not key:
            try:
                from funeralai.config import get_api_key as _config_get_key
                key = _config_get_key(provider) or ""
            except Exception:
                pass
        if not key:
            raise RuntimeError(
                f"使用 {provider} 需要设置环境变量 {cfg['env_key']}，\n"
                f"或通过 funeralai 交互配置，或使用 --api-key 参数传入。"
            )
        return provider, _pick_key(key)

    # Explicit API key without provider — guess from prefix
    if api_key:
        if api_key.startswith("sk-ant-"):
            return "anthropic", api_key
        return "openai", api_key

    # Auto-detect: scan env vars in priority order
    for name, cfg in PROVIDERS.items():
        key = os.environ.get(cfg["env_key"], "")
        if key:
            return name, _pick_key(key)

    # Fallback: check saved config
    try:
        from funeralai.config import get_default_provider
        config_result = get_default_provider()
        if config_result:
            return config_result
    except Exception:
        pass

    env_names = [cfg["env_key"] for cfg in PROVIDERS.values()]
    raise RuntimeError(
        "未找到 API 密钥。请设置以下任一环境变量:\n"
        f"  {', '.join(env_names)}\n"
        "或运行 funeralai 进行交互配置。"
    )


def call_llm(
    provider_name: str,
    system_prompt: str,
    user_content: str,
    api_key: str,
    model: str | None = None,
    max_tokens: int = 2000,
) -> str:
    """Dispatch LLM call to the right backend."""
    cfg = PROVIDERS[provider_name]
    actual_model = model or cfg["default_model"]

    if cfg["type"] == "anthropic":
        return _call_anthropic(
            system_prompt, user_content, api_key, actual_model, max_tokens
        )
    return _call_openai_compat(
        system_prompt, user_content, api_key, actual_model, cfg["base_url"], max_tokens
    )


def _extract(
    text: str,
    provider_name: str,
    api_key: str,
    model: str | None = None,
    prompt_version: int = 1,
) -> str:
    """Pass 1: Extract structured facts from text. Returns raw extraction string."""
    extract_path = _EXTRACT_PATHS.get(prompt_version, _EXTRACT_PATHS[1])
    extract_prompt = load_prompt(extract_path)
    return call_llm(
        provider_name, extract_prompt, text, api_key, model, max_tokens=4096
    )


def _trim_extraction(parsed: dict, fields: tuple[str, ...]) -> str:
    """Extract a subset of fields from parsed extraction as JSON string."""
    subset = {k: parsed[k] for k in fields if k in parsed}
    return json.dumps(subset, ensure_ascii=False, indent=2)


def _prepare_judge_inputs(
    extraction: str,
    text: str,
    supplementary: str,
    prompt_version: int,
) -> dict[str, str]:
    """Prepare tailored inputs for each parallel judge call.

    Ad detect and summary get trimmed extraction (less tokens).
    Evidence and verdict share full context (extraction + original text).
    """
    pipeline = _PIPELINE_NAMES.get(prompt_version, "local")
    header = f"## 分析流水线: {pipeline}\n\n"

    parsed = parse_json(extraction)

    if parsed and isinstance(parsed, dict):
        ad_input = header + f"## 结构化提取\n\n{_trim_extraction(parsed, _AD_DETECT_FIELDS)}"
        summary_input = header + f"## 结构化提取\n\n{_trim_extraction(parsed, _SUMMARY_FIELDS)}"
    else:
        ad_input = header + f"## 结构化提取\n\n{extraction}"
        summary_input = header + f"## 结构化提取\n\n{extraction}"

    if supplementary:
        summary_input += f"\n\n{supplementary}"

    full_input = header + f"## 结构化提取\n\n{extraction}\n\n## 原文\n\n{text}"
    if supplementary:
        full_input += f"\n\n{supplementary}"

    return {
        "ad_detect": ad_input,
        "summary": summary_input,
        "evidence": full_input,
        "verdict": full_input,  # same as evidence — intentionally shared
    }


def _assemble_result(results: dict[str, dict | None]) -> dict:
    """Assemble final result dict from parallel judge outputs."""
    assembled: dict = {}

    # From ad detection
    ad = results.get("ad_detect")
    if ad and isinstance(ad, dict):
        assembled["article_type"] = ad.get("article_type", "evaluable")
        assembled["advertorial_confidence"] = ad.get("advertorial_confidence")
        assembled["advertorial_signals"] = ad.get("advertorial_signals", [])
    else:
        assembled["article_type"] = "evaluable"
        assembled["advertorial_confidence"] = None
        assembled["advertorial_signals"] = []

    # From summary
    summary = results.get("summary")
    if summary and isinstance(summary, dict):
        assembled["primary_product"] = summary.get("primary_product")
        assembled["product_reality"] = summary.get("product_reality")
        if "code_reality" in summary:
            assembled["code_reality"] = summary["code_reality"]
        if "product_experience" in summary:
            assembled["product_experience"] = summary["product_experience"]
    else:
        assembled["primary_product"] = None
        assembled["product_reality"] = None

    # From evidence
    evidence = results.get("evidence")
    if evidence and isinstance(evidence, dict):
        assembled["evidence"] = evidence.get("evidence", [])
    else:
        assembled["evidence"] = []

    # From verdict
    verdict = results.get("verdict")
    if verdict and isinstance(verdict, dict):
        assembled["verdict"] = verdict.get("verdict", "")
        assembled["investment_recommendation"] = verdict.get(
            "investment_recommendation", _DEFAULT_RECOMMENDATION
        )
        assembled["information_completeness"] = verdict.get(
            "information_completeness", "low"
        )
    else:
        assembled["verdict"] = ""
        assembled["investment_recommendation"] = _DEFAULT_RECOMMENDATION
        assembled["information_completeness"] = "low"

    # Handle advertorial/non_evaluable defaults
    atype = assembled.get("article_type", "")
    if atype in ("non_evaluable", "advertorial"):
        assembled.setdefault("investment_recommendation", _DEFAULT_RECOMMENDATION)

    return assembled


def _judge(
    extraction: str,
    text: str,
    provider_name: str,
    api_key: str,
    model: str | None = None,
    prompt_version: int = 1,
    supplementary: str = "",
) -> dict:
    """Pass 2: Parallel judge — 4 concurrent LLM calls, assembled into one result.

    Calls: ad_detect, summary, evidence, verdict — each with a focused prompt
    and tailored input. Runs via ThreadPoolExecutor(max_workers=4).
    """
    inputs = _prepare_judge_inputs(extraction, text, supplementary, prompt_version)
    prompts = {k: load_prompt(path) for k, path in _JUDGE_PROMPTS.items()}

    parsed_results: dict[str, dict | None] = {}

    def _call(key: str) -> tuple[str, dict | None]:
        try:
            raw = call_llm(
                provider_name, prompts[key], inputs[key], api_key, model,
                max_tokens=_JUDGE_MAX_TOKENS[key],
            )
            result = parse_json(raw)
            if result is None:
                _progress(f"  ⚠ {key}: JSON 解析失败")
            return key, result
        except Exception as e:
            _progress(f"  ⚠ {key} 失败: {e}")
            return key, None

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_call, k) for k in _JUDGE_PROMPTS]
        for future in as_completed(futures, timeout=150):
            key, result = future.result(timeout=150)
            parsed_results[key] = result

    return _assemble_result(parsed_results)


def _analyze_core(
    text: str,
    provider_name: str,
    api_key: str,
    model: str | None = None,
    prompt_version: int = 1,
    supplementary: str = "",
) -> dict:
    """Core two-pass analysis. No print side effects — caller manages output."""
    extraction = _extract(text, provider_name, api_key, model, prompt_version)
    return _judge(
        extraction, text, provider_name, api_key, model, prompt_version,
        supplementary=supplementary,
    )


def _collect_user_evidence(
    text: str,
    extraction_raw: str,
    red_flags: list[str] | None,
    provider_name: str,
    api_key: str,
    model: str | None,
) -> tuple[str, dict]:
    """Parse extraction for gaps, ask user core + supplementary questions.

    Language is auto-detected from the input text.
    Returns (supplementary_text, interactive_meta_dict).
    """
    from funeralai.questioner import (
        build_questions,
        collect_answers,
        format_answers_for_judge,
    )

    extraction_parsed = parse_json(extraction_raw)
    gaps = []
    product_name = None
    if extraction_parsed:
        gaps = extraction_parsed.get("gaps", [])
        products = extraction_parsed.get("products", [])
        if products:
            product_name = products[0]

    questions, lang = build_questions(
        text=text,
        gaps=gaps,
        red_flags=red_flags or [],
        provider_name=provider_name,
        api_key=api_key,
        model=model,
    )
    answers = collect_answers(questions, product_name=product_name, lang=lang)
    supplementary = format_answers_for_judge(answers, lang=lang)
    meta = {
        "questions_asked": len(questions),
        "questions_answered": len(answers),
        "answers": answers,
    }
    return supplementary, meta


def analyze(
    text: str,
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    prompt_version: int = 1,
    interactive: bool = True,
    red_flags: list[str] | None = None,
) -> dict:
    """Analyze input text using the analysis framework.

    Three-pass: extract → ask user for firsthand experience → judge.
    Set interactive=False to skip Q&A (batch mode, piped input, etc.).
    Non-TTY environments automatically skip Q&A even when interactive=True.
    """
    provider_name, key = _resolve_provider(provider, api_key)
    actual_model = model or PROVIDERS[provider_name]["default_model"]
    _progress(f"使用 {provider_name} ({actual_model})")
    _progress("提取中...")

    extraction = _extract(text, provider_name, key, model, prompt_version)

    supplementary = ""
    interactive_meta = None

    if interactive:
        supplementary, interactive_meta = _collect_user_evidence(
            text, extraction, red_flags, provider_name, key, model,
        )

    _progress("判断中...")
    result = _judge(
        extraction, text, provider_name, key, model, prompt_version,
        supplementary=supplementary,
    )

    if interactive_meta:
        result["_interactive"] = interactive_meta

    return result


def analyze_interactive(
    text: str,
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    prompt_version: int = 1,
    red_flags: list[str] | None = None,
) -> dict:
    """Analyze with interactive Q&A. Kept for backward compatibility.

    Equivalent to analyze(interactive=True). New code should call analyze() directly.
    """
    return analyze(
        text,
        api_key=api_key,
        model=model,
        provider=provider,
        prompt_version=prompt_version,
        interactive=True,
        red_flags=red_flags,
    )


def analyze_batch(
    files: list[str],
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    max_workers: int = 5,          # 保留签名兼容，batch 路径忽略
    on_complete: Callable | None = None,
) -> list[dict]:
    """Analyze multiple files serially.

    Serial by design: LLM API rate limits make concurrent requests to the
    same provider counterproductive. Each loop iteration naturally releases
    the text and intermediate variables for GC.
    """
    from funeralai.reader import read_file

    provider_name, key = _resolve_provider(provider, api_key)
    actual_model = model or PROVIDERS[provider_name]["default_model"]
    _progress(f"批量分析 {len(files)} 个文件 — {provider_name} ({actual_model})")

    results: list[dict] = []
    for i, path in enumerate(files):
        try:
            text = read_file(path)
            if not text.strip():
                raise ValueError("文件内容为空")
            result = _analyze_core(text, provider_name, key, model)
            entry = {"file": path, "result": result}
        except Exception as e:
            entry = {"file": path, "error": str(e)}

        results.append(entry)
        status = "✓" if "result" in entry else "✗"
        _progress(f"  [{i + 1}/{len(files)}] {status} {path}")
        if on_complete:
            on_complete(path, entry)

    return results


def _synthesize_votes(individual: list[dict]) -> dict:
    """Compute consensus from multiple model results."""
    recs = []
    for entry in individual:
        result = entry.get("result")
        if result:
            rec = result.get("investment_recommendation", "")
            if rec:
                recs.append(rec)

    if not recs:
        return {
            "agreement": "split",
            "recommendation": _DEFAULT_RECOMMENDATION,
            "details": "所有模型均未返回有效结论",
        }

    counts = Counter(recs)
    total = len(recs)
    most_common_rec, most_common_count = counts.most_common(1)[0]

    if most_common_count == total:
        agreement = "unanimous"
        details = f"{total}/{total} 模型一致认为{most_common_rec}"
    elif most_common_count > total / 2:
        agreement = "majority"
        details = f"{most_common_count}/{total} 模型认为{most_common_rec}"
    else:
        agreement = "split"
        parts = [f"{c}票{r}" for r, c in counts.most_common()]
        details = "意见分裂: " + ", ".join(parts)

    return {
        "agreement": agreement,
        "recommendation": most_common_rec,
        "details": details,
    }


def analyze_vote(
    text: str,
    providers: list[str],
    model: str | None = None,
    max_workers: int | None = None,
    prompt_version: int = 1,
    interactive: bool = True,
    red_flags: list[str] | None = None,
) -> dict:
    """Run the same text through multiple providers in parallel, then vote.

    When interactive=True, does a pre-extract with the first provider to get
    gaps, asks the user once, then shares the user's answers across all
    providers' judge passes.
    """
    workers = max_workers or len(providers)
    _progress(f"多模型投票 — {', '.join(providers)}, 并发 {workers}")

    # Collect user evidence once before parallel analysis
    supplementary = ""
    interactive_meta = None
    pre_extraction = None
    first_prov = None

    if interactive:
        first_prov, first_key = _resolve_provider(providers[0])
        _progress("预提取中（用于生成问题）...")
        pre_extraction = _extract(
            text, first_prov, first_key, model, prompt_version,
        )
        supplementary, interactive_meta = _collect_user_evidence(
            text, pre_extraction, red_flags, first_prov, first_key, model,
        )

    individual: list[dict] = [None] * len(providers)  # type: ignore[list-item]
    lock = threading.Lock()
    done_count = 0

    def _run(idx: int, prov: str) -> dict:
        nonlocal done_count
        actual_model = model or PROVIDERS.get(prov, {}).get("default_model", "?")
        try:
            _, key = _resolve_provider(prov)
            # Reuse pre-extraction for first provider to avoid duplicate LLM call
            if pre_extraction is not None and prov == first_prov:
                result = _judge(
                    pre_extraction, text, prov, key, model,
                    prompt_version, supplementary=supplementary,
                )
            else:
                result = _analyze_core(
                    text, prov, key, model,
                    prompt_version=prompt_version,
                    supplementary=supplementary,
                )
            entry = {"provider": prov, "model": actual_model, "result": result}
        except Exception as e:
            entry = {"provider": prov, "model": actual_model, "error": str(e)}

        with lock:
            done_count += 1
            status = "✓" if "result" in entry else "✗"
            _progress(f"  [{done_count}/{len(providers)}] {status} {prov}")
        return entry

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_run, i, p): i for i, p in enumerate(providers)
        }
        for future in as_completed(futures):
            idx = futures[future]
            individual[idx] = future.result()

    consensus = _synthesize_votes(individual)

    vote_result = {
        "mode": "vote",
        "individual_results": individual,
        "consensus": consensus,
    }
    if interactive_meta:
        vote_result["_interactive"] = interactive_meta

    return vote_result
