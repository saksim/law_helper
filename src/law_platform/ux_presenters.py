from __future__ import annotations

from typing import Any


MOJIBAKE_MARKERS = ("�", "锛", "鏂", "鎵", "绾", "寰", "鐩", "妗", "杞", "浠", "涓", "鍏", "璧")


def has_broken_text(value: Any) -> bool:
    text = str(value or "")
    return any(marker in text for marker in MOJIBAKE_MARKERS)


def clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or has_broken_text(text):
        return fallback
    return text


def risk_label(value: Any) -> str:
    return {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(str(value or "").lower(), "未评估")


def stage_label(value: Any) -> str:
    return {
        "execution": "执行中",
        "pre_litigation": "诉前准备",
        "litigation": "审理中",
        "closed": "已结案",
    }.get(str(value or "").lower(), clean_text(value, "执行中"))


def importance_from_score(score: Any) -> str:
    try:
        value = int(score or 0)
    except Exception:
        value = 0
    if value >= 85:
        return "critical"
    if value >= 70:
        return "high"
    if value >= 50:
        return "medium"
    return "low"


def importance_label(value: Any, score: Any = None) -> str:
    raw = str(value or importance_from_score(score)).lower()
    return {
        "critical": "重点线索",
        "high": "高价值",
        "medium": "待核验",
        "low": "低优先级",
    }.get(raw, "待核验")


def review_status_label(value: Any) -> str:
    return {
        "pending": "待确认",
        "confirmed": "已确认",
        "rejected": "已忽略",
        "task_created": "已转任务",
        "review_required": "需复核",
    }.get(str(value or "").lower(), "待确认")


def action_status_label(value: Any) -> str:
    return {
        "unread": "待处理",
        "acknowledged": "已确认",
        "ignored": "已忽略",
        "task_created": "已转任务",
    }.get(str(value or "").lower(), "待处理")


def report_status_label(value: Any) -> str:
    return {
        "review_required": "待律师确认",
        "confirmed": "已确认",
        "draft": "草稿",
        "failed": "生成失败",
    }.get(str(value or "").lower(), "待律师确认")


def file_status_label(parse_status: Any, quality_summary: dict[str, Any] | None = None) -> str:
    status = str(parse_status or "").lower()
    quality_summary = quality_summary or {}
    if status in {"parse_pending", "pending", "running"}:
        return "正在整理材料"
    if status in {"review_required", "low_confidence"} or quality_summary.get("low_confidence_blocks"):
        return "有内容需要校对"
    if status in {"done", "extract_done", "completed"}:
        return "要素摘要已生成"
    if status == "failed":
        return "材料整理失败，可稍后重试或人工整理"
    return "材料已接收"


def event_type_label(value: Any) -> str:
    return {
        "new_execution": "执行动态",
        "new_auction": "拍卖动态",
        "equity_change": "股权变化",
        "new_company": "工商动态",
    }.get(str(value or "").lower(), "监控动态")


def clue_kind_label(clue_type: Any) -> str:
    return {
        "auction": "司法拍卖",
        "execution": "执行公开信息",
        "equity": "股权与关联主体",
        "company": "工商信息",
        "related_subject": "关联主体",
    }.get(str(clue_type or "").lower(), "资产线索")


def clue_title(clue: dict[str, Any], subject: dict[str, Any] | None = None) -> str:
    subject_name = clean_text((subject or {}).get("name"), "相关主体")
    kind = str(clue.get("clue_type") or "").lower()
    fallback = {
        "auction": f"{subject_name} 有司法拍卖线索",
        "execution": f"{subject_name} 有执行公开信息",
        "equity": f"{subject_name} 有股权或关联主体线索",
        "company": f"{subject_name} 有工商变更线索",
        "related_subject": f"{subject_name} 有关联主体线索",
    }.get(kind, f"{subject_name} 有待核验资产线索")
    return clean_text(clue.get("title"), fallback)


def clue_why(clue: dict[str, Any]) -> str:
    kind = str(clue.get("clue_type") or "").lower()
    fallback = {
        "auction": "可能直接对应可处置资产，需要尽快核验权属、处置阶段和是否可参与分配。",
        "execution": "可能影响并案、追加调查或回款路径，需要判断与本案债权的关联性。",
        "equity": "可能指向可追加的股权、对外投资或关联主体，需要核验是否具备执行价值。",
        "company": "可能帮助定位股权、投资、负责人或关联主体变化，为后续调查提供入口。",
        "related_subject": "可能指向可追加调查的关联主体，需要确认关系强度和执行价值。",
    }.get(kind, "该线索可能影响执行回款路径，需要律师确认真实性、关联性和可操作性。")
    return clean_text(clue.get("description"), fallback)


def recommended_action(clue: dict[str, Any]) -> str:
    kind = str(clue.get("clue_type") or "").lower()
    fallback = {
        "auction": "核验拍卖资产权属、处置阶段、优先受偿情况，并判断是否申请参与分配。",
        "execution": "核验新增执行信息与本案主体、债权金额和执行法院的关联性。",
        "equity": "核验股权结构、对外投资和关联主体，判断是否追加调查或采取保全措施。",
        "company": "核验工商变更、股东和高管信息，筛选可继续追查的主体。",
        "related_subject": "核验主体关系、财产线索和可执行价值，必要时转为调查任务。",
    }.get(kind, "核验来源、主体身份、权属状态和可执行价值后再采取下一步动作。")
    return clean_text(clue.get("recommended_action"), fallback)


def verification_items(clue: dict[str, Any]) -> list[str]:
    base = ["核对主体是否与本案相关", "核对来源页面和发布时间", "确认是否存在可执行价值"]
    kind = str(clue.get("clue_type") or "").lower()
    extras = {
        "auction": ["确认资产权属和拍卖阶段", "确认是否可申请参与分配"],
        "execution": ["确认案号、法院和金额", "判断是否需要并案或追加调查"],
        "equity": ["确认持股比例和出资状态", "判断是否存在可追加主体"],
        "company": ["确认股东、高管和对外投资变化", "筛选后续调查入口"],
    }.get(kind, ["确认线索真实性和行动成本"])
    return base + extras


def present_source_ref(ref: dict[str, Any] | None) -> dict[str, Any]:
    ref = ref or {}
    return {
        "source_name": clean_text(ref.get("source_name"), "已授权来源"),
        "source_url": ref.get("source_url"),
        "source_time": clean_text(ref.get("source_time") or ref.get("fetched_at"), "时间待核验"),
        "snippet": clean_text(ref.get("snippet"), "来源摘要待核验"),
    }


def present_clue(clue: dict[str, Any], subject: dict[str, Any] | None = None) -> dict[str, Any]:
    score = clue.get("actionability_score") or 0
    importance = importance_from_score(score)
    source_refs = [present_source_ref(ref) for ref in clue.get("source_refs", [])]
    try:
        confidence_value = float(clue.get("confidence") or 0)
    except Exception:
        confidence_value = 0.0
    return {
        "id": clue["id"],
        "case_id": clue.get("case_id"),
        "subject_id": clue.get("subject_id"),
        "subject_name": clean_text((subject or {}).get("name"), "相关主体"),
        "title": clue_title(clue, subject),
        "kind": clue_kind_label(clue.get("clue_type")),
        "importance": importance,
        "importance_label": importance_label(importance, score),
        "score": score,
        "why_important": clue_why(clue),
        "recommended_action": recommended_action(clue),
        "verification_items": verification_items(clue),
        "source_refs": source_refs,
        "source_summary": "；".join(f"{ref['source_name']} · {ref['source_time']}" for ref in source_refs) or "来源待补充",
        "review_status": clue.get("review_status", "pending"),
        "review_status_label": review_status_label(clue.get("review_status")),
        "confidence_label": "需重点核验" if confidence_value and confidence_value < 0.75 else "可作为待确认线索",
        "estimated_value": clean_text(clue.get("estimated_value"), "金额待核验"),
        "mobile_url": f"/mobile/clues/{clue['id']}",
        "desktop_restore_url": f"/?case_id={clue.get('case_id')}&tab=clues&clue_id={clue['id']}",
        "next_action_url": f"/api/asset-clues/{clue['id']}/review",
        "created_at": clue.get("created_at"),
    }


def present_file(file: dict[str, Any], blocks: list[dict[str, Any]], entities: list[dict[str, Any]]) -> dict[str, Any]:
    low_confidence = [
        block
        for block in blocks
        if float(block.get("confidence") or 1) < 0.8 or block.get("review_status") == "pending"
    ]
    dates = [entity for entity in entities if entity.get("entity_type") in {"date", "deadline"}]
    return {
        "id": file["id"],
        "case_id": file.get("case_id"),
        "name": clean_text(file.get("original_name"), "未命名材料"),
        "status": file.get("parse_status"),
        "status_label": file_status_label(file.get("parse_status"), file.get("quality_summary")),
        "sensitivity_level": file.get("sensitivity_level"),
        "source_channel": clean_text(file.get("source_channel"), "网页端上传"),
        "low_confidence_count": len(low_confidence),
        "key_dates": [
            {"value": clean_text(entity.get("normalized_value"), "日期待核验"), "source": entity.get("source_ref")}
            for entity in dates[:6]
        ],
        "review_items": [
            {
                "id": block["id"],
                "label": f"第 {block.get('page_no') or 1} 页",
                "text": clean_text(block.get("text"), "内容需要校对"),
                "confidence": block.get("confidence"),
                "review_status_label": review_status_label(block.get("review_status") or "review_required"),
            }
            for block in low_confidence[:8]
        ],
        "parsed_blocks": [
            {
                "id": block["id"],
                "label": f"? {block.get('page_no') or 1} ?",
                "text": clean_text(block.get("text"), "?????"),
                "confidence": block.get("confidence"),
                "review_status_label": review_status_label(block.get("review_status") or "review_required"),
            }
            for block in blocks[:20]
        ],
        "created_at": file.get("created_at"),
    }


def present_event(event: dict[str, Any], target: dict[str, Any] | None = None, subject: dict[str, Any] | None = None, case: dict[str, Any] | None = None) -> dict[str, Any]:
    importance = str(event.get("importance") or "medium").lower()
    source_refs = [present_source_ref(ref) for ref in event.get("source_refs", [])]
    subject_name = clean_text((subject or {}).get("name"), "相关主体")
    return {
        "id": event["id"],
        "case_id": (target or {}).get("case_id"),
        "case_name": clean_text((case or {}).get("case_name"), "相关案件"),
        "subject_id": (target or {}).get("subject_id"),
        "subject_name": subject_name,
        "title": clean_text(event.get("title"), f"{subject_name} 有新的监控动态"),
        "event_type": event.get("event_type"),
        "event_type_label": event_type_label(event.get("event_type")),
        "importance": importance,
        "importance_label": importance_label(importance),
        "detected_at": event.get("detected_at"),
        "source_refs": source_refs,
        "source_summary": "；".join(f"{ref['source_name']} · {ref['source_time']}" for ref in source_refs) or "来源待补充",
        "why_important": "该主体被列为重点监控对象，新动态可能影响执行回款路径。",
        "recommended_action": clean_text(event.get("recommended_action"), "查看来源并决定确认、忽略或转任务。"),
        "action_status": event.get("action_status", "unread"),
        "action_status_label": action_status_label(event.get("action_status")),
        "desktop_restore_url": f"/?case_id={(target or {}).get('case_id')}&tab=monitor&event_id={event['id']}",
    }


def present_case_card(case: dict[str, Any], counts: dict[str, Any] | None = None) -> dict[str, Any]:
    counts = counts or {}
    return {
        "id": case["id"],
        "case_name": clean_text(case.get("case_name"), "未命名案件"),
        "stage": case.get("stage"),
        "stage_label": stage_label(case.get("stage")),
        "risk_level": case.get("risk_level"),
        "risk_label": risk_label(case.get("risk_level")),
        "amount": clean_text(case.get("amount"), "金额待录入"),
        "status": case.get("status"),
        "counts": counts,
        "updated_at": case.get("updated_at"),
    }