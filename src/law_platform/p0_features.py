from __future__ import annotations

from typing import Any

from .diffing import classify_monitor_event, diff_snapshots
from .errors import AppError
from .models import money_to_text, new_id, now_iso
from .report_export import render_report_export
from .scoring import score_external_record, total_score
from .services import LawPlatform

_ORIGINAL_UPLOAD_FILE = LawPlatform.upload_file
_ORIGINAL_RESOLVE_SUBJECT = LawPlatform.resolve_subject
_ORIGINAL_GET_SUBJECT = LawPlatform.get_subject
_ORIGINAL_CASE_OVERVIEW = LawPlatform.case_overview
_ORIGINAL_GET_REPORT = LawPlatform.get_report


def install_p0_features() -> None:
    if getattr(LawPlatform, "_p0_features_installed", False):
        return
    LawPlatform.upload_file = upload_file
    LawPlatform.resolve_subject = resolve_subject
    LawPlatform.get_subject = get_subject
    LawPlatform.generate_asset_clue_report = generate_asset_clue_report
    LawPlatform.review_clue = review_clue
    LawPlatform.review_report = review_report
    LawPlatform.export_report = export_report
    LawPlatform.create_monitor_target = create_monitor_target
    LawPlatform.run_monitor_check = run_monitor_check
    LawPlatform.case_overview = case_overview
    LawPlatform._create_monitor_event = create_monitor_event_with_deliveries
    LawPlatform._create_notification = create_notification
    LawPlatform._p0_features_installed = True


def upload_file(self: LawPlatform, ctx, case_id: str, filename: str, content: bytes, file_type: str, sensitivity_level: str, source_channel: str) -> dict[str, Any]:
    result = _ORIGINAL_UPLOAD_FILE(self, ctx, case_id, filename, content, file_type, sensitivity_level, source_channel)
    apply_case_entities(self, case_id, result.get("entities") or [])
    return result


def apply_case_entities(self: LawPlatform, case_id: str, entities: list[dict[str, Any]]) -> None:
    case = self.store.get("cases", case_id)
    if not case:
        return
    summary = dict(case.get("extracted_summary") or {})
    buckets = {
        "case_no": "case_no",
        "court": "court",
        "cause_of_action": "cause_of_action",
        "amount": "amount",
        "deadline": "deadlines",
        "execution_basis": "execution_basis",
        "party": "parties",
        "date": "dates",
        "unified_social_credit_code": "unified_social_credit_codes",
    }
    for entity in entities:
        key = buckets.get(entity.get("entity_type"))
        if not key:
            continue
        value = entity.get("normalized_value")
        if not value:
            continue
        if key in {"deadlines", "parties", "dates", "unified_social_credit_codes"}:
            summary.setdefault(key, [])
            if value not in summary[key]:
                summary[key].append(value)
        else:
            summary.setdefault(key, value)
    updates: dict[str, Any] = {"extracted_summary": summary, "updated_at": now_iso()}
    if not case.get("cause_of_action") and summary.get("cause_of_action"):
        updates["cause_of_action"] = summary["cause_of_action"]
    if not case.get("amount") and summary.get("amount"):
        updates["amount"] = summary["amount"]
    self.store.update("cases", case_id, updates)


def resolve_subject(self: LawPlatform, ctx, payload: dict[str, Any]) -> dict[str, Any]:
    result = _ORIGINAL_RESOLVE_SUBJECT(self, ctx, payload)
    aliases = list(dict.fromkeys(payload.get("aliases") or []))
    if aliases:
        subject_id = result["candidates"][0]["subject_id"]
        subject = self.store.get("subjects", subject_id)
        merged = list(dict.fromkeys((subject.get("aliases") or []) + aliases))
        self.store.update("subjects", subject_id, {"aliases": merged, "updated_at": now_iso()})
        result["candidates"][0]["aliases"] = merged
    return result


def get_subject(self: LawPlatform, ctx, subject_id: str) -> dict[str, Any]:
    subject = _ORIGINAL_GET_SUBJECT(self, ctx, subject_id)
    relations = [row for row in self.store.list("subject_relations") if row.get("source_subject_id") == subject_id or row.get("target_subject_id") == subject_id]
    return {**subject, "relations": relations}


