"""UI language detection + bilingual string mapping.

All user-facing text in the CLI goes through ``t(key)``.

Language detection priority:
    1. config.json ``lang`` field (user explicit setting)
    2. LANG / LC_ALL env var (e.g. zh_CN.UTF-8 -> zh)
    3. Default: en

This is **UI language** (interface text), separate from questioner.py's
``_detect_lang(text)`` which detects analysis language based on input
content CJK ratio.
"""

import os

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_current_lang: str = "en"

# ---------------------------------------------------------------------------
# String registry — every user-facing string lives here
# ---------------------------------------------------------------------------

_STRINGS: dict[str, dict[str, str]] = {
    # Welcome / Slogan
    "slogan":          {"zh": "整点真实", "en": "be real"},
    "welcome_back":    {"zh": "欢迎回来",  "en": "Welcome back"},

    # Status bar
    "status_bar":      {"zh": "葬AI v{version} | {provider} ({model})",
                        "en": "ZangAI v{version} | {provider} ({model})"},

    # Setup
    "no_api_key":      {"zh": "未检测到 API key。粘贴你的 API key（推荐 Anthropic Claude）：",
                        "en": "No API key detected. Paste your API key (Anthropic Claude recommended):"},
    "codex_detected":  {"zh": "✓ 检测到 Codex CLI 已登录，使用 OpenAI (via codex auth)",
                        "en": "✓ Codex CLI auth detected, using OpenAI (via codex auth)"},
    "key_saved":       {"zh": "✓ 已保存 {provider} ({masked_key}) 到 ~/.config/funeralai/config.json",
                        "en": "✓ Saved {provider} ({masked_key}) to ~/.config/funeralai/config.json"},
    "pick_provider":   {"zh": "请选择 LLM 提供商：",
                        "en": "Pick your LLM provider:"},
    "invalid_choice":  {"zh": "请输入编号 1-{n} 或 provider 名称",
                        "en": "Enter a number 1-{n} or provider name"},
    "no_key_non_tty":  {"zh": "未找到 API 密钥。请设置环境变量（如 OPENAI_API_KEY）或运行 funeralai 进行交互配置。",
                        "en": "No API key found. Set an env var (e.g. OPENAI_API_KEY) or run funeralai interactively."},

    # Intent feedback
    "detected_github": {"zh": "检测到 GitHub 仓库，正在实查...",
                        "en": "GitHub repo detected, inspecting..."},
    "detected_web":    {"zh": "检测到网页，正在实查...",
                        "en": "Web page detected, inspecting..."},
    "detected_file":   {"zh": "检测到本地文件: {name}",
                        "en": "Local file detected: {name}"},
    "detected_dir":    {"zh": "检测到目录: {path}，找到 {n} 个文件，开始批量分析...",
                        "en": "Directory detected: {path}, found {n} files, starting batch..."},
    "batch_no_ask":    {"zh": "（批量模式跳过体验问答）",
                        "en": "(Batch mode skips experience Q&A)"},
    "switched":        {"zh": "✓ 切换到 {provider} ({model})",
                        "en": "✓ Switched to {provider} ({model})"},
    "goodbye":         {"zh": "再见", "en": "Goodbye"},

    # Error recovery
    "err_api_key":     {"zh": "API key 无效。重新配置?",
                        "en": "API key invalid. Reconfigure?"},
    "err_rate_limit":  {"zh": "请求太频繁。试试切换 provider: /provider deepseek",
                        "en": "Rate limited. Try switching: /provider deepseek"},

    # Unclear input
    "unclear_greeting": {"zh": "你好。粘贴 URL、拖入文件、或贴文章内容，我来分析。",
                         "en": "Hi. Paste a URL, drag a file, or paste article content to start."},
    "unclear_default":  {"zh": "粘贴 URL、拖入文件、或贴文章内容开始分析。输入 /help 查看更多用法",
                         "en": "Paste a URL, drag a file, or paste content to analyze. Type /help for more."},

    # Help / Dashboard command table
    "cmd_file":        {"zh": "分析本地文件 (.md/.txt/.pdf)",   "en": "Analyze local file (.md/.txt/.pdf)"},
    "cmd_url":         {"zh": "分析 GitHub 仓库或网页",         "en": "Analyze GitHub repo or web page"},
    "cmd_batch":       {"zh": "批量分析多个文件",               "en": "Batch analyze multiple files"},
    "cmd_vote":        {"zh": "多模型投票",                     "en": "Multi-model vote"},
    "cmd_help":        {"zh": "查看全部选项",                   "en": "Show all options"},

    # TUI: Tips (displayed on home screen, random selection)
    "tip_slash":       {"zh": "输入 / 查看所有可用命令",
                        "en": "Type / to see all available commands"},
    "tip_github":      {"zh": "粘贴 GitHub URL 自动实查仓库",
                        "en": "Paste a GitHub URL to auto-inspect the repo"},
    "tip_vote":        {"zh": "用 /vote deepseek,openai 运行多模型投票",
                        "en": "Use /vote deepseek,openai for multi-model voting"},
    "tip_file":        {"zh": "拖入文件到终端即可开始分析",
                        "en": "Drag a file into the terminal to start analysis"},
    "tip_palette":     {"zh": "按 Ctrl+K 打开命令面板",
                        "en": "Press Ctrl+K to open the command palette"},
    "tip_provider":    {"zh": "输入 /provider 切换 LLM 提供商",
                        "en": "Type /provider to switch LLM providers"},
    "tip_theme":       {"zh": "输入 /theme 切换配色方案",
                        "en": "Type /theme to change the color theme"},
    "tip_retry":       {"zh": "输入「再来一次」或 retry 重新分析上次输入",
                        "en": "Type 'retry' to re-analyze the last input"},
    "tip_web":         {"zh": "粘贴任意网页 URL 体验产品实查分析",
                        "en": "Paste any web URL for product experience analysis"},
    "tip_lang":        {"zh": "输入 /lang 切换界面语言（中/英）",
                        "en": "Type /lang to switch UI language (zh/en)"},

    # TUI: Command palette categories
    "cat_analysis":    {"zh": "分析", "en": "Analysis"},
    "cat_provider":    {"zh": "提供商", "en": "Provider"},
    "cat_system":      {"zh": "系统", "en": "System"},

    # TUI: Command titles (for command palette and slash commands)
    "cmd_switch_provider":  {"zh": "切换 Provider", "en": "Switch Provider"},
    "cmd_switch_model":     {"zh": "切换模型", "en": "Switch Model"},
    "cmd_multi_vote":       {"zh": "多模型投票", "en": "Multi-model Vote"},
    "cmd_switch_lang":      {"zh": "切换语言", "en": "Switch Language"},
    "cmd_switch_theme":     {"zh": "切换主题", "en": "Switch Theme"},
    "cmd_show_config":      {"zh": "显示配置", "en": "Show Config"},
    "cmd_show_help":        {"zh": "显示帮助", "en": "Show Help"},
    "cmd_new_analysis":     {"zh": "新分析", "en": "New Analysis"},
    "cmd_show_history":     {"zh": "历史记录", "en": "History"},
    "cmd_clear":            {"zh": "清屏", "en": "Clear Screen"},
    "cmd_retry":            {"zh": "重新分析", "en": "Retry Analysis"},
    "cmd_exit":             {"zh": "退出", "en": "Exit"},

    # TUI: Spinner / status messages
    "status_inspecting_github": {"zh": "正在检查 GitHub 仓库...",
                                  "en": "Inspecting GitHub repo..."},
    "status_inspecting_web":    {"zh": "正在检查网页...",
                                  "en": "Inspecting web page..."},
    "status_extracting":        {"zh": "正在提取结构化事实...",
                                  "en": "Extracting structured facts..."},
    "status_asking":            {"zh": "正在收集一手体验...",
                                  "en": "Collecting first-hand experience..."},
    "status_judging":           {"zh": "4 路并行判断中...",
                                  "en": "Running 4 parallel judgments..."},
    "status_chatting":          {"zh": "正在思考...", "en": "Thinking..."},
    "status_done":              {"zh": "分析完成", "en": "Analysis complete"},

    # TUI: Dialog titles
    "dlg_provider_title":  {"zh": "选择 Provider", "en": "Select Provider"},
    "dlg_model_title":     {"zh": "选择模型", "en": "Select Model"},
    "dlg_vote_title":      {"zh": "选择投票 Provider（至少 2 个）",
                            "en": "Select Providers for Vote (min 2)"},
    "dlg_theme_title":     {"zh": "选择主题", "en": "Select Theme"},
    "dlg_help_title":      {"zh": "帮助", "en": "Help"},
    "dlg_config_title":    {"zh": "当前配置", "en": "Current Config"},
    "dlg_setup_title":     {"zh": "首次配置", "en": "Initial Setup"},

    # TUI: Footer
    "footer_no_provider":  {"zh": "未配置 Provider", "en": "No provider configured"},

    # TUI: Placeholder prompts (random, shown in input box)
    "placeholder_0":       {"zh": "粘贴 URL 或文章内容开始分析...",
                            "en": "Paste a URL or article content to analyze..."},
    "placeholder_1":       {"zh": "这个产品到底行不行？",
                            "en": "Is this product actually any good?"},
    "placeholder_2":       {"zh": "拖入文件，我来看看...",
                            "en": "Drag in a file, let me take a look..."},

    # TUI: Setup
    "setup_env_detected":  {"zh": "✓ 检测到环境变量 {provider}",
                            "en": "✓ Detected env var for {provider}"},
    "setup_paste_key":     {"zh": "粘贴你的 API key：",
                            "en": "Paste your API key:"},
    "setup_use_detected":    {"zh": "使用已检测到的 Provider",
                              "en": "Use detected provider"},
    "setup_configure_other": {"zh": "配置其他 Provider（推荐 Claude）",
                              "en": "Configure different provider (Claude recommended)"},
    "setup_select_provider": {"zh": "选择 Provider（无法自动识别 key 类型）：",
                              "en": "Select provider (cannot auto-detect key type):"},
    "setup_validating":      {"zh": "正在验证 {provider} API key...",
                              "en": "Verifying {provider} API key..."},
    "setup_saved_unverified": {"zh": "已保存 {provider}，但当前无法在线验证。后续分析时会再次尝试。",
                               "en": "Saved {provider}, but could not verify it online right now. Analysis will retry later."},
    "setup_reauth_prompt":   {"zh": "{provider} 登录失败。请选择其他 Provider，或重新输入这个 Provider 的 key。",
                              "en": "{provider} authentication failed. Select another provider or enter a new key for this provider."},

    # TUI: Question flow
    "question_prompt":     {"zh": "回答问题（Enter 跳过，q 跳过全部）：",
                            "en": "Answer (Enter to skip, q to skip all):"},
    "question_skipped":    {"zh": "（已跳过剩余问题）",
                            "en": "(Remaining questions skipped)"},
}

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def _lang_from_config() -> str | None:
    """Read lang field from config.json. Return None on any failure."""
    try:
        from funeralai.config import load_config
        lang = load_config().get("lang", "").strip().lower()
        if lang in ("zh", "en"):
            return lang
    except Exception:
        pass
    return None


