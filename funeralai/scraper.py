"""Web page inspector: HTTP fetch + content extraction + browser experience testing.

Produces a structured inspection report for product websites, checking whether
the product actually works — not just what the marketing copy says.
"""

from __future__ import annotations

import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _fetch_and_extract(url: str) -> dict:
    """Phase 1: HTTP fetch + content extraction via trafilatura.

    Returns structured data about the page's HTTP response and extracted content.
    """
    try:
        import httpx
    except ImportError:
        raise ImportError(
            "网页分析缺少依赖 httpx，请重新安装：\n"
            "  pip install funeralai"
        )

    data = {
        "url": url,
        "final_url": url,
        "status_code": None,
        "response_time_ms": None,
        "title": None,
        "description": None,
        "content_text": "",
        "content_length": 0,
        "content_extracted": True,
        "redirected": False,
        "redirect_domain_changed": False,
        "blocked": False,
        "error": None,
    }

    try:
        start = time.monotonic()
        with httpx.Client(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            },
        ) as client:
            response = client.get(url)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        data["status_code"] = response.status_code
        data["response_time_ms"] = elapsed_ms
        data["final_url"] = str(response.url)

        # Check redirect
        if str(response.url) != url:
            data["redirected"] = True
            orig_domain = urlparse(url).netloc
            final_domain = urlparse(str(response.url)).netloc
            if orig_domain != final_domain:
                data["redirect_domain_changed"] = True

        html = response.text

        # Check for bot/Cloudflare block
        if response.status_code in (403, 503):
            body_lower = html[:2000].lower()
            if any(kw in body_lower for kw in ("cloudflare", "captcha", "challenge", "bot")):
                data["blocked"] = True
                data["error"] = "被反爬虫机制拦截 (Cloudflare/CAPTCHA)"
                return data

        if response.status_code >= 400:
            data["error"] = f"HTTP {response.status_code}"
            return data

        # Extract title from HTML
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match:
            data["title"] = title_match.group(1).strip()[:200]

        # Extract meta description
        desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
            html, re.IGNORECASE,
        )
        if desc_match:
            data["description"] = desc_match.group(1).strip()[:500]

        # Extract main content via trafilatura
        try:
            import trafilatura
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
            )
            if extracted:
                # Truncate to 10,000 chars
                data["content_text"] = extracted[:10000]
                data["content_length"] = len(extracted)
                data["content_extracted"] = True
        except ImportError:
            raise ImportError(
                "网页内容提取缺少依赖 trafilatura，请重新安装：\n"
                "  pip install funeralai"
            )
        except Exception:
            # trafilatura extraction failed — signal via flag, keep content empty
            data["content_text"] = ""
            data["content_extracted"] = False

    except ImportError:
        raise
    except Exception as e:
        # httpx errors (TimeoutException, ConnectError, etc.)
        error_str = str(e)
        if "timeout" in error_str.lower():
            data["error"] = "请求超时 (>30s)"
            data["response_time_ms"] = 30000
        elif "connect" in error_str.lower():
            data["error"] = "无法连接到服务器"
        else:
            data["error"] = error_str

    return data


_browser_installed: bool | None = None  # cached after first check


def _install_browser() -> bool:
    """Auto-install playwright chromium. Returns True on success."""
    import subprocess

    try:
        from funeralai.analyzer import _progress
        _progress("首次使用，正在下载浏览器...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
        )
        return True
    except Exception:
        return False


