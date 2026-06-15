from __future__ import annotations

from html import escape
from typing import Any
from unicodedata import east_asian_width

ExportBody = str | bytes

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN_X = 50
MARGIN_TOP = 54
MARGIN_BOTTOM = 52
FONT_SIZE = 11
LEADING = 16
MAX_TEXT_WIDTH = 62


def render_report_export(report: dict[str, Any], clues: list[dict[str, Any]], export_format: str, watermark: str | None = None) -> tuple[ExportBody, str, str]:
    title = report.get("title", "asset-clue-report")
    content_md = report.get("content_md", "")
    if watermark:
        content_md = f"{content_md}\n\n---\n\n{watermark}"
    if export_format == "md":
        return content_md, "text/markdown; charset=utf-8", f"{title}.md"
    if export_format == "word":
        clue_rows = "".join(
            f"<li>{escape(clue.get('title', ''))} - {clue.get('actionability_score', '')} 分 - {escape((clue.get('source_refs') or [{}])[0].get('source_name', ''))}</li>"
            for clue in clues
        )
        watermark_html = f"<p><strong>导出水印</strong><br>{escape(watermark)}</p>" if watermark else ""
        html = f"""<!doctype html><html><head><meta charset='utf-8'><title>{escape(title)}</title></head><body><h1>{escape(title)}</h1><pre>{escape(content_md)}</pre><h2>线索清单</h2><ul>{clue_rows}</ul>{watermark_html}</body></html>"""
        return html, "application/msword; charset=utf-8", f"{title}.doc"
    if export_format == "pdf":
        body = render_pdf_report(title, content_md, clues, watermark)
        return body, "application/pdf", f"{title}.pdf"
    raise ValueError("unsupported_export_format")


def render_pdf_report(title: str, content_md: str, clues: list[dict[str, Any]], watermark: str | None = None) -> bytes:
    lines = [title, ""]
    lines.extend(markdown_to_pdf_lines(content_md))
    if clues:
        lines.extend(["", "线索清单"])
        for clue in clues:
            source = (clue.get("source_refs") or [{}])[0].get("source_name", "")
            lines.append(f"- {clue.get('title', '')} | 评分 {clue.get('actionability_score', '')} | 来源 {source}")
    lines.extend(["", "导出说明：本 PDF 由系统按报告内容生成，报告发布前仍需律师复核。"])
    wrapped = wrap_lines(lines)
    streams = paginate_lines(wrapped)
    return build_pdf(streams)


def markdown_to_pdf_lines(content_md: str) -> list[str]:
    rows: list[str] = []
    for raw in content_md.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            rows.append("")
            continue
        if line.startswith("###"):
            rows.append(line.lstrip("# "))
        elif line.startswith("##"):
            rows.extend(["", line.lstrip("# ")])
        elif line.startswith("#"):
            rows.extend(["", line.lstrip("# ")])
        else:
            rows.append(line)
    return rows


def wrap_lines(lines: list[str]) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if display_width(line) <= MAX_TEXT_WIDTH:
            wrapped.append(line)
            continue
        current = ""
        current_width = 0
        for char in line:
            width = char_width(char)
            if current and current_width + width > MAX_TEXT_WIDTH:
                wrapped.append(current)
                current = char
                current_width = width
            else:
                current += char
                current_width += width
        if current:
            wrapped.append(current)
    return wrapped


def paginate_lines(lines: list[str]) -> list[list[str]]:
    max_lines = max(1, int((PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM) / LEADING))
    pages: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if len(current) >= max_lines:
            pages.append(current)
            current = []
        current.append(line)
    if current or not pages:
        pages.append(current)
    return pages


def display_width(text: str) -> int:
    return sum(char_width(char) for char in text)


def char_width(char: str) -> int:
    return 2 if east_asian_width(char) in {"W", "F"} else 1


def build_pdf(pages: list[list[str]]) -> bytes:
    objects: dict[int, bytes] = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[3] = b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [4 0 R] >>"
    objects[4] = b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> /DW 1000 >>"

    kids: list[str] = []
    next_id = 5
    for page_lines in pages:
        stream = render_page_stream(page_lines)
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        objects[content_id] = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        kids.append(f"{page_id} 0 R")

    objects[2] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode("ascii")
    return assemble_pdf(objects)


def render_page_stream(lines: list[str]) -> bytes:
    commands = [f"BT /F1 {FONT_SIZE} Tf {MARGIN_X} {PAGE_HEIGHT - MARGIN_TOP} Td {LEADING} TL"]
    first = True
    for line in lines:
        if not first:
            commands.append("T*")
        first = False
        if line:
            commands.append(f"<{line.encode('utf-16-be').hex().upper()}> Tj")
    commands.append("ET")
    return "\n".join(commands).encode("ascii")


def assemble_pdf(objects: dict[int, bytes]) -> bytes:
    output = bytearray(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offsets = {0: 0}
    for object_id in sorted(objects):
        offsets[object_id] = len(output)
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(objects[object_id])
        output.extend(b"\nendobj\n")
    startxref = len(output)
    max_id = max(objects)
    output.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for object_id in range(1, max_id + 1):
        output.extend(f"{offsets[object_id]:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode("ascii"))
    return bytes(output)