def _lang_from_env() -> str | None:
    """Infer language from LANG / LC_ALL environment variables."""
    for var in ("LC_ALL", "LANG"):
        val = os.environ.get(var, "").lower()
        if val.startswith("zh"):
            return "zh"
        if val and val != "c" and val != "posix":
            # Any non-Chinese locale -> en
            return "en"
    return None


def detect_ui_lang() -> str:
    """Detect UI language. Priority: config > env > default en."""
    return _lang_from_config() or _lang_from_env() or "en"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_lang() -> None:
    """Call once at startup to set module-level language."""
    global _current_lang
    _current_lang = detect_ui_lang()


def set_lang(lang: str) -> None:
    """Switch language at runtime (e.g. /lang command)."""
    global _current_lang
    if lang in ("zh", "en"):
        _current_lang = lang


def get_lang() -> str:
    """Return current UI language code."""
    return _current_lang


# Tip keys for random selection on home screen
TIP_KEYS = [
    "tip_slash", "tip_github", "tip_vote", "tip_file", "tip_palette",
    "tip_provider", "tip_theme", "tip_retry", "tip_web", "tip_lang",
]

# Placeholder keys for random selection in input box
PLACEHOLDER_KEYS = ["placeholder_0", "placeholder_1", "placeholder_2"]


def t(key: str, **kwargs) -> str:
    """Get localized string for *key*, formatted with *kwargs*.

    Falls back to English if the key or language is missing.
    Returns the raw key if it isn't registered at all.
    """
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_current_lang) or entry.get("en", key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass  # return unformatted if caller missed a kwarg
    return text