def generate_asset_clue_report(self: LawPlatform, ctx, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    case = self.security.require_case_access(ctx, case_id, "generate_asset_clue_report")
    subject = get_subject(self, ctx, payload["subject_id"])
    connector_ids = payload.get("connector_ids") or [
        "manual_company_connector",
        "execution_public_connector",
        "public_auction_connector",
        "ip_rights_connector",
        "bid_receivable_connector",
    ]
    template = payload.get("report_template", "execution_asset_clue_v1")
    template_check = self.plugins.run_contract_tests(template)
    if template_check["status"] != "passed":
        raise AppError("VALIDATION_ERROR", "报告模板未通过契约测试", 400, template_check)
    records: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    for connector_id in connector_ids:
        run, new_records = self.plugins.execute_connector(connector_id, ctx.tenant_id, case, subject, ctx.actor_id)
        runs.append(run)
        for record in new_records:
            self.store.insert("external_records", record)
        records.extend(new_records)
    clues: list[dict[str, Any]] = []
    for record in records:
        clues.extend(clues_from_record(self, ctx, case, subject, record))
    report = create_report(self, case, subject, clues, template)
    job = {"job_id": new_id("job"), "status": "completed", "report_id": report["id"], "plugin_run_ids": [run["id"] for run in runs], "clue_ids": [clue["id"] for clue in clues]}
    self.security.audit(ctx, "asset_clue_report_generated", "report", report["id"], {"case_id": case_id, "clue_count": len(clues), "connector_ids": connector_ids})
    return job


def clues_from_record(self: LawPlatform, ctx, case: dict[str, Any], subject: dict[str, Any], record: dict[str, Any]) -> list[dict[str, Any]]:
    if record["record_type"] == "company":
        payload = record.get("normalized_payload", {})
        clues = [create_clue(self, ctx, case, subject, record, "equity", f"{subject['name']}存在股权结构线索")]
        for shareholder in payload.get("shareholders", [])[:2]:
            related = ensure_related_subject(self, ctx, subject, shareholder.get("name", "关联主体待核验"), "shareholder", record["id"])
            clues.append(create_clue(self, ctx, case, related, record, "related_subject", f"发现关联主体：{related['name']}"))
        return clues
    clue_type = {"auction": "auction", "execution": "execution", "ip": "ip", "bid": "bid", "receivable": "receivable"}.get(record["record_type"], "related_subject")
    title = {"auction": f"{subject['name']}存在司法拍卖线索", "execution": f"{subject['name']}新增执行公开信息", "ip": f"{subject['name']}存在知识产权线索", "bid": f"{subject['name']}存在招投标经营线索", "receivable": f"{subject['name']}存在应收账款线索"}.get(record["record_type"], f"{subject['name']}存在待核验财产线索")
    return [create_clue(self, ctx, case, subject, record, clue_type, title)]


def ensure_related_subject(self: LawPlatform, ctx, source_subject: dict[str, Any], name: str, relation_type: str, source_record_id: str) -> dict[str, Any]:
    existing = next((row for row in self.store.list("subjects") if row.get("tenant_id") == ctx.tenant_id and row.get("name") == name), None)
    subject = existing or {"id": new_id("sub"), "tenant_id": ctx.tenant_id, "subject_type": "company" if "公司" in name or "平台" in name else "person", "name": name, "aliases": [], "unified_social_credit_code": None, "id_card_hash": None, "resolve_status": "candidate", "confidence": 0.7, "profile": {"source": "connector_relation", "needs_confirmation": True}, "created_at": now_iso(), "updated_at": now_iso()}
    if not existing:
        self.store.insert("subjects", subject)
    relation_id = f"{source_subject['id']}:{subject['id']}:{relation_type}:{source_record_id}"
    if not self.store.get("subject_relations", relation_id):
        self.store.insert("subject_relations", {"id": relation_id, "source_subject_id": source_subject["id"], "target_subject_id": subject["id"], "relation_type": relation_type, "strength": 0.72, "source_record_id": source_record_id, "created_at": now_iso()})
    return subject

def create_clue(self: LawPlatform, ctx, case: dict[str, Any], subject: dict[str, Any], record: dict[str, Any], clue_type: str, title: str) -> dict[str, Any]:
    scoring_record = {**record, "record_type": clue_type if clue_type != "equity" else "company"}
    breakdown = score_external_record(scoring_record, case)
    score = total_score(breakdown)
    source_ref = {"source_name": record["source_name"], "source_url": record.get("source_url"), "source_time": record.get("record_time"), "fetched_at": record["fetched_at"], "external_record_id": record["id"], "snippet": str(record.get("normalized_payload", {}))[:220]}
    clue = {"id": new_id("clue"), "case_id": case["id"], "subject_id": subject["id"], "report_id": None, "clue_type": clue_type, "title": title, "description": record_description(record), "estimated_value": estimated_value(case, record), "actionability_score": score, "score_breakdown": breakdown, "confidence": breakdown["credibility"] / 100, "source_refs": [source_ref], "review_status": "pending", "recommended_action": recommended_action(clue_type), "verification_items": verification_items(clue_type), "why_important": why_important(clue_type), "created_at": now_iso(), "updated_at": now_iso()}
    self.store.insert("asset_clues", clue)
    self.store.insert("asset_clue_scores", {"id": new_id("score"), "clue_id": clue["id"], "case_id": case["id"], "score_breakdown": breakdown, "total_score": score, "created_at": now_iso()})
    return clue


def create_report(self: LawPlatform, case: dict[str, Any], subject: dict[str, Any], clues: list[dict[str, Any]], template: str) -> dict[str, Any]:
    report_id = new_id("report")
    sections = [
        "# 财产线索报告",
        f"## 被执行人主体确认\n- 主体：{subject['name']}\n- 识别状态：{subject['resolve_status']}",
        "## 执行公开信息摘要", section_for(clues, "execution"),
        "## 工商与股权结构", section_for(clues, "equity"),
        "## 对外投资与关联主体", section_for(clues, "related_subject"),
        "## 司法拍卖资产线索", section_for(clues, "auction"),
        "## 知识产权和经营权益线索", section_for(clues, "ip"),
        "## 招投标/应收账款线索", section_for(clues, "bid") + "\n" + section_for(clues, "receivable"),
        "## 疑似可追加主体或人格混同线索\n- 关联主体仅作为待核验事项，不作为最终法律判断。",
        "## 线索价值排序", "\n".join(f"- {clue['title']}：{clue['actionability_score']} 分，来源：{clue['source_refs'][0]['source_name']}，可信度：{int(clue['confidence'] * 100)}%" for clue in sorted(clues, key=lambda row: row["actionability_score"], reverse=True)),
        "## 建议执行动作", "\n".join(f"- {clue['recommended_action']}" for clue in clues),
        "## 待人工核验事项\n- 核验主体身份、资产权属、公告状态和执行可行性。\n- 报告发布前必须完成律师复核。",
    ]
    report = {"id": report_id, "case_id": case["id"], "report_type": "asset_clue", "title": f"{case['case_name']} - 财产线索报告", "content_md": "\n\n".join(sections), "generation_status": "review_required", "generated_by": "system", "model_invocation_id": None, "reviewed_by": None, "template": template, "created_at": now_iso(), "updated_at": now_iso()}
    self.store.insert("reports", report)
    for clue in clues:
        self.store.update("asset_clues", clue["id"], {"report_id": report_id})
        clue["report_id"] = report_id
    return report


def review_report(self: LawPlatform, ctx, report_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    report = self.store.get("reports", report_id)
    if not report:
        raise AppError("VALIDATION_ERROR", "报告不存在", 404)
    self.security.require_case_access(ctx, report["case_id"], "review_report")
    status = payload.get("review_status", "confirmed")
    generation_status = "confirmed" if status == "confirmed" else "review_required"
    updated = self.store.update("reports", report_id, {"generation_status": generation_status, "reviewed_by": ctx.actor_id, "review_comment": payload.get("comment"), "updated_at": now_iso()})
    review = self._review(ctx, "report", report_id, status, payload.get("comment"))
    self.security.audit(ctx, "report_reviewed", "report", report_id, {"review_id": review["id"], "status": status})
    return updated


def export_report(self: LawPlatform, ctx, report_id: str, export_format: str) -> dict[str, Any]:
    report_with_clues = _ORIGINAL_GET_REPORT(self, ctx, report_id)
    try:
        body, media_type, filename = render_report_export(report_with_clues, report_with_clues["asset_clues"], export_format)
    except ValueError:
        raise AppError("VALIDATION_ERROR", "P0 当前支持 md 和 word 基础导出", 400)
    export = {"id": new_id("export"), "tenant_id": ctx.tenant_id, "report_id": report_id, "actor_id": ctx.actor_id, "format": export_format, "filename": filename, "created_at": now_iso()}
    self.store.insert("report_exports", export)
    self.security.audit(ctx, "report_exported", "report", report_id, {"export_id": export["id"], "format": export_format})
    return {"body": body, "media_type": media_type, "filename": filename, "export": export}


def review_clue(self: LawPlatform, ctx, clue_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    clue = self.store.get("asset_clues", clue_id)
    if not clue:
        raise AppError("VALIDATION_ERROR", "线索不存在", 404)
    self.security.require_case_access(ctx, clue["case_id"], "review_asset_clue")
    updates = {"review_status": payload["review_status"], "review_comment": payload.get("comment"), "updated_at": now_iso()}
    if payload.get("corrected_fields"):
        updates.update(payload["corrected_fields"])
        updates["review_status"] = "edited"
    task = None
    if payload.get("next_action") == "create_task":
        updates["review_status"] = "task_created"
        task = self._create_task(ctx, clue["case_id"], "asset_clue", clue_id, clue["recommended_action"] or "核验线索")
    updated = self.store.update("asset_clues", clue_id, updates)
    review = self._review(ctx, "asset_clue", clue_id, updates["review_status"], payload.get("comment"))
    if payload.get("usefulness") or updates["review_status"] == "rejected":
        feedback = {"id": new_id("fb"), "tenant_id": ctx.tenant_id, "object_type": "asset_clue", "object_id": clue_id, "actor_id": ctx.actor_id, "usefulness": payload.get("usefulness"), "reason": payload.get("comment"), "created_at": now_iso()}
        self.store.insert("feedback_records", feedback)
    self.security.audit(ctx, "asset_clue_reviewed", "asset_clue", clue_id, {"review_id": review["id"], "task_id": task["id"] if task else None})
    return {"clue": updated, "task": task}


def create_monitor_target(self: LawPlatform, ctx, payload: dict[str, Any]) -> dict[str, Any]:
    case = self.security.require_case_access(ctx, payload["case_id"], "create_monitor_target")
    subject = get_subject(self, ctx, payload["subject_id"])
    target = {"id": new_id("mon"), "tenant_id": ctx.tenant_id, "case_id": case["id"], "subject_id": subject["id"], "event_types": payload.get("event_types") or ["new_execution", "new_auction"], "frequency": payload.get("frequency", "daily"), "notify_channels": payload.get("notify_channels") or ["in_app"], "status": "active", "created_at": now_iso(), "updated_at": now_iso()}
    self.store.insert("monitor_targets", target)
    create_snapshot(self, target["id"], snapshot_for_subject(subject), "initial")
    event = create_monitor_event_with_deliveries(self, ctx, target, subject, "company_change", "high", "重点主体监控已建立", [])
    self.security.audit(ctx, "monitor_target_created", "monitor_target", target["id"], {"event_id": event["id"]})
    return {**target, "initial_event_id": event["id"]}


def run_monitor_check(self: LawPlatform, ctx, target_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    target = self.store.get("monitor_targets", target_id)
    if not target:
        raise AppError("VALIDATION_ERROR", "监控目标不存在", 404)
    self.security.require_case_access(ctx, target["case_id"], "run_monitor_check")
    subject = get_subject(self, ctx, target["subject_id"])
    previous = latest_snapshot(self, target_id)
    current_payload = payload.get("snapshot") or snapshot_for_subject(subject)
    diffs = diff_snapshots(previous.get("payload") if previous else None, current_payload)
    snapshot = create_snapshot(self, target_id, current_payload, "manual_check")
    event = None
    if diffs:
        event_type, importance = classify_monitor_event(diffs)
        title = payload.get("title") or f"{subject['name']} 发现字段变化"
        event = create_monitor_event_with_deliveries(self, ctx, target, subject, event_type, importance, title, diffs)
    self.security.audit(ctx, "monitor_check_run", "monitor_target", target_id, {"snapshot_id": snapshot["id"], "diff_count": len(diffs), "event_id": event["id"] if event else None})
    return {"snapshot": snapshot, "diffs": diffs, "event": event}

def case_overview(self: LawPlatform, ctx, case_id: str) -> dict[str, Any]:
    data = _ORIGINAL_CASE_OVERVIEW(self, ctx, case_id)
    case = self.store.get("cases", case_id) or {}
    data["case"]["extracted_summary"] = case.get("extracted_summary", {})
    report_reviews = [{"type": "report", "id": report["id"], "title": report["title"]} for report in self.store.list("reports") if report.get("case_id") == case_id and report.get("generation_status") == "review_required"]
    known = {(row["type"], row["id"]) for row in data.get("pending_reviews", [])}
    data["pending_reviews"].extend(row for row in report_reviews if (row["type"], row["id"]) not in known)
    return data


def snapshot_for_subject(subject: dict[str, Any]) -> dict[str, Any]:
    return {"name": subject.get("name"), "aliases": subject.get("aliases", []), "resolve_status": subject.get("resolve_status"), "profile": subject.get("profile", {})}


def latest_snapshot(self: LawPlatform, target_id: str) -> dict[str, Any] | None:
    snapshots = [row for row in self.store.list("monitor_snapshots") if row.get("monitor_target_id") == target_id]
    return sorted(snapshots, key=lambda row: row["created_at"])[-1] if snapshots else None


def create_snapshot(self: LawPlatform, target_id: str, payload: dict[str, Any], snapshot_type: str) -> dict[str, Any]:
    snapshot = {"id": new_id("snap"), "monitor_target_id": target_id, "snapshot_type": snapshot_type, "payload": payload, "created_at": now_iso()}
    self.store.insert("monitor_snapshots", snapshot)
    return snapshot


def create_monitor_event_with_deliveries(self: LawPlatform, ctx, target: dict[str, Any], subject: dict[str, Any], event_type: str, importance: str, title: str, field_diffs: list[dict[str, Any]]) -> dict[str, Any]:
    source_ref = {"source_name": "站内监控快照", "source_url": f"/api/monitor-targets/{target['id']}", "source_time": now_iso(), "fetched_at": now_iso(), "snippet": title}
    event = {"id": new_id("event"), "monitor_target_id": target["id"], "event_type": event_type, "title": title, "importance": importance, "detected_at": now_iso(), "source_refs": [source_ref], "field_diffs": field_diffs, "action_status": "unread", "recommended_action": "查看来源并决定确认、忽略或转任务。", "created_at": now_iso(), "updated_at": now_iso()}
    self.store.insert("monitor_events", event)
    create_notification(self, ctx, target, event)
    return event


def create_notification(self: LawPlatform, ctx, target: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    notification_id = new_id("note")
    notification = {"id": notification_id, "tenant_id": ctx.tenant_id, "event_id": event["id"], "title": event["title"], "why_important": "该主体被列为重点监控对象，新动态可能影响执行回款路径。", "deep_link": f"/mobile/notifications/{notification_id}", "channels": target.get("notify_channels") or ["in_app"], "action_buttons": ["确认", "忽略", "转任务"], "created_at": now_iso()}
    self.store.insert("notifications", notification)
    plugin_by_channel = {"in_app": "in_app_notifier", "feishu": "feishu_notifier", "wecom": "wecom_notifier", "email": "email_notifier"}
    for channel in notification["channels"]:
        plugin_id = plugin_by_channel.get(channel, "in_app_notifier")
        contract = self.plugins.run_contract_tests(plugin_id)
        delivery = {"id": new_id("delivery"), "tenant_id": ctx.tenant_id, "notification_id": notification_id, "channel": channel, "plugin_id": plugin_id, "delivery_status": "recorded" if contract["status"] == "passed" else "failed", "deep_link": notification["deep_link"], "created_at": now_iso()}
        self.store.insert("notification_deliveries", delivery)
    return notification


def record_description(record: dict[str, Any]) -> str:
    payload = record.get("normalized_payload", {})
    if record["record_type"] == "auction":
        return f"公开拍卖来源显示：{payload.get('asset_name')}，状态：{payload.get('status')}。"
    if record["record_type"] == "execution":
        return f"执行公开信息显示案件相关动态，金额：{payload.get('amount') or '待核验'}。"
    if record["record_type"] == "company":
        return f"工商来源显示存在股东、曾用名或关联主体，注册资本：{payload.get('registered_capital', '待核验')}。"
    if record["record_type"] == "ip":
        return f"知识产权来源显示：{payload.get('right_name')}，状态：{payload.get('status')}。"
    if record["record_type"] == "bid":
        return f"招投标来源显示：{payload.get('project_name')}，状态：{payload.get('status')}。"
    if record["record_type"] == "receivable":
        return f"应收账款来源显示：{payload.get('debtor')}，状态：{payload.get('status')}。"
    return "授权来源返回了待核验记录。"


def estimated_value(case: dict[str, Any], record: dict[str, Any]) -> str:
    payload = record.get("normalized_payload", {})
    return payload.get("estimated_value") or payload.get("starting_price") or payload.get("contract_amount") or (money_to_text(case.get("amount")) if record["record_type"] == "execution" else "待核验")


def recommended_action(clue_type: str) -> str:
    return {"auction": "核验拍卖资产权属、处置阶段和是否可申请参与分配。", "execution": "核验新增执行信息与本案关联性，判断是否并案或追加调查。", "equity": "核验股权结构、对外投资和可追加主体线索。", "related_subject": "核验关联主体身份、出资关系和可追加路径。", "ip": "核验知识产权权属、质押和可处置价值。", "bid": "核验中标合同、付款方和回款周期。", "receivable": "核验应收账款债务人、金额和协助执行可能性。"}.get(clue_type, "人工核验来源和可执行性。")


def verification_items(clue_type: str) -> list[str]:
    common = ["核验来源是否为授权或公开渠道", "核验主体是否与本案被执行人一致"]
    return common + {"auction": ["核验拍卖标的权属", "核验拍卖阶段和处置状态"], "execution": ["核验案号和执行法院", "核验是否可并案或追加调查"], "equity": ["核验股东名册和出资状态"], "related_subject": ["核验关联关系强度", "核验是否存在人格混同线索"], "ip": ["核验权属和质押状态"], "bid": ["核验合同金额和付款方"], "receivable": ["核验债权金额和付款周期"]}.get(clue_type, ["人工核验可执行性"])


def why_important(clue_type: str) -> str:
    return {"auction": "可能存在可参与分配或申请控制的处置资产。", "execution": "新增执行动态可能影响回款路径和优先顺位。", "equity": "股权和投资关系可能引出可执行权益或追加主体。", "related_subject": "关联主体可能影响追加执行和人格混同判断。", "ip": "知识产权可能具备处置、许可或质押价值。", "bid": "中标项目可能形成经营回款或应收账款。", "receivable": "应收账款可作为协助执行或保全线索。"}.get(clue_type, "该线索可能影响执行动作选择。")


def section_for(clues: list[dict[str, Any]], clue_type: str) -> str:
    rows = [clue for clue in clues if clue["clue_type"] == clue_type]
    if not rows:
        return "- P0 当前未发现授权来源返回的明确线索。"
    return "\n".join(f"- {clue['title']}，评分：{clue['actionability_score']}，来源：{clue['source_refs'][0]['source_name']}，建议：{clue['recommended_action']}" for clue in rows)