def _browser_probe(url: str) -> dict | None:
    """Phase 2: Browser experience test via playwright.

    Returns browser-level metrics or None if playwright is unavailable.
    Auto-installs chromium on first use if needed.
    """
    global _browser_installed

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    if _browser_installed is False:
        return None

    data = {
        "page_load_ms": None,
        "js_errors": [],
        "resource_stats": {
            "total": 0,
            "failed": 0,
            "total_bytes": 0,
        },
        "interactive_elements": {
            "forms": 0,
            "buttons": 0,
            "inputs": 0,
            "links_internal": 0,
            "links_external": 0,
        },
        "link_health": {
            "checked": 0,
            "broken": 0,
            "broken_urls": [],
        },
        "error": None,
    }

    def _launch_browser(p):
        """Launch chromium, auto-installing on first failure."""
        global _browser_installed
        if _browser_installed is True:
            return p.chromium.launch(headless=True)
        try:
            b = p.chromium.launch(headless=True)
            _browser_installed = True
            return b
        except Exception:
            if not _install_browser():
                _browser_installed = False
                return None
            b = p.chromium.launch(headless=True)
            _browser_installed = True
            return b

    try:
        with sync_playwright() as p:
            browser = _launch_browser(p)
            if browser is None:
                return None
            try:
                context = browser.new_context(
                    user_agent=_USER_AGENT,
                    viewport={"width": 1280, "height": 720},
                )
                page = context.new_page()

                # Collect JS console errors
                js_errors: list[str] = []
                page.on("console", lambda msg: (
                    js_errors.append(msg.text[:200])
                    if msg.type == "error" else None
                ))

                # Track resources with counters (not unbounded list)
                res_total = 0
                res_failed = 0
                res_bytes = 0

                def _on_response(response):
                    nonlocal res_total, res_failed, res_bytes
                    res_total += 1
                    if response.status >= 400:
                        res_failed += 1
                    try:
                        res_bytes += int(response.headers.get("content-length", 0))
                    except (ValueError, TypeError):
                        pass

                page.on("response", _on_response)

                # Navigate
                start = time.monotonic()
                try:
                    page.goto(url, wait_until="networkidle", timeout=30000)
                except Exception:
                    # Fallback: try with less strict wait
                    try:
                        start = time.monotonic()
                        page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    except Exception as e:
                        data["error"] = f"页面加载失败: {str(e)[:200]}"
                        return data

                load_ms = int((time.monotonic() - start) * 1000)
                data["page_load_ms"] = load_ms
                data["js_errors"] = js_errors[:20]

                # Resource stats
                data["resource_stats"] = {
                    "total": res_total,
                    "failed": res_failed,
                    "total_bytes": res_bytes,
                }

                # Extract all hrefs in one CDP call (avoid N+1 round-trips)
                parsed_base = urlparse(url)
                all_hrefs: list[str] = []
                try:
                    all_hrefs = page.eval_on_selector_all(
                        "a[href]", "els => els.map(e => e.href)"
                    ) or []
                except Exception:
                    pass

                # Classify links
                internal_urls: list[str] = []
                external_count = 0
                for href in all_hrefs[:200]:
                    if not href or href.startswith("#") or href.startswith("javascript:"):
                        continue
                    full = urljoin(url, href)
                    if urlparse(full).netloc == parsed_base.netloc:
                        internal_urls.append(full)
                    else:
                        external_count += 1

                # Interactive elements
                try:
                    data["interactive_elements"]["forms"] = page.locator("form").count()
                    data["interactive_elements"]["buttons"] = page.locator(
                        "button, [role='button'], input[type='submit']"
                    ).count()
                    data["interactive_elements"]["inputs"] = page.locator(
                        "input:not([type='hidden']):not([type='submit']), textarea, select"
                    ).count()
                    data["interactive_elements"]["links_internal"] = len(internal_urls)
                    data["interactive_elements"]["links_external"] = external_count
                except Exception:
                    pass

                # Link health check (sample top-N internal links, concurrent)
                unique_internal = list(dict.fromkeys(internal_urls))[:10]
                if unique_internal:
                    try:
                        import httpx

                        def _check_link(link_url: str) -> bool:
                            """Returns True if broken."""
                            try:
                                with httpx.Client(
                                    follow_redirects=True,
                                    timeout=10.0,
                                    headers={"User-Agent": "funeralai-linkcheck/1.0"},
                                ) as client:
                                    resp = client.head(link_url)
                                    return resp.status_code >= 400
                            except Exception:
                                return True

                        with ThreadPoolExecutor(max_workers=5) as pool:
                            results = list(pool.map(_check_link, unique_internal))

                        broken_urls = [
                            u for u, is_broken in zip(unique_internal, results) if is_broken
                        ]
                        data["link_health"] = {
                            "checked": len(unique_internal),
                            "broken": len(broken_urls),
                            "broken_urls": broken_urls[:5],
                        }
                    except ImportError:
                        pass
                    except Exception:
                        pass

            finally:
                browser.close()

    except Exception as e:
        data["error"] = f"浏览器测试失败: {str(e)[:200]}"

    return data


