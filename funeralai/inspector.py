"""GitHub repository inspector: API metadata + local code inspection + report generation.

Produces a structured inspection report that feeds into the LLM analysis pipeline,
giving the judge real evidence instead of just README marketing text.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# Extensions considered "real code" vs documentation/config/template
_CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".java",
    ".kt", ".swift", ".c", ".cpp", ".h", ".hpp", ".cs", ".php", ".lua",
    ".zig", ".ex", ".exs", ".clj", ".scala", ".r", ".R", ".jl",
    ".sh", ".bash", ".zsh", ".fish", ".pl", ".pm",
}
_DOC_EXTS = {".md", ".txt", ".rst", ".adoc", ".org", ".wiki"}
_CONFIG_EXTS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".env", ".properties", ".lock",
}
_TEMPLATE_EXTS = {
    ".tmpl", ".ejs", ".hbs", ".mustache", ".jinja", ".jinja2",
    ".j2", ".liquid", ".njk", ".pug", ".erb",
}

GITHUB_URL_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")

# Directories to skip when walking
_SKIP_DIRS = {
    ".git", "node_modules", "vendor", "venv", ".venv", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", ".next",
    "target", ".gradle", "Pods",
}


def parse_github_url(url: str) -> tuple[str, str] | None:
    """Parse a GitHub URL and return (owner, repo) or None."""
    match = GITHUB_URL_RE.match(url)
    if match:
        return match.group(1), match.group(2)
    return None


def _check_gh() -> None:
    """Verify gh CLI is installed and authenticated."""
    if not shutil.which("gh"):
        raise RuntimeError(
            "需要安装 GitHub CLI (gh)。\n"
            "  macOS: brew install gh\n"
            "  其他: https://cli.github.com/"
        )
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "GitHub CLI 未认证。请运行:\n"
            "  gh auth login"
        )


def _gh_api(endpoint: str) -> dict | list | None:
    """Call GitHub API via gh CLI. Returns parsed JSON or None on failure."""
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def _fetch_api_data(owner: str, repo: str) -> dict:
    """Fetch repository metadata from GitHub API."""
    base = f"repos/{owner}/{repo}"

    repo_data = _gh_api(base) or {}
    languages = _gh_api(f"{base}/languages") or {}
    contributors = _gh_api(f"{base}/contributors?per_page=10") or []
    commits = _gh_api(f"{base}/commits?per_page=30") or []

    # README
    readme_data = _gh_api(f"{base}/readme")
    readme_text = ""
    if readme_data and "content" in readme_data:
        try:
            readme_text = base64.b64decode(readme_data["content"]).decode("utf-8")
        except Exception:
            readme_text = "(README 解码失败)"
    elif readme_data is None:
        readme_text = "(README 不存在)"

    return {
        "owner": owner,
        "repo": repo,
        "stars": repo_data.get("stargazers_count", 0),
        "forks": repo_data.get("forks_count", 0),
        "open_issues": repo_data.get("open_issues_count", 0),
        "license": (repo_data.get("license") or {}).get("spdx_id", "无"),
        "created_at": repo_data.get("created_at", ""),
        "pushed_at": repo_data.get("pushed_at", ""),
        "size_kb": repo_data.get("size", 0),
        "description": repo_data.get("description", ""),
        "languages": languages,
        "contributors": [
            {"login": c.get("login", "?"), "contributions": c.get("contributions", 0)}
            for c in (contributors if isinstance(contributors, list) else [])
        ],
        "recent_commits": len(commits) if isinstance(commits, list) else 0,
        "readme_text": readme_text,
    }


def _loc_totals(loc: dict) -> dict:
    """Compute LOC totals from a loc breakdown dict. Returns precomputed stats."""
    code = sum(loc.get("code", {}).values())
    doc = sum(loc.get("doc", {}).values())
    template = sum(loc.get("template", {}).values())
    config = sum(loc.get("config", {}).values())
    other = sum(loc.get("other", {}).values())
    total = code + doc + template + config + other
    return {
        "code": code,
        "doc": doc,
        "template": template,
        "config": config,
        "other": other,
        "total": total,
        "code_ratio": (code / total * 100) if total > 0 else 0,
    }


def _walk_tree(path: Path) -> tuple[dict, dict, list[tuple[Path, int]], int]:
    """Single-pass tree walk. Returns (loc, tests, code_candidates, total_files).

    Consolidates what was previously 3 separate os.walk() calls:
    LOC counting, test detection, and code sampling candidate collection.
    """
    loc = {"code": {}, "doc": {}, "config": {}, "template": {}, "other": {}}
    total_files = 0
    test_dirs: list[str] = []
    test_file_count = 0
    code_candidates: list[tuple[Path, int]] = []

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        rel = Path(root).relative_to(path)

        # Test directory detection
        for d in dirs:
            if d.lower() in ("tests", "test", "__tests__", "spec", "specs"):
                test_dirs.append(str(rel / d))

        for fname in files:
            fpath = Path(root) / fname
            ext = fpath.suffix.lower()

            # Test file detection (before ext filter — test files may have any ext)
            fl = fname.lower()
            if (
                fl.startswith("test_") or fl.endswith("_test.py")
                or ".test." in fl or ".spec." in fl
                or fl.endswith("_test.go")
            ):
                test_file_count += 1

            if not ext:
                continue

            total_files += 1

            # Categorize
            if ext in _CODE_EXTS:
                cat = "code"
            elif ext in _DOC_EXTS:
                cat = "doc"
            elif ext in _CONFIG_EXTS:
                cat = "config"
            elif ext in _TEMPLATE_EXTS:
                cat = "template"
            else:
                cat = "other"

            # Count lines
            try:
                lines = len(fpath.read_text(encoding="utf-8", errors="ignore").splitlines())
            except (OSError, UnicodeDecodeError):
                continue

            loc[cat][ext] = loc[cat].get(ext, 0) + lines

            # Code sampling candidates (collect during walk, select later)
            if cat == "code":
                try:
                    size = fpath.stat().st_size
                    if 200 < size < 50000:
                        code_candidates.append((fpath, size))
                except OSError:
                    pass

    tests = {
        "has_tests": bool(test_dirs or test_file_count > 0),
        "test_dirs": test_dirs[:10],
        "test_file_count": test_file_count,
    }
    return loc, tests, code_candidates, total_files


def _detect_build(path: Path) -> dict:
    """Detect build systems and CI configuration."""
    checks = {
        "package.json": "Node.js (npm/yarn/bun)",
        "pyproject.toml": "Python (pyproject)",
        "setup.py": "Python (setup.py)",
        "Cargo.toml": "Rust (Cargo)",
        "go.mod": "Go modules",
        "Makefile": "Make",
        "CMakeLists.txt": "CMake",
        "Dockerfile": "Docker",
        "docker-compose.yml": "Docker Compose",
        "docker-compose.yaml": "Docker Compose",
    }
    ci_checks = {
        ".github/workflows": "GitHub Actions",
        ".gitlab-ci.yml": "GitLab CI",
        ".circleci": "CircleCI",
        "Jenkinsfile": "Jenkins",
        ".travis.yml": "Travis CI",
    }

    build_systems = []
    for fname, label in checks.items():
        if (path / fname).exists():
            build_systems.append(label)

    ci_systems = []
    for fname, label in ci_checks.items():
        if (path / fname).exists():
            ci_systems.append(label)

    return {
        "build_systems": build_systems,
        "ci_systems": ci_systems,
    }


def _select_samples(
    code_candidates: list[tuple[Path, int]],
    base_path: Path,
    max_files: int = 5,
    max_lines: int = 80,
) -> list[dict]:
    """Select representative code files from pre-collected candidates."""
    # Sort by size descending — larger files tend to be more substantive
    code_candidates.sort(key=lambda x: -x[1])

    # Pick from different directories for diversity
    seen_dirs: set[str] = set()
    picked: list[dict] = []
    for fpath, _ in code_candidates:
        parent = str(fpath.parent.relative_to(base_path))
        if parent in seen_dirs:
            continue
        seen_dirs.add(parent)
        try:
            lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()[:max_lines]
            picked.append({
                "path": str(fpath.relative_to(base_path)),
                "lines": len(lines),
                "content": "\n".join(lines),
            })
        except (OSError, UnicodeDecodeError):
            continue
        if len(picked) >= max_files:
            break

    return picked


def _detect_red_flags(
    api_data: dict,
    totals: dict,
    tests: dict,
    total_files: int = 0,
) -> list[str]:
    """Automatically flag suspicious patterns."""
    flags = []

    # Code ratio
    if totals["total"] > 0 and totals["code_ratio"] < 30:
        flags.append(
            f"代码占比仅 {totals['code_ratio']:.0f}%，大部分内容是文档/模板/配置"
        )

    # No tests
    if not tests.get("has_tests"):
        flags.append("未发现测试文件或测试目录")

    # Single contributor dominance
    contributors = api_data.get("contributors", [])
    if len(contributors) >= 2:
        total_commits = sum(c["contributions"] for c in contributors)
        if total_commits > 0 and contributors[0]["contributions"] / total_commits > 0.90:
            top = contributors[0]["login"]
            pct = contributors[0]["contributions"] / total_commits
            flags.append(f"单一贡献者主导: {top} 占 {pct:.0%} 提交")
    elif len(contributors) == 1:
        flags.append(f"仅有一个贡献者: {contributors[0]['login']}")

    # README much longer than code
    readme_lines = len(api_data.get("readme_text", "").splitlines())
    if readme_lines > 200 and totals["code"] > 0 and readme_lines > totals["code"] * 0.5:
        flags.append(
            f"README ({readme_lines} 行) 相对代码量 ({totals['code']} 行) 过长"
        )

    # Very few files
    if total_files > 0 and total_files < 10:
        flags.append(f"文件数量极少 ({total_files} 个)")

    return flags


def format_languages(languages: dict) -> str:
    """Format language breakdown as a readable string."""
    if not languages:
        return "无数据"
    total = sum(languages.values())
    if total == 0:
        return "无数据"
    parts = []
    for lang, bytes_ in sorted(languages.items(), key=lambda x: -x[1]):
        pct = bytes_ / total * 100
        if pct >= 1:
            parts.append(f"{lang} ({pct:.0f}%)")
    return " | ".join(parts) if parts else "无数据"


def _format_loc_breakdown(loc: dict) -> str:
    """Format LOC breakdown as readable text."""
    lines = []
    for cat, label in [("code", "代码"), ("doc", "文档"), ("template", "模板"), ("config", "配置"), ("other", "其他")]:
        total = sum(loc.get(cat, {}).values())
        if total > 0:
            top_exts = sorted(loc[cat].items(), key=lambda x: -x[1])[:5]
            ext_str = ", ".join(f"{e}({n})" for e, n in top_exts)
            lines.append(f"  - {label}: ~{total:,} 行 ({ext_str})")
    return "\n".join(lines)


def _build_report(api_data: dict, loc: dict, totals: dict, tests: dict, build: dict, samples: list[dict], red_flags: list[str], total_files: int = 0) -> str:
    """Generate the structured markdown inspection report."""
    owner = api_data["owner"]
    repo = api_data["repo"]
    stars = api_data.get("stars", 0)
    forks = api_data.get("forks", 0)

    contributors = api_data.get("contributors", [])
    contrib_str = f"{len(contributors)} 人"
    if contributors:
        total_c = sum(c["contributions"] for c in contributors)
        if total_c > 0:
            top = contributors[0]
            pct = top["contributions"] / total_c * 100
            contrib_str += f" ({top['login']} 占 {pct:.0f}% 提交)"

    report = f"""## 技术实查报告（自动生成）

