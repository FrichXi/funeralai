"""File reader supporting Markdown, plain text, and PDF."""

from __future__ import annotations

from pathlib import Path


def read_file(path: str) -> str:
    """Read a file and return its text content.

    Supports .md, .txt (UTF-8 text) and .pdf (via pymupdf/fitz).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = p.suffix.lower()

    if suffix in (".md", ".txt", ""):
        return p.read_text(encoding="utf-8")

    if suffix == ".pdf":
        return _read_pdf(p)

    # Fallback: try reading as text
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError(
            f"无法读取文件 {path}，不支持的格式: {suffix}\n"
            "支持的格式: .md, .txt, .pdf"
        )


def _read_pdf(path: Path) -> str:
    """Extract text from a PDF file using pymupdf."""
    try:
        import fitz  # pymupdf
    except ImportError:
        raise ImportError(
            "读取 PDF 需要安装 pymupdf:\n"
            "  pip install pymupdf"
        )

    doc = fitz.open(str(path))
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()

    if not pages:
        raise ValueError(f"PDF 文件为空或无法提取文本: {path}")

    return "\n\n".join(pages)