def _detect_web_red_flags(
    fetch_data: dict,
    browser_data: dict | None,
) -> list[str]:
    """Detect suspicious patterns from web inspection."""
    flags = []

    # HTTP-level flags
    if fetch_data.get("blocked"):
        flags.append("被反爬虫机制拦截，无法获取页面内容")

    status = fetch_data.get("status_code")
    if status and status >= 400:
        flags.append(f"HTTP 状态码 {status}，网站可能已下线或不可访问")

    if fetch_data.get("redirect_domain_changed"):
        flags.append(
            f"重定向到不同域名: {urlparse(fetch_data.get('final_url', '')).netloc}"
        )

    response_time = fetch_data.get("response_time_ms", 0)
    if response_time and response_time > 5000:
        flags.append(f"HTTP 响应时间过长: {response_time}ms")

    # Content flags
    content_len = fetch_data.get("content_length", 0)
    if content_len == 0 and not fetch_data.get("error"):
        flags.append("页面无实质内容（可能是纯营销页或 SPA 未渲染）")
    elif 0 < content_len < 200:
        flags.append(f"页面内容极少（仅 {content_len} 字符），可能是占位页")

    # Browser-level flags
    if browser_data and not browser_data.get("error"):
        load_ms = browser_data.get("page_load_ms", 0)
        if load_ms and load_ms > 5000:
            flags.append(f"页面加载时间过长: {load_ms}ms")

        js_errors = browser_data.get("js_errors", [])
        if len(js_errors) > 5:
            flags.append(f"大量 JS 控制台错误: {len(js_errors)} 个")

        res_stats = browser_data.get("resource_stats", {})
        if res_stats.get("failed", 0) > 3:
            flags.append(f"多个资源加载失败: {res_stats['failed']} 个")

        interactive = browser_data.get("interactive_elements", {})
        total_interactive = (
            interactive.get("forms", 0)
            + interactive.get("buttons", 0)
            + interactive.get("inputs", 0)
        )
        if total_interactive == 0:
            flags.append("无交互元素（无表单、按钮或输入框）——可能不是真正的产品页")

        link_health = browser_data.get("link_health", {})
        if link_health.get("checked", 0) > 0:
            broken_ratio = link_health["broken"] / link_health["checked"]
            if broken_ratio > 0.3:
                flags.append(
                    f"内部链接健康度差: {link_health['broken']}/{link_health['checked']} 个链接不可访问"
                )
    elif browser_data and browser_data.get("error"):
        flags.append(f"浏览器体验测试失败: {browser_data['error'][:100]}")

    return flags


