from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

from .models import new_id
from .ocr import OCRService

try:
    import pdfplumber
except Exception:  # pragma: no cover - optional runtime dependency
    pdfplumber = None


CASE_NO_RE = re.compile(r"[（(]?\d{4}[）)]?[\u4e00-\u9fa5A-Za-z0-9民执初终再申行保财破-]{2,30}号")
AMOUNT_RE = re.compile(r"(?:人民币|金额|标的|欠款|本金|价款)[：:\s]*([0-9][0-9,]*(?:\.\d+)?)(万|元)?")
COMPANY_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9（）()]{2,40}(?:股份有限公司|有限责任公司|有限公司|公司)")
DATE_RE = re.compile(r"\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2}")
USCC_RE = re.compile(r"\b[0-9A-Z]{18}\b")
CAUSE_RE = re.compile(r"(?:案由[：:\s]*)?([\u4e00-\u9fa5]{2,20}(?:纠纷|争议|案))")
DEADLINE_RE = re.compile(r"(?:期限|履行期限|支付期限|限于|应于)([^。；;\n]{2,60}(?:日内|日前|之前|届满|\d{4}年\d{1,2}月\d{1,2}日))")
EXECUTION_BASIS_RE = re.compile(r"(?:执行依据|依据)[：:\s]*([^。；;\n]{4,80})")
PARTY_RE = re.compile(r"(?:申请执行人|被执行人|原告|被告|申请人|被申请人)[：:\s]*([^，。；;\n]{2,40})")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")


@dataclass
class ParsedDocument:
    markdown: str
    blocks: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    parse_status: str
    quality_summary: dict[str, Any]


class DocumentPipeline:
    def __init__(self) -> None:
        self.ocr = OCRService()

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        pages, extraction_summary = self._extract_pages(filename, content)
        blocks: list[dict[str, Any]] = []
        for page_no, text, bbox in pages:
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if part.strip()]
            if not paragraphs and text.strip():
                paragraphs = [text.strip()]
            for paragraph in paragraphs:
                confidence = self._confidence(paragraph, extraction_summary)
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
            ocr_status = extraction_summary.get("ocr_status") or "not_attempted"
            ocr_detail = extraction_summary.get("ocr_detail")
            review_text = f"未能识别出可读文本，OCR 状态：{ocr_status}。请人工整理后上传。"
            if ocr_detail:
                review_text = f"{review_text} {ocr_detail}"
            blocks.append(
                {
                    "id": new_id("block"),
                    "page_no": 1,
                    "block_type": "paragraph",
                    "text": review_text,
                    "markdown": review_text,
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
                **extraction_summary,
            },
        )

    def _extract_pages(self, filename: str, content: bytes) -> tuple[list[tuple[int, str, list[float]]], dict[str, Any]]:
        name = filename.lower()
        if name.endswith(".pdf"):
            pages = self._extract_pdf_text_pages(content)
            if any(text.strip() for _, text, _ in pages):
                return pages, {"text_extraction": "pdf_text", "ocr_attempted": False, "ocr_status": "not_needed", "verification_status": "untested"}
            ocr_result = self.ocr.extract_pages(filename, content)
            ocr_pages = [(page.page_no, page.text, page.bbox) for page in ocr_result.pages if page.text.strip()]
            return ocr_pages, self._ocr_summary(ocr_result, "ocr" if ocr_pages else "none")
        if name.endswith(IMAGE_EXTENSIONS):
            ocr_result = self.ocr.extract_pages(filename, content)
            ocr_pages = [(page.page_no, page.text, page.bbox) for page in ocr_result.pages if page.text.strip()]
            return ocr_pages, self._ocr_summary(ocr_result, "ocr" if ocr_pages else "none")
        text = content.decode("utf-8", errors="replace")
        chunks = [chunk.strip() for chunk in re.split(r"\f|\n---page---\n", text) if chunk.strip()]
        return [(index, chunk, [0, 0, 595, 842]) for index, chunk in enumerate(chunks or [text], start=1)], {
            "text_extraction": "plain_text",
            "ocr_attempted": False,
            "ocr_status": "not_needed",
            "verification_status": "untested",
        }

    def _extract_pdf_text_pages(self, content: bytes) -> list[tuple[int, str, list[float]]]:
        if pdfplumber is None:
            return []
        pages: list[tuple[int, str, list[float]]] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append((index, text, [0, 0, float(page.width), float(page.height)]))
        return pages

    def _ocr_summary(self, ocr_result: Any, text_extraction: str) -> dict[str, Any]:
        detail = ocr_result.detail or next((page.detail for page in ocr_result.pages if page.detail), None)
        return {
            "text_extraction": text_extraction,
            "ocr_attempted": True,
            "ocr_status": ocr_result.status,
            "ocr_provider": ocr_result.provider,
            "ocr_detail": detail,
            "verification_status": "untested",
        }

    def _confidence(self, text: str, extraction_summary: dict[str, Any] | None = None) -> float:
        extraction_summary = extraction_summary or {}
        if "�" in text or "锟" in text or len(text.strip()) < 12:
            return 0.62
        if extraction_summary.get("text_extraction") == "ocr":
            return 0.72
        if re.search(r"[A-Za-z0-9]{20,}", text):
            return 0.74
        return 0.91

    def _extract_entities(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
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
        for block in blocks:
            text = block["text"]
            for entity_type, pattern, confidence in patterns:
                for match in pattern.finditer(text):
                    raw = match.group(1) if match.lastindex else match.group(0)
                    self._append_entity(entities, seen, entity_type, raw, raw, block, confidence)
            for match in AMOUNT_RE.finditer(text):
                raw = "".join(value or "" for value in match.groups())
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