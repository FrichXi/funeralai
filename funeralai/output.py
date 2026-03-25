"""Output formatting: terminal (human-readable) and JSON."""

from __future__ import annotations

import json
import sys


# Terminal colors (ANSI)
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[91m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_RESET = "\033[0m"


def _use_color() -> bool:
    """Check if stdout supports color."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _make_c():
    """Return a colorize helper based on current terminal capability."""
    if _use_color():
        return lambda code, text: f"{code}{text}{_RESET}"
    return lambda code, text: text


def format_json(result: dict) -> str:
    """Format result as JSON string."""
    return json.dumps(result, ensure_ascii=False, indent=2)


def _rec_styled(recommendation: str, c) -> str:
    """Return recommendation with emoji and color."""
    if "进一步看" in recommendation:
        return f"\U0001f913 {c(_GREEN + _BOLD, recommendation)}"  # 🤓
    elif "不建议" in recommendation:
        return f"\U0001f62d {c(_RED + _BOLD, recommendation)}"  # 😭
    else:
        return f"\U0001f914 {c(_YELLOW + _BOLD, recommendation)}"  # 🤔


def _type_label(article_type: str) -> str:
    """Human-readable label for article_type."""
    labels = {
        "evaluable": "可评估",
        "non_evaluable": "不涉及产品评价",
        "advertorial": "广告/软文",
    }
    return labels.get(article_type, article_type)


def _display_width(s: str) -> int:
    """Approximate display width accounting for CJK double-width characters."""
    w = 0
    for ch in s:
        cp = ord(ch)
        if (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0xF900 <= cp <= 0xFAFF
            or 0xFF01 <= cp <= 0xFF60
            or 0x3000 <= cp <= 0x303F
        ):
            w += 2
        else:
            w += 1
    return w


def _add_section(
    lines: list[str],
    title: str,
    items: list[str],
    c,
    item_color: str,
) -> None:
    """Add a section with bullet items."""
    if not items:
        return
    pad = max(1, 30 - _display_width(title))
    lines.append(c(_DIM, f"\u2500\u2500\u2500 {title} " + "\u2500" * pad))
    for item in items:
        lines.append(f"  - {item}")
    lines.append("")


_EVIDENCE_TYPE_ZH = {
    "fact": "事实",
    "inference": "推断",
    "risk": "风险",
    "promotional": "推广",
    "code_inspection": "代码实查",
    "product_testing": "产品实测",
}


def _render_result_body(result: dict, c, lines: list[str], *, show_type: bool = True) -> None:
    """Render the analysis report body.

    Layout: product summary → evidence → verdict → ad detection.
    """
    article_type = result.get("article_type", "unknown")
    primary_product = result.get("primary_product") or "-"
    recommendation = result.get("investment_recommendation", "-")

    # ── Product summary ──
    type_label = _type_label(article_type)
    lines.append(f"  {c(_BOLD, primary_product)}")
    if show_type:
        lines.append(f"  来源: {type_label}  \u00b7  {_rec_styled(recommendation, c)}")
    else:
        lines.append(f"  {_rec_styled(recommendation, c)}")
    lines.append("")

    product_reality = result.get("product_reality")
    if product_reality:
        lines.append(f"  {product_reality}")
        lines.append("")

    if article_type == "non_evaluable":
        return

    # ── Evidence ──
    evidence = result.get("evidence", [])
    if evidence:
        pad = max(1, 30 - _display_width("证据"))
        lines.append(c(_DIM, f"\u2500\u2500 证据 " + "\u2500" * pad))
        lines.append("")
        for e in evidence:
            etype = e.get("type", "fact")
            quote = e.get("quote", "")
            claim = e.get("claim", "")
            type_label_e = _EVIDENCE_TYPE_ZH.get(etype, etype)
            if etype in ("code_inspection", "product_testing"):
                tag = c(_YELLOW + _BOLD, f"[{type_label_e}]")
            elif etype == "risk":
                tag = c(_RED, f"[{type_label_e}]")
            elif etype == "promotional":
                tag = c(_YELLOW, f"[{type_label_e}]")
            else:
                tag = c(_CYAN, f"[{type_label_e}]")
            lines.append(f"  {tag} {claim}")
            if quote:
                lines.append(c(_DIM, f"         \u300c{quote}\u300d"))
        lines.append("")

    # ── Verdict ──
    verdict = result.get("verdict", "")
    if verdict:
        pad = max(1, 30 - _display_width("结论"))
        lines.append(c(_DIM, f"\u2500\u2500 结论 " + "\u2500" * pad))
        lines.append("")
        lines.append(f"  {c(_BOLD, verdict)}")
        lines.append("")

    # ── Ad detection ──
    ad_confidence = result.get("advertorial_confidence")
    ad_signals = result.get("advertorial_signals", [])
    if ad_confidence and ad_signals:
        confidence_zh = {"high": "高", "medium": "中", "low": "低"}.get(
            ad_confidence, ad_confidence
        )
        pad = max(1, 30 - _display_width(f"广告浓度: {confidence_zh}"))
        lines.append(c(_DIM, f"\u2500\u2500 广告浓度: {confidence_zh} \U0001f921 " + "\u2500" * pad))
        for s in ad_signals:
            lines.append(f"  \u00b7 {s}")
        lines.append("")

    # Interactive Q&A supplementary info
    _render_interactive_section(result, c, lines)


def _render_interactive_section(result: dict, c, lines: list[str]) -> None:
    """Render the interactive Q&A section if present."""
    interactive = result.get("_interactive")
    if not interactive:
        return

    asked = interactive.get("questions_asked", 0)
    answered = interactive.get("questions_answered", 0)
    answers = interactive.get("answers", [])

    if not answers:
        return

    title = f"补充信息 (问 {asked} / 答 {answered})"
    pad = max(1, 30 - _display_width(title))
    lines.append(c(_DIM, f"─── {title} " + "─" * pad))
    lines.append(c(_DIM, "  以下信息来自用户补充，非原始材料"))
    for a in answers:
        lines.append(f"  Q: {a['question']}")
        lines.append(f"  A: {c(_BOLD, a['answer'])}")
        lines.append("")


def _render_vote_body(vote_result: dict, c, lines: list[str]) -> None:
    """Render consensus + per-model results. Shared by vote terminal formatters."""
    consensus = vote_result.get("consensus", {})
    individual = vote_result.get("individual_results", [])

    # Consensus
    agreement = consensus.get("agreement", "split")
    agreement_label = {
        "unanimous": "一致同意",
        "majority": "多数同意",
        "split": "意见分裂",
    }.get(agreement, agreement)

    rec = consensus.get("recommendation", "-")
    details = consensus.get("details", "")

    lines.append(c(_DIM, "──── 共识 " + "─" * 28))
    lines.append(f"  投票结果: {c(_BOLD, agreement_label)}")
    lines.append(f"  结论: {_rec_styled(rec, c)}")
    if details:
        lines.append(f"  详情: {details}")
    lines.append("")

    # Per-model results
    for entry in individual:
        prov = entry.get("provider", "?")
        lines.append(c(_DIM, f"──── {prov} " + "─" * max(1, 33 - _display_width(prov))))

        if "error" in entry:
            lines.append(c(_RED, f"  错误: {entry['error']}"))
        else:
            result = entry.get("result", {})
            r = result.get("investment_recommendation", "-")
            lines.append(f"  结论: {_rec_styled(r, c)}")
            code_reality = result.get("code_reality", "")
            if code_reality:
                lines.append(f"  代码真相: {code_reality}")
            product_exp = result.get("product_experience", "")
            if product_exp:
                lines.append(f"  产品体验: {product_exp}")
            reality = result.get("product_reality", "")
            if reality:
                lines.append(f"  说人话: {reality}")
            verdict = result.get("verdict", "")
            if verdict:
                lines.append(f"  判断: {verdict}")
        lines.append("")


# ── Single file output ───────────────────────────────────────


def format_terminal(result: dict) -> str:
    """Format result as a human-readable terminal report in Chinese."""
    c = _make_c()
    lines: list[str] = []

    # Header
    lines.append("")
    lines.append(c(_BOLD, "═" * 39))
    lines.append(c(_BOLD, "  葬AI 分析报告"))
    lines.append(c(_BOLD, "═" * 39))
    lines.append("")

    _render_result_body(result, c, lines)

    return "\n".join(lines)


# ── Batch output ──────────────────────────────────────────────


def format_batch_terminal(results: list[dict]) -> str:
    """Format batch results: one report block per file + summary."""
    c = _make_c()
    lines: list[str] = []

    success = 0
    fail = 0

    for entry in results:
        path = entry.get("file", "?")
        lines.append(c(_BOLD, f"\n{'═' * 39}"))
        lines.append(c(_BOLD, f"  {path}"))
        lines.append(c(_BOLD, "═" * 39))

        if "error" in entry:
            fail += 1
            lines.append(c(_RED, f"  错误: {entry['error']}"))
            lines.append("")
        else:
            success += 1
            lines.append(format_terminal(entry["result"]))

    # Summary
    lines.append(c(_BOLD, f"\n{'─' * 39}"))
    lines.append(
        c(_BOLD, f"  汇总: {success} 成功, {fail} 失败, 共 {len(results)} 个文件")
    )
    lines.append("")

    return "\n".join(lines)


def format_batch_json(results: list[dict]) -> str:
    """Format batch results as a JSON array."""
    return format_json(results)


# ── Vote output ───────────────────────────────────────────────


def format_vote_terminal(vote_result: dict) -> str:
    """Format vote results: consensus summary + per-model conclusions."""
    c = _make_c()
    lines: list[str] = []

    # Header
    lines.append("")
    lines.append(c(_BOLD, "═" * 39))
    lines.append(c(_BOLD, "  葬AI 多模型投票报告"))
    lines.append(c(_BOLD, "═" * 39))
    lines.append("")

    _render_vote_body(vote_result, c, lines)

    return "\n".join(lines)


def format_vote_json(vote_result: dict) -> str:
    """Format vote results as JSON."""
    return format_json(vote_result)


# ── GitHub inspection output ─────────────────────────────────


def _format_inspection_section(inspection: dict, c) -> list[str]:
    """Render the code inspection summary block for terminal output."""
    from funeralai.inspector import format_languages

    lines: list[str] = []
    api = inspection.get("api", {})
    owner = inspection.get("owner", "?")
    repo = inspection.get("repo", "?")
    stars = api.get("stars", 0)
    forks = api.get("forks", 0)

    pad = max(1, 30 - _display_width("代码实查"))
    lines.append(c(_DIM, f"─── 代码实查 " + "─" * pad))

    lines.append(f"  仓库: {c(_BOLD, f'{owner}/{repo}')} | Stars: {stars:,} | Forks: {forks:,}")

    # Languages
    languages = api.get("languages", {})
    if languages:
        lang_str = format_languages(languages)
        if lang_str != "无数据":
            lines.append(f"  语言: {lang_str}")

    # Contributors
    contributors = api.get("contributors", [])
    if contributors:
        total_c = sum(ct["contributions"] for ct in contributors)
        if total_c > 0:
            top = contributors[0]
            pct = top["contributions"] / total_c * 100
            lines.append(
                f"  贡献者: {len(contributors)} 人 ({top['login']} 占 {pct:.0f}%)"
            )

    # LOC breakdown — use precomputed totals
    totals = inspection.get("totals", {})
    total_files = inspection.get("total_files", 0)
    if total_files > 0:
        code_ratio = totals.get("code_ratio", 0)
        ratio_color = _RED if code_ratio < 30 else _GREEN if code_ratio > 60 else _YELLOW
        lines.append(f"  文件: {total_files} | 总行数: ~{totals.get('total', 0):,}")
        lines.append(
            f"  代码: ~{totals.get('code', 0):,} ({c(ratio_color, f'{code_ratio:.0f}%')}) | "
            f"文档: ~{totals.get('doc', 0):,} | 模板: ~{totals.get('template', 0):,} | 配置: ~{totals.get('config', 0):,}"
        )

    # Tests
    tests = inspection.get("tests", {})
    if tests.get("has_tests"):
        lines.append(c(_GREEN, f"  测试: ✓ {tests.get('test_file_count', 0)} 个测试文件"))
    else:
        lines.append(c(_RED, "  测试: ❌ 未发现"))

    # Build/CI
    build = inspection.get("build", {})
    if build.get("ci_systems"):
        lines.append(f"  CI: ✓ {', '.join(build['ci_systems'])}")
    if build.get("build_systems"):
        lines.append(f"  构建: {', '.join(build['build_systems'])}")

    # Red flags
    red_flags = inspection.get("red_flags", [])
    if red_flags:
        lines.append("")
        for flag in red_flags:
            lines.append(c(_RED, f"  🚩 {flag}"))

    lines.append("")
    return lines


def _format_terminal_inspected(
    result: dict,
    inspection: dict,
    title: str,
    inspection_renderer,
    extra_fields: list[tuple[str, str]],
) -> str:
    """Shared formatter for inspection-based analysis (GitHub / Web)."""
    c = _make_c()
    lines: list[str] = []

    lines.append("")
    lines.append(c(_BOLD, "═" * 39))
    lines.append(c(_BOLD, f"  葬AI 分析报告 — {title}"))
    lines.append(c(_BOLD, "═" * 39))
    lines.append("")

    lines.extend(inspection_renderer(inspection, c))

    for field_key, field_label in extra_fields:
        value = result.get(field_key)
        if value:
            lines.append(f"  {field_label}: {c(_BOLD, value)}")
            lines.append("")

    _render_result_body(result, c, lines, show_type=False)
    return "\n".join(lines)


def _format_vote_terminal_inspected(
    vote_result: dict,
    inspection: dict,
    title: str,
    inspection_renderer,
) -> str:
    """Shared formatter for inspection-based vote reports (GitHub / Web)."""
    c = _make_c()
    lines: list[str] = []

    lines.append("")
    lines.append(c(_BOLD, "═" * 39))
    lines.append(c(_BOLD, f"  葬AI 多模型投票报告 — {title}"))
    lines.append(c(_BOLD, "═" * 39))
    lines.append("")

    lines.extend(inspection_renderer(inspection, c))
    _render_vote_body(vote_result, c, lines)
    return "\n".join(lines)


def _github_title(inspection: dict) -> str:
    return f"{inspection.get('owner', '?')}/{inspection.get('repo', '?')}"


def _web_title(inspection: dict) -> str:
    return inspection.get("title") or inspection.get("url", "?")


def format_terminal_github(result: dict, inspection: dict) -> str:
    """Format GitHub analysis result: inspection block + standard analysis."""
    return _format_terminal_inspected(
        result, inspection,
        title=_github_title(inspection),
        inspection_renderer=_format_inspection_section,
        extra_fields=[("code_reality", "代码真相")],
    )


def format_vote_terminal_github(vote_result: dict, inspection: dict) -> str:
    """Format GitHub vote results: inspection block + per-model conclusions."""
    return _format_vote_terminal_inspected(
        vote_result, inspection,
        title=_github_title(inspection),
        inspection_renderer=_format_inspection_section,
    )


# ── Web inspection output ─────────────────────────────────


def _format_web_inspection_section(inspection: dict, c) -> list[str]:
    """Render the web inspection summary block for terminal output."""
    lines: list[str] = []
    url = inspection.get("url", "?")
    title = inspection.get("title") or "无标题"

    pad = max(1, 30 - _display_width("产品体验实查"))
    lines.append(c(_DIM, f"─── 产品体验实查 " + "─" * pad))

    lines.append(f"  URL: {c(_BOLD, url)}")
    lines.append(f"  标题: {title}")

    # HTTP status
    status = inspection.get("status_code")
    if status:
        status_color = _GREEN if status < 400 else _RED
        lines.append(f"  状态码: {c(status_color, str(status))}")

    response_time = inspection.get("response_time_ms")
    if response_time:
        time_color = _GREEN if response_time < 2000 else _YELLOW if response_time < 5000 else _RED
        lines.append(f"  响应时间: {c(time_color, f'{response_time}ms')}")

    content_len = inspection.get("content_length", 0)
    lines.append(f"  内容长度: {content_len:,} 字符")

    if inspection.get("redirected"):
        final = inspection.get("final_url", "?")
        if inspection.get("redirect_domain_changed"):
            lines.append(c(_YELLOW, f"  重定向: 跨域 → {final}"))
        else:
            lines.append(f"  重定向: → {final}")

    if inspection.get("blocked"):
        lines.append(c(_RED, "  反爬拦截: ✗ 被拦截"))

    # Browser test results
    browser = inspection.get("browser")
    if browser and not browser.get("error"):
        load_ms = browser.get("page_load_ms")
        if load_ms:
            load_color = _GREEN if load_ms < 2000 else _YELLOW if load_ms < 5000 else _RED
            lines.append(f"  页面加载: {c(load_color, f'{load_ms}ms')}")

        js_errors = browser.get("js_errors", [])
        if js_errors:
            lines.append(c(_RED, f"  JS 错误: {len(js_errors)} 个"))
        else:
            lines.append(c(_GREEN, "  JS 错误: 无"))

        res = browser.get("resource_stats", {})
        failed = res.get("failed", 0)
        if failed:
            lines.append(c(_RED, f"  资源: {res.get('total', 0)} 个 (失败 {failed})"))
        else:
            lines.append(f"  资源: {res.get('total', 0)} 个")

        ie = browser.get("interactive_elements", {})
        total_ie = ie.get("forms", 0) + ie.get("buttons", 0) + ie.get("inputs", 0)
        ie_color = _GREEN if total_ie > 0 else _RED
        lines.append(
            c(ie_color,
              f"  交互元素: 表单 {ie.get('forms', 0)} / "
              f"按钮 {ie.get('buttons', 0)} / "
              f"输入框 {ie.get('inputs', 0)}")
        )

        lh = browser.get("link_health", {})
        if lh.get("checked", 0) > 0:
            broken = lh.get("broken", 0)
            link_color = _GREEN if broken == 0 else _RED
            lines.append(
                c(link_color,
                  f"  链接健康: {lh['checked'] - broken}/{lh['checked']} 可访问")
            )
    elif not inspection.get("browser_tested", False):
        lines.append(c(_DIM, "  浏览器测试: 未启用"))

    # Red flags
    red_flags = inspection.get("red_flags", [])
    if red_flags:
        lines.append("")
        for flag in red_flags:
            lines.append(c(_RED, f"  🚩 {flag}"))

    lines.append("")
    return lines


def format_terminal_web(result: dict, inspection: dict) -> str:
    """Format web URL analysis result: inspection block + standard analysis."""
    return _format_terminal_inspected(
        result, inspection,
        title=_web_title(inspection),
        inspection_renderer=_format_web_inspection_section,
        extra_fields=[("product_experience", "产品体验")],
    )


def format_vote_terminal_web(vote_result: dict, inspection: dict) -> str:
    """Format web URL vote results: inspection block + per-model conclusions."""
    return _format_vote_terminal_inspected(
        vote_result, inspection,
        title=_web_title(inspection),
        inspection_renderer=_format_web_inspection_section,
    )