def _build_web_report(
    url: str,
    fetch_data: dict,
    browser_data: dict | None,
    red_flags: list[str],
) -> str:
    """Generate the structured markdown inspection report for a web page."""
    status = fetch_data.get("status_code", "N/A")
    response_time = fetch_data.get("response_time_ms", "N/A")
    title = fetch_data.get("title") or "无标题"
    description = fetch_data.get("description") or "无描述"

    report = f"""## 产品体验实查报告（自动生成）

### 基本信息
- URL: {url}
- 最终 URL: {fetch_data.get('final_url', url)}
- HTTP 状态码: {status}
- 响应时间: {response_time}ms
- 页面标题: {title}
- 页面描述: {description}
- 内容长度: {fetch_data.get('content_length', 0)} 字符"""

    if fetch_data.get("redirected"):
        report += f"\n- 发生重定向: 是"
        if fetch_data.get("redirect_domain_changed"):
            report += f"（跨域）"

    if fetch_data.get("blocked"):
        report += f"\n- 反爬虫拦截: 是"

    if fetch_data.get("error"):
        report += f"\n- 错误: {fetch_data['error']}"

    # Browser test results
    if browser_data and not browser_data.get("error"):
        report += "\n\n### 浏览器体验测试"
        report += f"\n- 页面加载时间: {browser_data.get('page_load_ms', 'N/A')}ms"

        # JS errors
        js_errors = browser_data.get("js_errors", [])
        if js_errors:
            report += f"\n- JS 控制台错误: {len(js_errors)} 个"
            for err in js_errors[:5]:
                report += f"\n  - {err}"
        else:
            report += "\n- JS 控制台错误: 无"

        # Resources
        res = browser_data.get("resource_stats", {})
        report += f"\n- 资源加载: 共 {res.get('total', 0)} 个"
        if res.get("failed", 0) > 0:
            report += f"，失败 {res['failed']} 个"
        total_kb = res.get("total_bytes", 0) / 1024
        if total_kb > 0:
            report += f"，总传输 ~{total_kb:.0f} KB"

        # Interactive elements
        ie = browser_data.get("interactive_elements", {})
        report += "\n\n### 交互元素"
        report += f"\n- 表单: {ie.get('forms', 0)}"
        report += f"\n- 按钮: {ie.get('buttons', 0)}"
        report += f"\n- 输入框: {ie.get('inputs', 0)}"
        report += f"\n- 内部链接: {ie.get('links_internal', 0)}"
        report += f"\n- 外部链接: {ie.get('links_external', 0)}"

        # Link health
        lh = browser_data.get("link_health", {})
        if lh.get("checked", 0) > 0:
            report += f"\n\n### 链接健康度"
            report += f"\n- 检查内部链接: {lh['checked']} 个"
            report += f"\n- 失效链接: {lh['broken']} 个"
            if lh.get("broken_urls"):
                for bu in lh["broken_urls"]:
                    report += f"\n  - {bu}"

    elif browser_data and browser_data.get("error"):
        report += f"\n\n### 浏览器体验测试\n- 失败: {browser_data['error']}"

    # Red flags
    if red_flags:
        report += "\n\n### 自动红旗"
        for flag in red_flags:
            report += f"\n- {flag}"

    return report


def inspect_web(url: str, no_browser: bool = False) -> tuple[dict, str, str]:
    """Inspect a web URL and return (inspection_data, page_content, report_markdown).

    inspection_data: raw structured data for JSON output
    page_content: extracted page text for LLM input
    report_markdown: formatted report for LLM input
    """
    from funeralai.analyzer import _progress

    # Phase 1: HTTP fetch + content extraction
    _progress(f"抓取 {url} ...")
    fetch_data = _fetch_and_extract(url)

    page_content = fetch_data.get("content_text", "")

    # Phase 2: Browser experience test (optional)
    browser_data = None
    if not no_browser:
        _progress("浏览器体验测试...")
        browser_data = _browser_probe(url)
        if browser_data is None:
            _progress("浏览器体验测试不可用，跳过")

    # Red flags
    red_flags = _detect_web_red_flags(fetch_data, browser_data)

    # Build report
    report = _build_web_report(url, fetch_data, browser_data, red_flags)

    # Structured data for JSON output
    inspection_data = {
        "url": url,
        "final_url": fetch_data.get("final_url", url),
        "status_code": fetch_data.get("status_code"),
        "response_time_ms": fetch_data.get("response_time_ms"),
        "title": fetch_data.get("title"),
        "description": fetch_data.get("description"),
        "content_length": fetch_data.get("content_length", 0),
        "content_extracted": fetch_data.get("content_extracted", True),
        "redirected": fetch_data.get("redirected", False),
        "redirect_domain_changed": fetch_data.get("redirect_domain_changed", False),
        "blocked": fetch_data.get("blocked", False),
        "browser_tested": browser_data is not None and not browser_data.get("error"),
        "browser": browser_data,
        "red_flags": red_flags,
        "no_browser": no_browser,
    }

    return inspection_data, page_content, report
