from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import new_id

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional runtime dependency
    pdfplumber = None


CASE_NO_RE = re.compile(r"[（(]?\d{4}[）)]?[\u4e00-\u9fa5A-Za-z0-9民执初终再申行.-]{2,30}号")
AMOUNT_RE = re.compile(r"(?:人民币)?([0-9][0-9,]*(?:\.\d+)?)(万?元)")
COMPANY_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9（）()]{2,40}(?:股份有限公司|有限责任公司|有限公司|公司)")
DATE_RE = re.compile(r"\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2}")
USCC_RE = re.compile(r"\b[0-9A-Z]{18}\b")
CAUSE_RE = re.compile(r"(?:案由[：:\s]*)?([\u4e00-\u9fa5]{2,16}(?:纠纷|争议|案))")
DEADLINE_RE = re.compile(r"(?:期限|履行期限|支付期限|限于|应于)([^。；;\n]{2,60}(?:日内|日前|之前|届满|\d{4}年\d{1,2}月\d{1,2}日))")
EXECUTION_BASIS_RE = re.compile(r"(?:执行依据|依据)[：:\s]*([^。；;\n]{4,80})")
PARTY_RE = re.compile(r"(?:申请执行人|被执行人|原告|被告|申请人|被申请人)[：:\s]*([^，。；;\n]{2,40})")


@dataclass
class ParsedDocument:
    markdown: str
    blocks: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    parse_status: str
    quality_summary: dict[str, Any]


class DocumentPipeline:
    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        pages = self._extract_pages(filename, content)
        blocks: list[dict[str, Any]] = []
        for page_no, text, bbox in pages:
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if part.strip()]
            if not paragraphs and text.strip():
                paragraphs = [text.strip()]
            for paragraph in paragraphs:
                confidence = self._confidence(paragraph)
                blocks.append(
                    {
                        "id": new_id("block"),
                        "page_no": page_no,
                        "block_type": "paragraph",
                        "text": paragraph,
                        "markdown": paragraph,
                        "bbox": bbox,
                        "confidence": confidence,
                        "review_status": "pending" if confidence < 0.8 else "confirmed",
                    }
                )
        if not blocks:
            blocks.append(
                {
                    "id": new_id("block"),
                    "page_no": 1,
                    "block_type": "paragraph",
                    "text": "未能识别出可读文本，请人工整理后上传。",
                    "markdown": "未能识别出可读文本，请人工整理后上传。",
                    "bbox": [0, 0, 0, 0],
                    "confidence": 0.2,
                    "review_status": "pending",
                }
            )
        markdown = "\n\n".join(block["markdown"] for block in blocks)
        entities = self._extract_entities(blocks)
        low_confidence = sum(1 for block in blocks if block["confidence"] < 0.8)
        return ParsedDocument(
            markdown=markdown,
            blocks=blocks,
            entities=entities,
            parse_status="review_required" if low_confidence else "done",
            quality_summary={
                "blocks_count": len(blocks),
                "low_confidence_blocks": low_confidence,
                "has_page_mapping": True,
                "extracted_entity_types": sorted({entity["entity_type"] for entity in entities}),
            },
        )

    def _extract_pages(self, filename: str, content: bytes) -> list[tuple[int, str, list[float]]]:
        name = filename.lower()
        if name.endswith(".pdf") and pdfplumber is not None:
            import io

            pages: list[tuple[int, str, list[float]]] = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for index, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    pages.append((index, text, [0, 0, float(page.width), float(page.height)]))
            return pages
        text = content.decode("utf-8", errors="replace")
        chunks = [chunk.strip() for chunk in re.split(r"\f|\n---page---\n", text) if chunk.strip()]
        return [(index, chunk, [0, 0, 595, 842]) for index, chunk in enumerate(chunks or [text], start=1)]

    def _confidence(self, text: str) -> float:
        if "�" in text or len(text.strip()) < 12:
            return 0.62
        if re.search(r"[A-Za-z0-9]{20,}", text):
            return 0.74
        return 0.91

    def _extract_entities(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for block in blocks:
            text = block["text"]
            patterns = [
                ("case_no", CASE_NO_RE, 0.88),
                ("company", COMPANY_RE, 0.82),
                ("date", DATE_RE, 0.8),
                ("unified_social_credit_code", USCC_RE, 0.9),
                ("cause_of_action", CAUSE_RE, 0.74),
                ("deadline", DEADLINE_RE, 0.78),
                ("execution_basis", EXECUTION_BASIS_RE, 0.76),
                ("party", PARTY_RE, 0.77),
            ]
            for entity_type, pattern, confidence in patterns:
                for match in pattern.finditer(text):
                    raw = match.group(1) if match.lastindex else match.group(0)
                    self._append_entity(entities, seen, entity_type, raw, raw, block, confidence)
            for match in AMOUNT_RE.finditer(text):
                raw = "".join(match.groups())
                self._append_entity(entities, seen, "amount", raw, raw, block, 0.84)
            if "法院" in text:
                line = next((line.strip() for line in text.splitlines() if "法院" in line), text[:80])
                self._append_entity(entities, seen, "court", line, line, block, 0.78)
        return entities

    def _append_entity(
        self,
        entities: list[dict[str, Any]],
        seen: set[tuple[str, str, str]],
        entity_type: str,
        raw_text: str,
        normalized_value: str,
        block: dict[str, Any],
        confidence: float,
    ) -> None:
        raw_text = raw_text.strip()
        if not raw_text:
            return
        key = (entity_type, raw_text, block["id"])
        if key in seen:
            return
        seen.add(key)
        entities.append(self._entity(entity_type, raw_text, normalized_value.strip(), block, confidence))

    def _entity(self, entity_type: str, raw_text: str, normalized_value: str, block: dict[str, Any], confidence: float) -> dict[str, Any]:
        return {
            "id": new_id("ent"),
            "object_type": "file",
            "object_id": "",
            "entity_type": entity_type,
            "raw_text": raw_text,
            "normalized_value": normalized_value,
            "source_ref": {
                "block_id": block["id"],
                "page_no": block["page_no"],
                "snippet": block["text"][:160],
                "bbox": block["bbox"],
            },
            "confidence": confidence,
        }