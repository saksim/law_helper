from __future__ import annotations

from typing import Any

from .data_dictionary import build_lineage, data_dictionary_payload, normalize_file_type, normalize_source_channel, validate_store_against_dictionary
from .document_pipeline import DocumentPipeline
from .errors import AppError
from .implementation_plan import (
    create_implementation_checkpoint,
    implementation_plan_payload,
    implementation_status as build_implementation_status,
)
from .models import TENANT_ID, money_to_text, new_id, now_iso
from .plugins import PluginService
from .qa_acceptance import acceptance_plan_payload, create_acceptance_run
from .runbook import (
    create_runbook_check,
    create_runbook_incident,
    resolve_runbook_incident,
    runbook_payload,
    runbook_status as build_runbook_status,
)
from .security import RequestContext, SecurityService
from .store import Store


class LawPlatform:
    def __init__(self, store: Store):
        self.store = store
        self.security = SecurityService(store)
        self.plugins = PluginService(store)
        self.documents = DocumentPipeline()

    def create_case(self, ctx: RequestContext, payload: dict[str, Any]) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "lawyer"})
        case_id = new_id("case")
        responsible = payload.get("responsible_lawyer_id") or ctx.actor_id
        access_user_ids = sorted(set([ctx.actor_id, responsible, "user_assistant", "user_reviewer"]))
        case = {
            "id": case_id,
            "tenant_id": ctx.tenant_id,
            "case_name": payload["case_name"],
            "case_type": payload.get("case_type", "execution"),
            "cause_of_action": payload.get("cause_of_action"),
            "stage": payload.get("stage", "execution"),
            "amount": str(payload.get("amount")) if payload.get("amount") is not None else None,
            "responsible_lawyer_id": responsible,
            "risk_level": payload.get("risk_level", "medium"),
            "status": "active",
            "access_user_ids": access_user_ids,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.insert("cases", case)
        self.security.audit(ctx, "case_created", "case", case_id, {"case_name": case["case_name"]})
        return case

    def list_cases(self, ctx: RequestContext) -> list[dict[str, Any]]:
        user = self.security.user(ctx)
        rows = []
        for case in self.store.list("cases"):
            if case.get("tenant_id") != ctx.tenant_id or case.get("deleted_at"):
                continue
            if user["role"] in {"owner", "admin"} or ctx.actor_id in case.get("access_user_ids", []) or case.get("responsible_lawyer_id") == ctx.actor_id:
                rows.append(case)
        return rows

    def get_case(self, ctx: RequestContext, case_id: str) -> dict[str, Any]:
        return self.security.require_case_access(ctx, case_id)

    def update_case(self, ctx: RequestContext, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.security.require_case_access(ctx, case_id, "update")
        allowed = {key: value for key, value in payload.items() if key in {"case_name", "risk_level", "status", "stage", "cause_of_action"} and value is not None}
        allowed["updated_at"] = now_iso()
        case = self.store.update("cases", case_id, allowed)
        self.security.audit(ctx, "case_updated", "case", case_id, {"fields": sorted(allowed)})
        return case

    def upload_file(self, ctx: RequestContext, case_id: str, filename: str, content: bytes, file_type: str, sensitivity_level: str, source_channel: str) -> dict[str, Any]:
        self.security.require_case_access(ctx, case_id, "upload_file")
        self.security.require_sensitive_access(ctx, sensitivity_level)
        file_type = normalize_file_type(file_type)
        source_channel = normalize_source_channel(source_channel)
        parsed = self.documents.parse(filename, content)
        file_id = new_id("file")
        case_file = {
            "id": file_id,
            "case_id": case_id,
            "original_name": filename,
            "file_type": file_type,
            "storage_path": f"object://case-files/{case_id}/{file_id}/{filename}",
            "parse_status": parsed.parse_status,
            "sensitivity_level": sensitivity_level,
            "uploaded_by": ctx.actor_id,
            "source_channel": source_channel,
            "markdown": parsed.markdown,
            "quality_summary": parsed.quality_summary,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.insert("case_files", case_file)
        for block in parsed.blocks:
            block["file_id"] = file_id
            self.store.insert("document_blocks", block)
        for entity in parsed.entities:
            entity["object_id"] = file_id
            self.store.insert("extracted_entities", entity)
        self.security.audit(
            ctx,
            "file_uploaded_and_parsed",
            "case_file",
            file_id,
            {"case_id": case_id, "parse_status": parsed.parse_status, "sensitivity_level": sensitivity_level},
        )
        return {**case_file, "blocks": parsed.blocks, "entities": parsed.entities}

    def parse_result(self, ctx: RequestContext, file_id: str) -> dict[str, Any]:
        file = self.store.get("case_files", file_id)
        if not file:
            raise AppError("VALIDATION_ERROR", "文件不存在", 404)
        self.security.require_case_access(ctx, file["case_id"])
        self.security.require_sensitive_access(ctx, file.get("sensitivity_level", "L4"))
        blocks = [block for block in self.store.list("document_blocks") if block.get("file_id") == file_id]
        protected_blocks = [self.security.protect_material_record(ctx, block, file.get("sensitivity_level")) for block in blocks]
        self.security.audit(ctx, "material_viewed", "case_file", file_id, {"case_id": file["case_id"], "sensitivity_level": file.get("sensitivity_level"), "client_type": ctx.client_type})
        return {
            "file_id": file_id,
            "parse_status": file["parse_status"],
            "markdown_url": f"/api/files/{file_id}/markdown",
            "quality_summary": file.get("quality_summary", {}),
            "blocks": protected_blocks,
        }

    def review_block(self, ctx: RequestContext, block_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        block = self.store.get("document_blocks", block_id)
        if not block:
            raise AppError("VALIDATION_ERROR", "文档块不存在", 404)
        file = self.store.get("case_files", block["file_id"])
        self.security.require_case_access(ctx, file["case_id"], "review_document_block")
        updates = {"review_status": payload["review_status"], "updated_at": now_iso()}
        if payload.get("corrected_text"):
            updates["text"] = payload["corrected_text"]
            updates["markdown"] = payload["corrected_text"]
            updates["confidence"] = 1.0
        block = self.store.update("document_blocks", block_id, updates)
        review = self._review(ctx, "document_block", block_id, payload["review_status"], payload.get("reason"))
        self.security.audit(ctx, "document_block_reviewed", "document_block", block_id, {"review_id": review["id"]})
        return block

    def resolve_subject(self, ctx: RequestContext, payload: dict[str, Any]) -> dict[str, Any]:
        case_id = payload.get("case_id")
        if case_id:
            self.security.require_case_access(ctx, case_id, "resolve_subject")
        name = payload["name"].strip()
        uscc = (payload.get("unified_social_credit_code") or "").strip() or None
        existing = None
        for subject in self.store.list("subjects"):
            if subject.get("tenant_id") == ctx.tenant_id and (subject.get("name") == name or (uscc and subject.get("unified_social_credit_code") == uscc)):
                existing = subject
                break
        if existing:
            subject = existing
        else:
            subject = {
                "id": new_id("sub"),
                "tenant_id": ctx.tenant_id,
                "subject_type": "company" if any(word in name for word in ["公司", "企业", "集团"]) else "person",
                "name": name,
                "unified_social_credit_code": uscc,
                "id_card_hash": None,
                "resolve_status": "confirmed" if uscc else "candidate",
                "confidence": 0.95 if uscc else 0.76,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            self.store.insert("subjects", subject)
        if case_id:
            self._link_subject_to_case(case_id, subject["id"])
        self.security.audit(ctx, "subject_resolved", "subject", subject["id"], {"case_id": case_id, "requires_confirmation": not bool(uscc)})
        return {
            "candidates": [
                {
                    "subject_id": subject["id"],
                    "name": subject["name"],
                    "unified_social_credit_code": subject.get("unified_social_credit_code"),
                    "confidence": subject["confidence"],
                    "source_refs": [],
                    "resolve_status": subject["resolve_status"],
                }
            ],
            "requires_confirmation": not bool(uscc),
        }

    def get_subject(self, ctx: RequestContext, subject_id: str) -> dict[str, Any]:
        subject = self.store.get("subjects", subject_id)
        if not subject or subject.get("tenant_id") != ctx.tenant_id:
            raise AppError("VALIDATION_ERROR", "主体不存在", 404)
        return subject


    def attach_subject_to_case(self, ctx: RequestContext, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.security.require_case_access(ctx, case_id, 'attach_subject')
        subject_id = payload.get('subject_id')
        if subject_id:
            subject = self.get_subject(ctx, subject_id)
            self._link_subject_to_case(case_id, subject['id'])
            self.security.audit(ctx, 'subject_attached_to_case', 'subject', subject['id'], {'case_id': case_id})
            return {
                'candidates': [
                    {
                        'subject_id': subject['id'],
                        'name': subject['name'],
                        'unified_social_credit_code': subject.get('unified_social_credit_code'),
                        'confidence': subject.get('confidence'),
                        'source_refs': [],
                        'resolve_status': subject.get('resolve_status'),
                    }
                ],
                'requires_confirmation': subject.get('resolve_status') != 'confirmed',
                'test_status': 'untested',
            }
        if not payload.get('name'):
            raise AppError('VALIDATION_ERROR', 'subject_id or name is required', 400, {'test_status': 'untested'})
        return self.resolve_subject(ctx, {**payload, 'case_id': case_id})

    def generate_asset_clue_report(self, ctx: RequestContext, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        case = self.security.require_case_access(ctx, case_id, "generate_asset_clue_report")
        subject = self.get_subject(ctx, payload["subject_id"])
        connector_ids = payload.get("connector_ids") or ["manual_company_connector", "execution_public_connector", "public_auction_connector"]
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
        clues = [self._clue_from_record(ctx, case, subject, record) for record in records]
        report = self._create_report(ctx, case, subject, clues, template)
        job = {
            "job_id": new_id("job"),
            "status": "completed",
            "report_id": report["id"],
            "plugin_run_ids": [run["id"] for run in runs],
            "clue_ids": [clue["id"] for clue in clues],
        }
        self.security.audit(ctx, "asset_clue_report_generated", "report", report["id"], {"case_id": case_id, "clue_count": len(clues)})
        return job

    def get_report(self, ctx: RequestContext, report_id: str) -> dict[str, Any]:
        report = self.store.get("reports", report_id)
        if not report:
            raise AppError("VALIDATION_ERROR", "报告不存在", 404)
        self.security.require_case_access(ctx, report["case_id"])
        clues = [clue for clue in self.store.list("asset_clues") if clue.get("report_id") == report_id]
        self.security.audit(ctx, "report_viewed", "report", report_id, {"case_id": report["case_id"], "client_type": ctx.client_type})
        return self.security.redact_record({**report, "asset_clues": clues})

    def review_clue(self, ctx: RequestContext, clue_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        clue = self.store.get("asset_clues", clue_id)
        if not clue:
            raise AppError("VALIDATION_ERROR", "线索不存在", 404)
        self.security.require_case_access(ctx, clue["case_id"], "review_asset_clue")
        updates = {
            "review_status": payload["review_status"],
            "review_comment": payload.get("comment"),
            "updated_at": now_iso(),
        }
        task = None
        if payload.get("next_action") == "create_task":
            updates['review_status'] = 'task_created'
            task = self._create_task(ctx, clue["case_id"], "asset_clue", clue_id, clue["recommended_action"] or "核验线索")
        updated = self.store.update("asset_clues", clue_id, updates)
        review = self._review(ctx, "asset_clue", clue_id, updates["review_status"], payload.get("comment"))
        self.security.audit(ctx, "asset_clue_reviewed", "asset_clue", clue_id, {"review_id": review["id"], "task_id": task["id"] if task else None})
        return {"clue": updated, "task": task}

    def create_monitor_target(self, ctx: RequestContext, payload: dict[str, Any]) -> dict[str, Any]:
        case = self.security.require_case_access(ctx, payload["case_id"], "create_monitor_target")
        subject = self.get_subject(ctx, payload["subject_id"])
        target = {
            "id": new_id("mon"),
            "tenant_id": ctx.tenant_id,
            "case_id": case["id"],
            "subject_id": subject["id"],
            "event_types": payload.get("event_types") or ["new_execution", "new_auction"],
            "frequency": payload.get("frequency", "daily"),
            "notify_channels": payload.get("notify_channels") or ["in_app"],
            "status": "active",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.insert("monitor_targets", target)
        event = self._create_monitor_event(ctx, target, subject)
        self.security.audit(ctx, "monitor_target_created", "monitor_target", target["id"], {"event_id": event["id"]})
        return {**target, "initial_event_id": event["id"]}

    def list_monitor_targets(self, ctx: RequestContext) -> list[dict[str, Any]]:
        user = self.security.user(ctx)
        visible_case_ids = None
        if user.get("role") not in {"owner", "admin", "auditor"}:
            visible_case_ids = {case["id"] for case in self.list_cases(ctx)}
        return [
            target
            for target in self.store.list("monitor_targets")
            if target.get("tenant_id") == ctx.tenant_id and (visible_case_ids is None or target.get("case_id") in visible_case_ids)
        ]

    def list_monitor_events(self, ctx: RequestContext) -> list[dict[str, Any]]:
        user = self.security.user(ctx)
        visible_case_ids = None
        if user.get("role") not in {"owner", "admin", "auditor"}:
            visible_case_ids = {case["id"] for case in self.list_cases(ctx)}
        events = []
        for event in self.store.list("monitor_events"):
            target = self.store.get("monitor_targets", event["monitor_target_id"])
            if target and target.get("tenant_id") == ctx.tenant_id and (visible_case_ids is None or target.get("case_id") in visible_case_ids):
                events.append(self.security.redact_record(event))
        return events

    def handle_monitor_event(self, ctx: RequestContext, event_id: str, action: str) -> dict[str, Any]:
        event = self.store.get("monitor_events", event_id)
        if not event:
            raise AppError("VALIDATION_ERROR", "监控事件不存在", 404)
        target = self.store.get("monitor_targets", event["monitor_target_id"])
        self.security.require_case_access(ctx, target["case_id"], "handle_monitor_event")
        status_map = {"ack": "acknowledged", "ignore": "ignored", "convert-to-task": "task_created"}
        updated = self.store.update("monitor_events", event_id, {"action_status": status_map[action], "updated_at": now_iso()})
        task = None
        if action == "convert-to-task":
            task = self._create_task(ctx, target["case_id"], "monitor_event", event_id, event["recommended_action"])
        self.security.audit(ctx, f"monitor_event_{action}", "monitor_event", event_id, {"task_id": task["id"] if task else None})
        return {"event": updated, "task": task}

    def case_overview(self, ctx: RequestContext, case_id: str) -> dict[str, Any]:
        case = self.security.require_case_access(ctx, case_id)
        clues = [clue for clue in self.store.list("asset_clues") if clue.get("case_id") == case_id]
        events = []
        for event in self.store.list("monitor_events"):
            target = self.store.get("monitor_targets", event["monitor_target_id"])
            if target and target["case_id"] == case_id:
                events.append(event)
        files = [file for file in self.store.list("case_files") if file.get("case_id") == case_id]
        tasks = [task for task in self.store.list("tasks") if task.get("case_id") == case_id and task.get("status") == "open"]
        pending_reviews = [
            {"type": "asset_clue", "id": clue["id"], "title": clue["title"]}
            for clue in clues
            if clue.get("review_status") == "pending"
        ]
        pending_reviews.extend(
            {"type": "case_file", "id": file["id"], "title": file["original_name"]}
            for file in files
            if file.get("parse_status") == "review_required"
        )
        highlights = [
            {
                "type": "asset_clue",
                "title": clue["title"],
                "importance": self._importance(clue["actionability_score"]),
                "source_time": (clue["source_refs"][0] or {}).get("source_time") if clue.get("source_refs") else clue.get("created_at"),
                "action": clue.get("recommended_action"),
            }
            for clue in sorted(clues, key=lambda row: row["actionability_score"], reverse=True)[:5]
        ]
        highlights.extend(
            {
                "type": "monitor_event",
                "title": event["title"],
                "importance": event["importance"],
                "source_time": event["detected_at"],
                "action": event["recommended_action"],
            }
            for event in events[:3]
        )
        file_ids = {file["id"] for file in files}
        deadlines = [
            {
                "source": entity["source_ref"],
                "date": entity["normalized_value"],
                "title": "材料中识别到关键日期",
            }
            for entity in self.store.list("extracted_entities")
            if entity.get("entity_type") == "date" and entity.get("object_id") in file_ids
        ][:5]
        return {
            "case": {"id": case["id"], "case_name": case["case_name"], "stage": case["stage"], "risk_level": case.get("risk_level")},
            "today_highlights": highlights,
            "pending_reviews": pending_reviews,
            "deadlines": deadlines,
            "tasks": tasks,
            "material_status": [{"file_id": file["id"], "name": file["original_name"], "parse_status": file["parse_status"]} for file in files],
        }

    def mobile_notification(self, ctx: RequestContext, notification_id: str) -> dict[str, Any]:
        notification = self.store.get("notifications", notification_id)
        if not notification:
            raise AppError("VALIDATION_ERROR", "通知不存在", 404)
        event = self.store.get("monitor_events", notification["event_id"])
        target = self.store.get("monitor_targets", event["monitor_target_id"])
        self.security.require_case_access(ctx, target["case_id"], "view_notification")
        return {
            "id": notification["id"],
            "event_id": event["id"],
            "title": notification["title"],
            "event_type": event["event_type"],
            "why_important": notification["why_important"],
            "source_refs": event["source_refs"],
            "detected_at": event["detected_at"],
            "recommended_action": event["recommended_action"],
            "deep_link": notification["deep_link"],
            "action_buttons": ["确认", "忽略", "转任务"],
            "action_status": event["action_status"],
        }

    def audit_logs(self, ctx: RequestContext) -> list[dict[str, Any]]:
        self.security.require_role(ctx, {"owner", "admin", "auditor"})
        return [log for log in self.store.list("audit_logs") if log.get("tenant_id") == ctx.tenant_id]

    def review_records(self, ctx: RequestContext) -> list[dict[str, Any]]:
        self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer"})
        return [row for row in self.store.list("review_records") if row.get("tenant_id") == ctx.tenant_id]

    def model_invocations(self, ctx: RequestContext) -> list[dict[str, Any]]:
        self.security.require_role(ctx, {"owner", "admin", "auditor"})
        return [row for row in self.store.list("model_invocations") if row.get("tenant_id") == ctx.tenant_id]

    def qa_acceptance_plan(self, ctx: RequestContext) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
        return acceptance_plan_payload()

    def create_qa_acceptance_run(self, ctx: RequestContext, payload: dict[str, Any]) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer"})
        run = create_acceptance_run(self.store, ctx.tenant_id, ctx.actor_id, payload)
        self.security.audit(
            ctx,
            "qa_acceptance_run_created",
            "qa_acceptance_run",
            run["id"],
            {
                "status": run["status"],
                "blocker_count": run["summary"]["blocker_count"],
                "missing_evidence_count": run["summary"]["missing_evidence_count"],
            },
        )
        return run

    def qa_acceptance_runs(self, ctx: RequestContext) -> list[dict[str, Any]]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
        return [row for row in self.store.list("qa_acceptance_runs") if row.get("tenant_id") == ctx.tenant_id]

    def implementation_plan(self, ctx: RequestContext) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
        return implementation_plan_payload()

    def implementation_status(self, ctx: RequestContext) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
        return build_implementation_status(self.store, ctx.tenant_id)

    def create_implementation_checkpoint(self, ctx: RequestContext, payload: dict[str, Any]) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer"})
        checkpoint = create_implementation_checkpoint(self.store, ctx.tenant_id, ctx.actor_id, payload)
        status = build_implementation_status(self.store, ctx.tenant_id)
        self.security.audit(
            ctx,
            "implementation_checkpoint_created",
            "implementation_checkpoint",
            checkpoint["id"],
            {
                "phase": checkpoint.get("phase"),
                "sprint": checkpoint.get("sprint"),
                "milestone": checkpoint.get("milestone"),
                "overall_status": status["overall_status"],
            },
        )
        return {**checkpoint, "implementation_status": status}

    def implementation_checkpoints(self, ctx: RequestContext) -> list[dict[str, Any]]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
        return [row for row in self.store.list("implementation_checkpoints") if row.get("tenant_id") == ctx.tenant_id]

    def runbook(self, ctx: RequestContext) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
        return runbook_payload()

    def runbook_status(self, ctx: RequestContext) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
        return build_runbook_status(self.store, ctx.tenant_id)

    def create_runbook_check(self, ctx: RequestContext, payload: dict[str, Any]) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer"})
        check = create_runbook_check(self.store, ctx.tenant_id, ctx.actor_id, payload)
        status = build_runbook_status(self.store, ctx.tenant_id)
        self.security.audit(
            ctx,
            "runbook_check_recorded",
            "runbook_check",
            check["id"],
            {"check_type": check.get("check_type"), "check_key": check.get("check_key"), "status": check.get("status")},
        )
        return {**check, "runbook_status": status}

    def runbook_checks(self, ctx: RequestContext) -> list[dict[str, Any]]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
        return [row for row in self.store.list("runbook_checks") if row.get("tenant_id") == ctx.tenant_id]

    def create_runbook_incident(self, ctx: RequestContext, payload: dict[str, Any]) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer"})
        incident = create_runbook_incident(self.store, ctx.tenant_id, ctx.actor_id, payload)
        status = build_runbook_status(self.store, ctx.tenant_id)
        self.security.audit(
            ctx,
            "runbook_incident_created",
            "runbook_incident",
            incident["id"],
            {"incident_type": incident.get("incident_type"), "severity": incident.get("severity"), "status": incident.get("status")},
        )
        return {**incident, "runbook_status": status}

    def resolve_runbook_incident(self, ctx: RequestContext, incident_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer"})
        try:
            incident = resolve_runbook_incident(self.store, ctx.tenant_id, incident_id, ctx.actor_id, payload)
        except KeyError:
            raise AppError("VALIDATION_ERROR", "Runbook incident does not exist", 404) from None
        status = build_runbook_status(self.store, ctx.tenant_id)
        self.security.audit(
            ctx,
            "runbook_incident_resolved",
            "runbook_incident",
            incident["id"],
            {"incident_type": incident.get("incident_type"), "severity": incident.get("severity"), "status": incident.get("status")},
        )
        return {**incident, "runbook_status": status}

    def runbook_incidents(self, ctx: RequestContext, status: str | None = None) -> list[dict[str, Any]]:
        self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
        return [
            row
            for row in self.store.list("runbook_incidents")
            if row.get("tenant_id") == ctx.tenant_id and (not status or row.get("status") == status)
        ]

    def data_dictionary(self, ctx: RequestContext) -> dict[str, Any]:
        self.security.require_role(ctx, {'owner', 'admin', 'lawyer', 'reviewer', 'auditor'})
        return data_dictionary_payload()

    def data_dictionary_status(self, ctx: RequestContext) -> dict[str, Any]:
        self.security.require_role(ctx, {'owner', 'admin', 'reviewer', 'auditor'})
        return validate_store_against_dictionary(self.store)

    def data_lineage(self, ctx: RequestContext, object_type: str, object_id: str) -> dict[str, Any]:
        lineage = build_lineage(self.store, object_type, object_id)
        business_object = lineage['business_object']
        case_id = business_object.get('case_id')
        if object_type == 'monitor_event':
            target = self.store.get('monitor_targets', business_object['monitor_target_id'])
            if not target:
                raise AppError('VALIDATION_ERROR', 'Monitor target does not exist', 404)
            case_id = target['case_id']
        if not case_id:
            raise AppError('VALIDATION_ERROR', 'Lineage object is not attached to a case', 400)
        self.security.require_case_access(ctx, case_id, 'view_data_lineage')
        return lineage

    def _link_subject_to_case(self, case_id: str, subject_id: str) -> None:
        relation_id = f"{case_id}:{subject_id}"
        if not self.store.get("subject_relations", relation_id):
            self.store.insert(
                "subject_relations",
                {
                    "id": relation_id,
                    "source_subject_id": subject_id,
                    "target_subject_id": subject_id,
                    'relation_type': 'related',
                    "strength": 1.0,
                    "source_record_id": case_id,
                    "created_at": now_iso(),
                },
            )

    def _clue_from_record(self, ctx: RequestContext, case: dict[str, Any], subject: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        score_base = {"auction": 86, "execution": 78, "company": 68}.get(record["record_type"], 60)
        clue_type = {"auction": "auction", "execution": "execution", "company": "equity"}.get(record["record_type"], "related_subject")
        title = {
            "auction": f"{subject['name']}存在司法拍卖线索",
            "execution": f"{subject['name']}新增执行公开信息",
            "company": f"{subject['name']}存在股权和关联主体线索",
        }.get(record["record_type"], f"{subject['name']}存在待核验财产线索")
        source_ref = {
            "source_name": record["source_name"],
            "source_url": record.get("source_url"),
            "source_time": record.get("record_time"),
            "fetched_at": record["fetched_at"],
            "external_record_id": record["id"],
            "snippet": str(record.get("normalized_payload", {}))[:220],
        }
        clue = {
            "id": new_id("clue"),
            "case_id": case["id"],
            "subject_id": subject["id"],
            "report_id": None,
            "clue_type": clue_type,
            "title": title,
            "description": self._record_description(record),
            "estimated_value": money_to_text(case.get("amount")) if record["record_type"] == "execution" else record.get("normalized_payload", {}).get("starting_price") or "待核验",
            "actionability_score": score_base,
            "confidence": 0.86 if record["authorization_status"] == "authorized" else 0.65,
            "source_refs": [source_ref],
            "review_status": "pending",
            "recommended_action": self._recommended_action(record["record_type"]),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.insert("asset_clues", clue)
        return clue

    def _create_report(self, ctx: RequestContext, case: dict[str, Any], subject: dict[str, Any], clues: list[dict[str, Any]], template: str) -> dict[str, Any]:
        report_id = new_id("report")
        sections = [
            "# 财产线索报告",
            f"## 被执行人主体确认\n- 主体：{subject['name']}\n- 识别状态：{subject['resolve_status']}",
            "## 执行公开信息摘要",
            self._section_for(clues, "execution"),
            "## 工商与股权结构",
            self._section_for(clues, "equity"),
            "## 对外投资与关联主体\n- 已纳入关联主体线索，需律师复核后决定是否追加调查。",
            "## 司法拍卖资产线索",
            self._section_for(clues, "auction"),
            "## 知识产权和经营权益线索\n- P0 当前未发现授权来源返回的明确线索。",
            "## 招投标/应收账款线索\n- P0 当前未发现授权来源返回的明确线索。",
            "## 疑似可追加主体或人格混同线索\n- 关联主体仅作为待核验事项，不作为最终法律判断。",
            "## 线索价值排序",
            "\n".join(f"- {clue['title']}：{clue['actionability_score']} 分，来源：{clue['source_refs'][0]['source_name']}" for clue in sorted(clues, key=lambda row: row["actionability_score"], reverse=True)),
            "## 建议执行动作",
            "\n".join(f"- {clue['recommended_action']}" for clue in clues),
            "## 待人工核验事项\n- 核验主体身份、资产权属、公告状态和执行可行性。\n- 报告发布前必须完成律师复核。",
        ]
        report = {
            "id": report_id,
            "case_id": case["id"],
            "report_type": "asset_clue",
            "title": f"{case['case_name']} - 财产线索报告",
            "content_md": "\n\n".join(sections),
            "generation_status": "review_required",
            "generated_by": "system",
            "model_invocation_id": None,
            "reviewed_by": None,
            "template": template,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.insert("reports", report)
        for clue in clues:
            self.store.update("asset_clues", clue["id"], {"report_id": report_id})
            clue["report_id"] = report_id
        return report

    def _record_description(self, record: dict[str, Any]) -> str:
        payload = record.get("normalized_payload", {})
        if record["record_type"] == "auction":
            return f"公开拍卖来源显示：{payload.get('asset_name')}，状态：{payload.get('status')}。"
        if record["record_type"] == "execution":
            return f"执行公开信息显示案件相关动态，金额：{payload.get('amount') or '待核验'}。"
        if record["record_type"] == "company":
            shareholders = payload.get("shareholders") or []
            return f"工商来源显示存在股东或关联主体：{shareholders[0]['name'] if shareholders else '待核验'}。"
        return "授权来源返回了待核验记录。"

    def _recommended_action(self, record_type: str) -> str:
        return {
            "auction": "核验拍卖资产权属、处置阶段和是否可申请参与分配。",
            "execution": "核验新增执行信息与本案关联性，判断是否并案或追加调查。",
            "company": "核验股权结构、对外投资和可追加主体线索。",
        }.get(record_type, "人工核验来源和可执行性。")

    def _section_for(self, clues: list[dict[str, Any]], clue_type: str) -> str:
        rows = [clue for clue in clues if clue["clue_type"] == clue_type]
        if not rows:
            return "- P0 当前未发现授权来源返回的明确线索。"
        return "\n".join(f"- {clue['title']}，来源：{clue['source_refs'][0]['source_name']}，建议：{clue['recommended_action']}" for clue in rows)

    def _importance(self, score: int) -> str:
        if score >= 85:
            return "critical"
        if score >= 70:
            return "high"
        if score >= 50:
            return "medium"
        return "low"

    def _create_task(self, ctx: RequestContext, case_id: str, object_type: str, object_id: str, title: str) -> dict[str, Any]:
        task = {
            "id": new_id("task"),
            "tenant_id": ctx.tenant_id,
            "case_id": case_id,
            "object_type": object_type,
            "object_id": object_id,
            "title": title,
            "status": "open",
            "assigned_to": ctx.actor_id,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.insert("tasks", task)
        return task

    def _create_monitor_event(self, ctx: RequestContext, target: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
        source_ref = {
            "source_name": "站内监控快照",
            "source_url": f"/api/monitor-targets/{target['id']}",
            "source_time": now_iso(),
            "fetched_at": now_iso(),
            "snippet": f"{subject['name']} 的监控目标已建立，后续新增执行、拍卖、股权变化会进入提醒。",
        }
        event = {
            "id": new_id("event"),
            "monitor_target_id": target["id"],
            "event_type": (target.get("event_types") or ["new_execution"])[0],
            "title": f"{subject['name']} 发现新动态",
            "importance": "high",
            "detected_at": now_iso(),
            "source_refs": [source_ref],
            "action_status": "unread",
            "recommended_action": "查看来源并决定确认、忽略或转任务。",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.insert("monitor_events", event)
        notification_id = new_id("note")
        notification = {
            "id": notification_id,
            "tenant_id": ctx.tenant_id,
            "event_id": event["id"],
            "title": event["title"],
            "why_important": "该主体被列为重点监控对象，新动态可能影响执行回款路径。",
            "deep_link": f"/mobile/notifications/{notification_id}",
            "channels": target.get("notify_channels") or ["in_app"],
            "action_buttons": ["确认", "忽略", "转任务"],
            "created_at": now_iso(),
        }
        self.store.insert("notifications", notification)
        return event

    def _review(self, ctx: RequestContext, object_type: str, object_id: str, status: str, reason: str | None) -> dict[str, Any]:
        review = {
            "id": new_id("review"),
            "tenant_id": ctx.tenant_id or TENANT_ID,
            "actor_id": ctx.actor_id,
            "object_type": object_type,
            "object_id": object_id,
            "review_status": status,
            "reason": reason,
            "created_at": now_iso(),
        }
        self.store.insert("review_records", review)
        return review

