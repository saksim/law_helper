from __future__ import annotations

from html import escape
from typing import Any


def render_report_export(report: dict[str, Any], clues: list[dict[str, Any]], export_format: str) -> tuple[str, str, str]:
    title = report.get("title", "asset-clue-report")
    if export_format == "md":
        body = report.get("content_md", "")
        return body, "text/markdown; charset=utf-8", f"{title}.md"
    if export_format == "word":
        clue_rows = "".join(
            f"<li>{escape(clue.get('title', ''))} - {clue.get('actionability_score', '')} 分 - {escape((clue.get('source_refs') or [{}])[0].get('source_name', ''))}</li>"
            for clue in clues
        )
        html = f"""<!doctype html><html><head><meta charset='utf-8'><title>{escape(title)}</title></head><body><h1>{escape(title)}</h1><pre>{escape(report.get('content_md', ''))}</pre><h2>线索清单</h2><ul>{clue_rows}</ul></body></html>"""
        return html, "application/msword; charset=utf-8", f"{title}.doc"
    raise ValueError("unsupported_export_format")