### 基本信息
- 仓库: {owner}/{repo} | Stars: {stars:,} | Forks: {forks:,}
- 描述: {api_data.get('description', '无')}
- 主语言: {format_languages(api_data.get('languages', {}))}
- 贡献者: {contrib_str}
- 最近提交数 (API 返回): {api_data.get('recent_commits', 0)} 次
- 创建时间: {api_data.get('created_at', '?')} | 最后推送: {api_data.get('pushed_at', '?')}
- License: {api_data.get('license', '无')}

### 代码实况
- 总文件: {total_files} | 总行数: ~{totals['total']:,}
- 实际代码行: ~{totals['code']:,} ({totals['code_ratio']:.0f}%) | 文档: ~{totals['doc']:,} | 模板: ~{totals['template']:,} | 配置: ~{totals['config']:,}
- 代码占比: {totals['code_ratio']:.0f}%
{_format_loc_breakdown(loc)}

### 质量信号
- 测试: {'✓ ' + f"发现 {tests['test_file_count']} 个测试文件" if tests.get('has_tests') else '❌ 未发现测试文件'}"""

    if tests.get("test_dirs"):
        report += f"\n  - 测试目录: {', '.join(tests['test_dirs'][:5])}"

    report += f"""
- CI: {'✓ ' + ', '.join(build.get('ci_systems', [])) if build.get('ci_systems') else '❌ 未发现 CI 配置'}
- 构建系统: {', '.join(build.get('build_systems', [])) if build.get('build_systems') else '未发现'}"""

    if samples:
        report += "\n\n### 代码采样\n"
        for s in samples:
            report += f"\n**{s['path']}** (前 {s['lines']} 行):\n```\n{s['content']}\n```\n"

    if red_flags:
        report += "\n### 自动红旗\n"
        for flag in red_flags:
            report += f"- {flag}\n"

    return report


def inspect_github(url: str, no_clone: bool = False) -> tuple[dict, str, str]:
    """Inspect a GitHub repository and return (inspection_data, readme_text, report_markdown).

    inspection_data: raw structured data for JSON output
    readme_text: README content for LLM input
    report_markdown: formatted report for LLM input
    """
    from funeralai.analyzer import _progress

    parsed = parse_github_url(url)
    if not parsed:
        raise ValueError(f"无效的 GitHub URL: {url}")

    owner, repo = parsed

    _check_gh()

    # Step 1: API metadata
    _progress(f"获取 {owner}/{repo} 元数据...")
    api_data = _fetch_api_data(owner, repo)

    readme_text = api_data.pop("readme_text", "(README 不存在)")

    # Check repo size
    size_mb = api_data.get("size_kb", 0) / 1024
    if size_mb > 500 and not no_clone:
        _progress(f"警告: 仓库较大 ({size_mb:.0f} MB)，建议使用 --no-clone")

    loc = {}
    tests = {"has_tests": False, "test_dirs": [], "test_file_count": 0}
    build = {"build_systems": [], "ci_systems": []}
    samples = []
    red_flags = []
    total_files = 0
    totals = _loc_totals(loc)

    # Step 2: Clone + local inspection
    if not no_clone:
        tmpdir = tempfile.mkdtemp(prefix="funeralai_")
        clone_path = Path(tmpdir) / repo
        try:
            _progress("克隆仓库 (shallow)...")
            subprocess.run(
                ["git", "clone", "--depth", "1", "--quiet", url, str(clone_path)],
                capture_output=True, text=True, timeout=60,
            )

            if clone_path.exists():
                _progress("分析代码结构...")
                loc, tests, code_candidates, total_files = _walk_tree(clone_path)
                build = _detect_build(clone_path)
                samples = _select_samples(code_candidates, clone_path)
                totals = _loc_totals(loc)
                red_flags = _detect_red_flags(api_data, totals, tests, total_files)
        except subprocess.TimeoutExpired:
            _progress("克隆超时，降级为仅 API 模式")
            red_flags.append("仓库克隆超时 (>60s)，无法进行本地代码检查")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    else:
        # API-only mode: limited red flags
        red_flags = _detect_red_flags(api_data, totals, tests, total_files)

    # Step 3: Build report
    report = _build_report(api_data, loc, totals, tests, build, samples, red_flags, total_files)

    # Structured data for JSON output
    inspection_data = {
        "url": url,
        "owner": owner,
        "repo": repo,
        "api": api_data,
        "loc": loc,
        "totals": totals,
        "total_files": total_files,
        "tests": tests,
        "build": build,
        "red_flags": red_flags,
        "no_clone": no_clone,
    }

    return inspection_data, readme_text, report
