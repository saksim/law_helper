from __future__ import annotations

import hashlib
import json
from typing import Any

from .errors import AppError
from .models import new_id, now_iso
from .services import LawPlatform

_ORIGINAL_REVIEW_CLUE = LawPlatform.review_clue
_ORIGINAL_REVIEW_REPORT = LawPlatform.review_report
_ORIGINAL_HANDLE_MONITOR_EVENT = LawPlatform.handle_monitor_event
_ORIGINAL_RUN_MONITOR_CHECK = getattr(LawPlatform, "run_monitor_check", None)
_ORIGINAL_CREATE_MONITOR_TARGET = getattr(LawPlatform, "create_monitor_target", None)
_ORIGINAL_CREATE_CONNECTOR_ALERT = getattr(LawPlatform, "create_connector_alert", None)
_ORIGINAL_CREATE_MANUAL_EXTERNAL_RECORD = getattr(LawPlatform, "create_manual_external_record", None)
_ORIGINAL_CONFIGURE_DATA_SOURCE = getattr(LawPlatform, "configure_data_source", None)


def install_p1_p2_features() -> None:
    if getattr(LawPlatform, "_p1_p2_features_installed", False):
        return
    LawPlatform.team_operations_dashboard = team_operations_dashboard
    LawPlatform.list_system_alerts = list_system_alerts
    LawPlatform.resolve_system_alert = resolve_system_alert
    LawPlatform.quality_metrics = quality_metrics
    LawPlatform.feedback_samples = feedback_samples
    LawPlatform.create_feedback_sample = create_feedback_sample
    LawPlatform.backup_checks = backup_checks
    LawPlatform.create_backup_check = create_backup_check
    LawPlatform.rotate_config = rotate_config
    LawPlatform.data_source_catalog = data_source_catalog
    LawPlatform.update_data_source_catalog = update_data_source_catalog
    LawPlatform.run_data_source_health_check = run_data_source_health_check
    LawPlatform.data_source_field_mappings = data_source_field_mappings
    LawPlatform.update_data_source_field_mappings = update_data_source_field_mappings
    LawPlatform.data_source_quality = data_source_quality
    LawPlatform.data_source_costs = data_source_costs
    LawPlatform.search_similar_cases = search_similar_cases
    LawPlatform.list_similar_cases = list_similar_cases
    LawPlatform.create_evidence_matrix = create_evidence_matrix
    LawPlatform.evidence_matrix = evidence_matrix
    LawPlatform.update_evidence_item = update_evidence_item
    LawPlatform.create_draft_document = create_draft_document
    LawPlatform.get_draft_document = get_draft_document
    LawPlatform.run_draft_quality_check = run_draft_quality_check
    LawPlatform.create_transcript_summary = create_transcript_summary
    LawPlatform.case_assistance = case_assistance
    LawPlatform.organizations = organizations
    LawPlatform.create_organization = create_organization
    LawPlatform.teams = teams
    LawPlatform.create_team = create_team
    LawPlatform.update_team_policies = update_team_policies
    LawPlatform.platform_plugins = platform_plugins
    LawPlatform.rollout_plugin = rollout_plugin
    LawPlatform.rollback_plugin = rollback_plugin
    LawPlatform.deployment_profiles = deployment_profiles
    LawPlatform.migration_runs = migration_runs
    LawPlatform.run_migration = run_migration
    LawPlatform.platform_slo = platform_slo
    LawPlatform.platform_costs = platform_costs
    LawPlatform.audit_archives = audit_archives
    LawPlatform.knowledge_nodes = knowledge_nodes
    LawPlatform.knowledge_node = knowledge_node
    LawPlatform.knowledge_graph = knowledge_graph
    LawPlatform.extract_feedback_insights = extract_feedback_insights
    LawPlatform.evaluation_runs = evaluation_runs
    LawPlatform.create_evaluation_run = create_evaluation_run
    LawPlatform.business_leads = business_leads
    LawPlatform.review_business_lead = review_business_lead
    LawPlatform.policy_alerts = policy_alerts
    LawPlatform.review_policy_alert = review_policy_alert
    LawPlatform.management_dashboard = management_dashboard
    LawPlatform.review_clue = review_clue
    LawPlatform.review_report = review_report
    LawPlatform.handle_monitor_event = handle_monitor_event
    if _ORIGINAL_RUN_MONITOR_CHECK:
        LawPlatform.run_monitor_check = run_monitor_check
    if _ORIGINAL_CREATE_MONITOR_TARGET:
        LawPlatform.create_monitor_target = create_monitor_target
    if _ORIGINAL_CREATE_CONNECTOR_ALERT:
        LawPlatform.create_connector_alert = create_connector_alert
    if _ORIGINAL_CREATE_MANUAL_EXTERNAL_RECORD:
        LawPlatform.create_manual_external_record = create_manual_external_record
    if _ORIGINAL_CONFIGURE_DATA_SOURCE:
        LawPlatform.configure_data_source = configure_data_source
    LawPlatform._p1_p2_features_installed = True


def _json_hash(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _tenant_rows(self: LawPlatform, collection: str, tenant_id: str) -> list[dict[str, Any]]:
    return [row for row in self.store.list(collection) if row.get("tenant_id") == tenant_id]


def _case_ids(self: LawPlatform, ctx) -> set[str]:
    return {case["id"] for case in self.list_cases(ctx)}


def _case_name(self: LawPlatform, case_id: str | None) -> str:
    case = self.store.get("cases", case_id or "")
    return case.get("case_name", "相关案件") if case else "相关案件"


def _ensure_default_org_team(self: LawPlatform, ctx) -> tuple[dict[str, Any], dict[str, Any]]:
    org = self.store.find_one("organizations", tenant_id=ctx.tenant_id)
    if not org:
        org = self.store.insert(
            "organizations",
            {
                "id": new_id("org"),
                "tenant_id": ctx.tenant_id,
                "name": (self.store.get("tenants", ctx.tenant_id) or {}).get("name", "默认组织"),
                "status": "active",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )
    team = self.store.find_one("teams", tenant_id=ctx.tenant_id)
    if not team:
        team = self.store.insert(
            "teams",
            {
                "id": new_id("team"),
                "tenant_id": ctx.tenant_id,
                "organization_id": org["id"],
                "name": "执行案件团队",
                "status": "active",
                "settings": {"default_notice_channel": "in_app"},
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )
    return org, team


def _create_system_alert(
    self: LawPlatform,
    ctx,
    alert_type: str,
    title: str,
    *,
    severity: str = "warning",
    status: str = "open",
    case_id: str | None = None,
    source_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alert = {
        "id": new_id("sysalert"),
        "tenant_id": ctx.tenant_id,
        "case_id": case_id,
        "source_id": source_id,
        "alert_type": alert_type,
        "severity": severity,
        "status": status,
        "title": title,
        "message": (details or {}).get("message") or title,
        "details": details or {},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    alert = self.store.insert("system_alerts", alert)
    self.security.audit(ctx, "system_alert_created", "system_alert", alert["id"], {"alert_type": alert_type, "severity": severity, "case_id": case_id, "source_id": source_id})
    return alert


def _semantic_monitor_event(event: dict[str, Any]) -> dict[str, Any]:
    diffs = event.get("field_diffs") or []
    changed = [str(diff.get("path") or diff.get("field") or "字段") for diff in diffs]
    if changed:
        summary = "、".join(changed[:4]) + "发生变化"
    else:
        summary = "监控对象出现新动态"
    impact = "可能影响执行回款路径，需要核验资产、主体或执行状态变化。"
    return {
        "semantic_summary": summary,
        "impact_assessment": impact,
        "recommended_action": event.get("recommended_action") or "查看来源，核验影响后确认、忽略或转任务。",
        "noise_feedback": event.get("noise_feedback") or {"ignored_count": 0, "acknowledged_count": 0, "task_created_count": 0, "noise_score": 0},
        "updated_at": now_iso(),
    }


def create_monitor_target(self: LawPlatform, ctx, payload: dict[str, Any]) -> dict[str, Any]:
    result = _ORIGINAL_CREATE_MONITOR_TARGET(self, ctx, payload)
    event_id = result.get("initial_event_id")
    if event_id and self.store.get("monitor_events", event_id):
        self.store.update("monitor_events", event_id, _semantic_monitor_event(self.store.get("monitor_events", event_id)))
    return result


def run_monitor_check(self: LawPlatform, ctx, target_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = _ORIGINAL_RUN_MONITOR_CHECK(self, ctx, target_id, payload)
    event = result.get("event")
    if event:
        updated = self.store.update("monitor_events", event["id"], _semantic_monitor_event(event))
        result["event"] = updated
    return result


def handle_monitor_event(self: LawPlatform, ctx, event_id: str, action: str) -> dict[str, Any]:
    result = _ORIGINAL_HANDLE_MONITOR_EVENT(self, ctx, event_id, action)
    event = result["event"]
    feedback = dict(event.get("noise_feedback") or {"ignored_count": 0, "acknowledged_count": 0, "task_created_count": 0, "noise_score": 0})
    key = {"ignore": "ignored_count", "ack": "acknowledged_count", "convert-to-task": "task_created_count"}[action]
    feedback[key] = int(feedback.get(key) or 0) + 1
    feedback["noise_score"] = max(0, int(feedback.get("ignored_count") or 0) - int(feedback.get("task_created_count") or 0))
    updated = self.store.update("monitor_events", event_id, {"noise_feedback": feedback, "updated_at": now_iso()})
    if action == "ignore":
        _persist_feedback_sample(
            self,
            ctx,
            "monitor_event",
            event_id,
            "ignored",
            {"input": event.get("semantic_summary") or event.get("title"), "output": event.get("recommended_action"), "source_refs": event.get("source_refs") or []},
        )
    result["event"] = updated
    return result


def review_clue(self: LawPlatform, ctx, clue_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = _ORIGINAL_REVIEW_CLUE(self, ctx, clue_id, payload)
    clue = result["clue"]
    if clue.get("review_status") in {"confirmed", "edited", "rejected", "task_created"}:
        _persist_feedback_sample(
            self,
            ctx,
            "asset_clue",
            clue_id,
            clue.get("review_status"),
            {"input": clue.get("description"), "output": clue.get("recommended_action"), "source_refs": clue.get("source_refs") or [], "comment": payload.get("comment")},
        )
    return result


def review_report(self: LawPlatform, ctx, report_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = _ORIGINAL_REVIEW_REPORT(self, ctx, report_id, payload)
    _persist_feedback_sample(
        self,
        ctx,
        "report",
        report_id,
        payload.get("review_status", "confirmed"),
        {"input": result.get("title"), "output": result.get("generation_status"), "comment": payload.get("comment")},
    )
    return result


def _persist_feedback_sample(self: LawPlatform, ctx, object_type: str, object_id: str, human_label: str, payload: dict[str, Any]) -> dict[str, Any]:
    existing = self.store.find_one("feedback_samples", tenant_id=ctx.tenant_id, object_type=object_type, object_id=object_id, human_label=human_label)
    if existing:
        return existing
    sample = {
        "id": new_id("sample"),
        "tenant_id": ctx.tenant_id,
        "case_id": payload.get("case_id"),
        "object_type": object_type,
        "object_id": object_id,
        "human_label": human_label,
        "input_summary": str(payload.get("input") or "")[:500],
        "output_summary": str(payload.get("output") or "")[:500],
        "source_refs": payload.get("source_refs") or [],
        "comment": payload.get("comment"),
        "sensitivity_level": payload.get("sensitivity_level", "L2"),
        "model_policy": "private_or_local_required_for_L3_L4",
        "created_by": ctx.actor_id,
        "created_at": now_iso(),
    }
    return self.store.insert("feedback_samples", sample)


def team_operations_dashboard(self: LawPlatform, ctx, status: str | None = None, case_id: str | None = None) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer", "auditor"})
    visible_ids = _case_ids(self, ctx)
    if case_id:
        self.security.require_case_access(ctx, case_id, "team_operations_dashboard")
        visible_ids &= {case_id}
    cases = [case for case in self.store.list("cases") if case.get("tenant_id") == ctx.tenant_id and case.get("id") in visible_ids and (not status or case.get("status") == status)]
    case_ids = {case["id"] for case in cases}
    clues = [row for row in self.store.list("asset_clues") if row.get("case_id") in case_ids]
    reports = [row for row in self.store.list("reports") if row.get("case_id") in case_ids]
    tasks = [row for row in self.store.list("tasks") if row.get("case_id") in case_ids]
    jobs = [row for row in self.store.list("jobs") if row.get("case_id") in case_ids or row.get("tenant_id") == ctx.tenant_id]
    alerts = [row for row in self.store.list("system_alerts") if row.get("tenant_id") == ctx.tenant_id and (not row.get("case_id") or row.get("case_id") in case_ids) and row.get("status") != "resolved"]
    connector_alerts = [row for row in self.store.list("connector_alerts") if row.get("case_id") in case_ids and row.get("status") in {"open", "retry_exhausted"}]
    return {
        "summary": {
            "case_count": len(cases),
            "clue_count": len(clues),
            "pending_clue_count": len([row for row in clues if row.get("review_status") == "pending"]),
            "report_count": len(reports),
            "pending_report_count": len([row for row in reports if row.get("generation_status") == "review_required"]),
            "open_task_count": len([row for row in tasks if row.get("status") == "open"]),
            "running_job_count": len([row for row in jobs if row.get("status") in {"queued", "running"}]),
            "open_alert_count": len(alerts) + len(connector_alerts),
        },
        "cases": cases,
        "alerts": alerts,
        "connector_alerts": connector_alerts,
        "quality": quality_metrics(self, ctx, case_id=case_id),
    }


def list_system_alerts(self: LawPlatform, ctx, status: str | None = None) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer", "auditor"})
    return [row for row in _tenant_rows(self, "system_alerts", ctx.tenant_id) if not status or row.get("status") == status]


def resolve_system_alert(self: LawPlatform, ctx, alert_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer"})
    alert = self.store.get("system_alerts", alert_id)
    if not alert or alert.get("tenant_id") != ctx.tenant_id:
        raise AppError("VALIDATION_ERROR", "System alert does not exist", 404)
    updated = self.store.update("system_alerts", alert_id, {"status": "resolved", "resolution": payload.get("resolution", "resolved"), "resolved_by": ctx.actor_id, "resolved_at": now_iso(), "updated_at": now_iso()})
    self.security.audit(ctx, "system_alert_resolved", "system_alert", alert_id, {"resolution": updated.get("resolution")})
    return updated


def quality_metrics(self: LawPlatform, ctx, case_id: str | None = None) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer", "auditor"})
    visible_ids = _case_ids(self, ctx)
    if case_id:
        self.security.require_case_access(ctx, case_id, "quality_metrics")
        visible_ids &= {case_id}
    files = [row for row in self.store.list("case_files") if row.get("case_id") in visible_ids]
    blocks = [row for row in self.store.list("document_blocks") if any(file["id"] == row.get("file_id") for file in files)]
    clues = [row for row in self.store.list("asset_clues") if row.get("case_id") in visible_ids]
    reports = [row for row in self.store.list("reports") if row.get("case_id") in visible_ids]
    deliveries = _tenant_rows(self, "notification_deliveries", ctx.tenant_id)
    metrics = {
        "parse_success_rate": _ratio(len([row for row in files if row.get("parse_status") in {"done", "review_required"}]), len(files)),
        "low_confidence_ratio": _ratio(len([row for row in blocks if float(row.get("confidence") or 0) < 0.75]), len(blocks)),
        "clue_confirmation_rate": _ratio(len([row for row in clues if row.get("review_status") in {"confirmed", "task_created"}]), len(clues)),
        "report_rejection_rate": _ratio(len([row for row in reports if row.get("review_comment") and row.get("generation_status") == "review_required"]), len(reports)),
        "notification_delivery_rate": _ratio(len([row for row in deliveries if row.get("delivery_status") in {"recorded", "sent"}]), len(deliveries)),
        "feedback_sample_count": len(_tenant_rows(self, "feedback_samples", ctx.tenant_id)),
    }
    for key, value in metrics.items():
        self.store.insert("quality_metrics", {"id": new_id("metric"), "tenant_id": ctx.tenant_id, "case_id": case_id, "metric_key": key, "metric_value": value, "created_at": now_iso()})
    return {"case_id": case_id, "metrics": metrics, "generated_at": now_iso()}


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(numerator / denominator, 4)


def feedback_samples(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
    for record in _tenant_rows(self, "feedback_records", ctx.tenant_id):
        _persist_feedback_sample(
            self,
            ctx,
            record.get("object_type", "feedback"),
            record.get("object_id", record["id"]),
            record.get("usefulness") or "feedback",
            {"input": record.get("reason"), "output": record.get("usefulness"), "comment": record.get("reason")},
        )
    return _tenant_rows(self, "feedback_samples", ctx.tenant_id)


def create_feedback_sample(self: LawPlatform, ctx, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer"})
    sample = _persist_feedback_sample(self, ctx, payload["object_type"], payload["object_id"], payload["human_label"], payload)
    self.security.audit(ctx, "feedback_sample_created", "feedback_sample", sample["id"], {"object_type": sample["object_type"], "human_label": sample["human_label"]})
    return sample


def backup_checks(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
    return _tenant_rows(self, "backup_checks", ctx.tenant_id)


def create_backup_check(self: LawPlatform, ctx, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "reviewer"})
    check = {
        "id": new_id("backup"),
        "tenant_id": ctx.tenant_id,
        "actor_id": ctx.actor_id,
        "status": payload.get("status", "passed"),
        "backup_scope": payload.get("backup_scope", "database_and_files"),
        "restore_drill_status": payload.get("restore_drill_status", "not_run"),
        "evidence_refs": payload.get("evidence_refs") or {},
        "notes": payload.get("notes"),
        "created_at": now_iso(),
    }
    check = self.store.insert("backup_checks", check)
    if check["status"] != "passed":
        _create_system_alert(self, ctx, "backup_check_failed", "备份或恢复演练未通过", severity="critical", details=check)
    self.security.audit(ctx, "backup_check_recorded", "backup_check", check["id"], {"status": check["status"], "restore_drill_status": check["restore_drill_status"]})
    return check


def rotate_config(self: LawPlatform, ctx, config_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    config_type = payload.get("config_type") or "data_source"
    collection = "notification_channel_configs" if config_type == "notification_channel" else "data_source_configs"
    row = self.store.get(collection, config_id) or next((item for item in self.store.list(collection) if item.get("connector_id") == config_id or item.get("channel") == config_id), None)
    if not row:
        raise AppError("VALIDATION_ERROR", "Config does not exist", 404)
    generation = int(row.get("rotation_generation") or 0) + 1
    updated = self.store.update(collection, row["id"], {"rotation_generation": generation, "rotated_at": now_iso(), "updated_at": now_iso()})
    rotation = {
        "id": new_id("rotation"),
        "tenant_id": ctx.tenant_id,
        "actor_id": ctx.actor_id,
        "config_id": config_id,
        "config_type": config_type,
        "masked_config": _mask_config(updated),
        "rotation_generation": generation,
        "created_at": now_iso(),
    }
    rotation = self.store.insert("config_rotations", rotation)
    self.security.audit(ctx, "config_rotated", "config", config_id, {"config_type": config_type, "rotation_generation": generation})
    return rotation


def _mask_config(row: dict[str, Any]) -> dict[str, Any]:
    masked = {}
    for key, value in row.items():
        if any(token in str(key).lower() for token in ["key", "token", "secret", "password", "webhook"]):
            masked[key] = "***" if value else value
        else:
            masked[key] = value
    return masked


def create_connector_alert(self: LawPlatform, ctx, case: dict[str, Any], subject: dict[str, Any], connector_id: str, exc: AppError) -> dict[str, Any]:
    alert = _ORIGINAL_CREATE_CONNECTOR_ALERT(self, ctx, case, subject, connector_id, exc)
    _create_system_alert(self, ctx, "connector_failed", f"数据源 {connector_id} 调用失败", case_id=case["id"], source_id=connector_id, details={"message": exc.message, "error_code": exc.code, "connector_alert_id": alert["id"]})
    return alert


def configure_data_source(self: LawPlatform, ctx, connector_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    config = _ORIGINAL_CONFIGURE_DATA_SOURCE(self, ctx, connector_id, payload)
    update_data_source_catalog(self, ctx, connector_id, {"authorization_status": "authorized" if config.get("enabled") else "unknown", "status": "active" if config.get("enabled") else "disabled", "config_id": config["id"]})
    return config


def data_source_catalog(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    existing = {row.get("source_id"): row for row in _tenant_rows(self, "data_source_catalog", ctx.tenant_id)}
    rows: list[dict[str, Any]] = []
    for plugin in self.plugins.list_plugins():
        if plugin.get("plugin_type") != "DataConnector":
            continue
        config = next((row for row in self.store.list("data_source_configs") if row.get("tenant_id") == ctx.tenant_id and row.get("connector_id") == plugin["plugin_id"]), None)
        row = existing.get(plugin["plugin_id"])
        if not row:
            row = self.store.insert(
                "data_source_catalog",
                {
                    "id": new_id("source"),
                    "tenant_id": ctx.tenant_id,
                    "source_id": plugin["plugin_id"],
                    "source_name": plugin["plugin_name"],
                    "authorization_status": "manual" if plugin["plugin_id"] == "manual_company_connector" else "unknown",
                    "status": "active" if plugin.get("enabled") else "disabled",
                    "billing_model": (plugin.get("cost") or {}).get("billing_model", "unknown"),
                    "field_mapping_version": (plugin.get("lineage") or {}).get("field_mapping_version", "v1"),
                    "required_fields": (plugin.get("quality") or {}).get("required_fields", []),
                    "frequency_limit": plugin.get("rate_limit", {}),
                    "config_id": config.get("id") if config else None,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
            )
        rows.append({**row, "plugin": plugin, "config": _mask_config(config or {})})
    return rows


def update_data_source_catalog(self: LawPlatform, ctx, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    catalog = self.store.find_one("data_source_catalog", tenant_id=ctx.tenant_id, source_id=source_id)
    updates = {
        "source_id": source_id,
        "source_name": payload.get("source_name") or source_id,
        "authorization_status": payload.get("authorization_status", "unknown"),
        "status": payload.get("status", "active"),
        "billing_model": payload.get("billing_model", "unknown"),
        "config_id": payload.get("config_id"),
        "updated_at": now_iso(),
    }
    if catalog:
        row = self.store.update("data_source_catalog", catalog["id"], updates)
    else:
        row = self.store.insert("data_source_catalog", {"id": new_id("source"), "tenant_id": ctx.tenant_id, "created_at": now_iso(), **updates})
    self.security.audit(ctx, "data_source_catalog_updated", "data_source", source_id, {"status": row.get("status"), "authorization_status": row.get("authorization_status")})
    return row


def run_data_source_health_check(self: LawPlatform, ctx, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    status = payload.get("status")
    if not status:
        contract = self.plugins.run_contract_tests(source_id)
        status = "passed" if contract["status"] == "passed" else "failed"
    check = {
        "id": new_id("health"),
        "tenant_id": ctx.tenant_id,
        "source_id": source_id,
        "status": status,
        "latency_ms": payload.get("latency_ms", 0),
        "error_rate": payload.get("error_rate", 0),
        "message": payload.get("message"),
        "created_at": now_iso(),
    }
    check = self.store.insert("connector_health_checks", check)
    if status != "passed":
        _create_system_alert(self, ctx, "connector_health_failed", f"数据源 {source_id} 健康检查失败", source_id=source_id, details=check)
    self.security.audit(ctx, "data_source_health_checked", "data_source", source_id, {"status": status})
    return check


def data_source_field_mappings(self: LawPlatform, ctx, source_id: str) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    row = self.store.find_one("field_mappings", tenant_id=ctx.tenant_id, source_id=source_id)
    if row:
        return row
    default = {
        "id": new_id("mapping"),
        "tenant_id": ctx.tenant_id,
        "source_id": source_id,
        "mapping_version": "v1",
        "mappings": {
            "source_name": "source_name",
            "source_url": "source_url",
            "record_type": "record_type",
            "record_time": "record_time",
            "fetched_at": "fetched_at",
            "normalized_payload": "normalized_payload",
            "authorization_status": "authorization_status",
        },
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    return self.store.insert("field_mappings", default)


def update_data_source_field_mappings(self: LawPlatform, ctx, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    row = data_source_field_mappings(self, ctx, source_id)
    updated = self.store.update("field_mappings", row["id"], {"mapping_version": payload.get("mapping_version", row["mapping_version"]), "mappings": payload.get("mappings", row["mappings"]), "updated_at": now_iso()})
    self.security.audit(ctx, "field_mapping_updated", "data_source", source_id, {"mapping_version": updated["mapping_version"]})
    return updated


def data_source_quality(self: LawPlatform, ctx, source_id: str) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "auditor", "lawyer", "reviewer"})
    records = [row for row in self.store.list("external_records") if row.get("connector_id") == source_id]
    required = ["source_name", "source_url", "record_type", "record_time", "fetched_at", "normalized_payload", "authorization_status"]
    completeness = _ratio(sum(1 for record in records for field in required if record.get(field) not in (None, "")), max(1, len(records) * len(required)))
    authorized = _ratio(len([row for row in records if row.get("authorization_status") in {"authorized", "manual", "public"}]), len(records))
    health = [row for row in _tenant_rows(self, "connector_health_checks", ctx.tenant_id) if row.get("source_id") == source_id]
    stability = _ratio(len([row for row in health if row.get("status") == "passed"]), len(health)) if health else 1.0
    freshness = 1.0 if records else 0.0
    score = round((completeness * 35) + (authorized * 25) + (stability * 25) + (freshness * 15), 2)
    result = {
        "id": new_id("quality"),
        "tenant_id": ctx.tenant_id,
        "source_id": source_id,
        "score": score,
        "breakdown": {"completeness": completeness, "authorization": authorized, "stability": stability, "freshness": freshness},
        "record_count": len(records),
        "created_at": now_iso(),
    }
    self.store.insert("data_quality_scores", result)
    return result


def data_source_costs(self: LawPlatform, ctx) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    rows = _tenant_rows(self, "source_cost_records", ctx.tenant_id)
    by_source: dict[str, dict[str, Any]] = {}
    for run in _tenant_rows(self, "plugin_runs", ctx.tenant_id):
        plugin = self.plugins.get(run["plugin_id"])
        if plugin.get("plugin_type") != "DataConnector":
            continue
        source = by_source.setdefault(run["plugin_id"], {"source_id": run["plugin_id"], "call_count": 0, "failed_count": 0, "amount": 0.0})
        source["call_count"] += 1
        if run.get("status") != "success":
            source["failed_count"] += 1
    for row in rows:
        source = by_source.setdefault(row["source_id"], {"source_id": row["source_id"], "call_count": 0, "failed_count": 0, "amount": 0.0})
        source["amount"] += float(row.get("amount") or 0)
    return {"sources": list(by_source.values()), "total_amount": round(sum(row["amount"] for row in by_source.values()), 2)}


def create_manual_external_record(self: LawPlatform, ctx, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = _ORIGINAL_CREATE_MANUAL_EXTERNAL_RECORD(self, ctx, case_id, payload)
    record = result["external_record"]
    attachments = payload.get("attachments") or []
    for item in attachments:
        self.store.insert(
            "manual_record_attachments",
            {
                "id": new_id("attach"),
                "tenant_id": ctx.tenant_id,
                "external_record_id": record["id"],
                "attachment_type": item.get("attachment_type", "screenshot"),
                "uri": item.get("uri"),
                "description": item.get("description"),
                "reviewed_by": payload.get("reviewed_by") or ctx.actor_id,
                "created_at": now_iso(),
            },
        )
    return result


def search_similar_cases(self: LawPlatform, ctx, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    case = self.security.require_case_access(ctx, case_id, "similar_case_search")
    self.security.check_model_policy(ctx, case_id, "L2", provider_external=False)
    source_ref = {"source_name": payload.get("source_name", "内部授权案例库"), "source_url": payload.get("source_url", f"internal://similar-cases/{case_id}"), "source_time": now_iso()}
    candidates = payload.get("candidates") or [
        {"title": f"{case.get('cause_of_action') or '执行'}相关执行异议案例", "court": "示例法院", "similarity": 0.82, "holding": "支持继续执行的因素包括主体一致、债权明确、财产状态可核验。"},
        {"title": "财产线索核验与追加被执行人案例", "court": "示例法院", "similarity": 0.76, "holding": "追加主体需要证据证明财产混同或出资瑕疵。"},
    ]
    rows = []
    for candidate in candidates:
        row = self.store.insert(
            "similar_cases",
            {
                "id": new_id("simcase"),
                "tenant_id": ctx.tenant_id,
                "case_id": case_id,
                "title": candidate["title"],
                "court": candidate.get("court"),
                "similarity": candidate.get("similarity", 0.7),
                "similar_points": candidate.get("similar_points", ["案由和执行阶段相近", "均涉及财产线索核验"]),
                "differences": candidate.get("differences", ["需核验地域和主体差异"]),
                "summary": candidate.get("holding"),
                "source_ref": candidate.get("source_ref") or source_ref,
                "review_status": "pending",
                "created_at": now_iso(),
            },
        )
        rows.append(row)
    argument = self.store.insert(
        "legal_arguments",
        {
            "id": new_id("arg"),
            "tenant_id": ctx.tenant_id,
            "case_id": case_id,
            "argument_type": "裁判倾向摘要",
            "supporting_factors": ["来源案例均要求主体和财产线索可追溯", "执行路径需要律师复核"],
            "opposing_factors": ["公开案例不能直接替代本案事实判断"],
            "source_ref": source_ref,
            "created_at": now_iso(),
        },
    )
    self.security.audit(ctx, "similar_cases_searched", "case", case_id, {"result_count": len(rows)})
    return {"similar_cases": rows, "legal_argument": argument}


def list_similar_cases(self: LawPlatform, ctx, case_id: str) -> list[dict[str, Any]]:
    self.security.require_case_access(ctx, case_id, "list_similar_cases")
    return [row for row in _tenant_rows(self, "similar_cases", ctx.tenant_id) if row.get("case_id") == case_id]


def create_evidence_matrix(self: LawPlatform, ctx, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_case_access(ctx, case_id, "create_evidence_matrix")
    claims = payload.get("fact_claims") or ["被执行主体身份", "执行依据与金额", "财产线索来源"]
    file_rows = [row for row in self.store.list("case_files") if row.get("case_id") == case_id]
    evidence_items = []
    for file in file_rows:
        item = self.store.insert(
            "evidence_items",
            {
                "id": new_id("evidence"),
                "tenant_id": ctx.tenant_id,
                "case_id": case_id,
                "file_id": file["id"],
                "title": payload.get("title") or file["original_name"],
                "proof_purpose": "证明案件事实或执行依据",
                "status": "pending",
                "source_ref": {"source_name": file["original_name"], "source_url": file.get("storage_path"), "page_no": 1},
                "suggested_name": f"证据-{file.get('file_type', '材料')}-{file['original_name']}",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )
        evidence_items.append(item)
    rows = []
    for claim in claims:
        matched = evidence_items[:1]
        row = self.store.insert(
            "evidence_matrix_rows",
            {
                "id": new_id("matrix"),
                "tenant_id": ctx.tenant_id,
                "case_id": case_id,
                "fact_claim": claim,
                "evidence_ids": [item["id"] for item in matched],
                "proof_purpose": "支撑事实主张",
                "gap": None if matched else "缺少证据",
                "status": "pending" if matched else "missing",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )
        rows.append(row)
    report = self.store.insert(
        "reports",
        {
            "id": new_id("report"),
            "case_id": case_id,
            "report_type": "evidence_matrix",
            "title": "证据矩阵",
            "content_md": "\n".join(f"- {row['fact_claim']}：{row['status']}" for row in rows),
            "generation_status": "review_required",
            "generated_by": "system",
            "model_invocation_id": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
    )
    self.security.audit(ctx, "evidence_matrix_created", "case", case_id, {"row_count": len(rows), "report_id": report["id"]})
    return {"evidence_items": evidence_items, "matrix_rows": rows, "report": report}


def evidence_matrix(self: LawPlatform, ctx, case_id: str) -> dict[str, Any]:
    self.security.require_case_access(ctx, case_id, "view_evidence_matrix")
    return {
        "evidence_items": [row for row in _tenant_rows(self, "evidence_items", ctx.tenant_id) if row.get("case_id") == case_id],
        "matrix_rows": [row for row in _tenant_rows(self, "evidence_matrix_rows", ctx.tenant_id) if row.get("case_id") == case_id],
    }


def update_evidence_item(self: LawPlatform, ctx, evidence_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    item = self.store.get("evidence_items", evidence_id)
    if not item or item.get("tenant_id") != ctx.tenant_id:
        raise AppError("VALIDATION_ERROR", "Evidence item does not exist", 404)
    self.security.require_case_access(ctx, item["case_id"], "update_evidence_item")
    updates = {key: value for key, value in payload.items() if key in {"title", "proof_purpose", "status", "suggested_name"} and value is not None}
    updates["updated_at"] = now_iso()
    updated = self.store.update("evidence_items", evidence_id, updates)
    self.security.audit(ctx, "evidence_item_updated", "evidence_item", evidence_id, {"fields": sorted(updates)})
    return updated


def create_draft_document(self: LawPlatform, ctx, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    case = self.security.require_case_access(ctx, case_id, "create_draft_document")
    self.security.check_model_policy(ctx, case_id, "L2", provider_external=False)
    evidence = evidence_matrix(self, ctx, case_id)["evidence_items"]
    clues = [row for row in self.store.list("asset_clues") if row.get("case_id") == case_id]
    template = payload.get("template", "execution_application")
    citations = [item.get("source_ref") for item in evidence[:5]] + [ref for clue in clues[:5] for ref in clue.get("source_refs", [])[:1]]
    content = [
        f"# {payload.get('title') or '执行辅助文书初稿'}",
        f"案件：{case['case_name']}",
        "## 事实依据",
        "\n".join(f"- {item['title']}：{item.get('proof_purpose')}" for item in evidence) or "- 待补充证据。",
        "## 财产线索",
        "\n".join(f"- {clue['title']}：{clue.get('recommended_action')}" for clue in clues) or "- 暂无线索。",
        "## 律师复核",
        "- 本文书为辅助初稿，必须由执业律师复核后使用。",
    ]
    draft = self.store.insert(
        "draft_documents",
        {
            "id": new_id("draft"),
            "tenant_id": ctx.tenant_id,
            "case_id": case_id,
            "template": template,
            "title": payload.get("title") or "执行辅助文书初稿",
            "content_md": "\n\n".join(content),
            "citations": citations,
            "review_status": "pending",
            "created_by": ctx.actor_id,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
    )
    self.security.audit(ctx, "draft_document_created", "draft_document", draft["id"], {"template": template, "citation_count": len(citations)})
    return draft


def get_draft_document(self: LawPlatform, ctx, draft_id: str) -> dict[str, Any]:
    draft = self.store.get("draft_documents", draft_id)
    if not draft or draft.get("tenant_id") != ctx.tenant_id:
        raise AppError("VALIDATION_ERROR", "Draft document does not exist", 404)
    self.security.require_case_access(ctx, draft["case_id"], "view_draft_document")
    return draft


def run_draft_quality_check(self: LawPlatform, ctx, draft_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    draft = get_draft_document(self, ctx, draft_id)
    content = draft.get("content_md", "")
    issue_types = ["subject_consistency", "amount_consistency", "date_consistency", "evidence_number_consistency"]
    issues = []
    for issue_type in issue_types:
        if issue_type == "evidence_number_consistency" and not draft.get("citations"):
            issues.append({"issue_type": issue_type, "severity": "warning", "message": "文书缺少证据引用编号或来源。", "source_ref": None})
        elif issue_type != "evidence_number_consistency" and "待补充" in content:
            issues.append({"issue_type": issue_type, "severity": "warning", "message": "存在待补充内容，需要律师确认。", "source_ref": (draft.get("citations") or [None])[0]})
        else:
            issues.append({"issue_type": issue_type, "severity": "info", "message": "未发现明显不一致，仍需律师复核。", "source_ref": (draft.get("citations") or [None])[0]})
    check = self.store.insert(
        "document_quality_checks",
        {
            "id": new_id("doccheck"),
            "tenant_id": ctx.tenant_id,
            "draft_id": draft_id,
            "case_id": draft["case_id"],
            "status": "review_required" if any(item["severity"] == "warning" for item in issues) else "passed",
            "issues": issues,
            "created_at": now_iso(),
        },
    )
    self.security.audit(ctx, "draft_quality_checked", "draft_document", draft_id, {"status": check["status"], "issue_count": len(issues)})
    return check


def create_transcript_summary(self: LawPlatform, ctx, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_case_access(ctx, case_id, "create_transcript_summary")
    text = payload.get("transcript_text", "")
    snippets = [line.strip() for line in text.splitlines() if line.strip()][:5]
    summary = "；".join(snippets[:3]) if snippets else "未提供可摘要文本。"
    row = self.store.insert(
        "transcript_summaries",
        {
            "id": new_id("transcript"),
            "tenant_id": ctx.tenant_id,
            "case_id": case_id,
            "summary": summary,
            "snippets": snippets,
            "source_ref": payload.get("source_ref") or {"source_name": payload.get("source_name", "人工上传笔录"), "source_url": f"case://{case_id}/transcript"},
            "review_status": "pending",
            "created_by": ctx.actor_id,
            "created_at": now_iso(),
        },
    )
    self.security.audit(ctx, "transcript_summary_created", "transcript_summary", row["id"], {"case_id": case_id})
    return row


def case_assistance(self: LawPlatform, ctx, case_id: str) -> dict[str, Any]:
    self.security.require_case_access(ctx, case_id, "case_assistance")
    return {
        "similar_cases": list_similar_cases(self, ctx, case_id),
        "legal_arguments": [row for row in _tenant_rows(self, "legal_arguments", ctx.tenant_id) if row.get("case_id") == case_id],
        "evidence_matrix": evidence_matrix(self, ctx, case_id),
        "draft_documents": [row for row in _tenant_rows(self, "draft_documents", ctx.tenant_id) if row.get("case_id") == case_id],
        "transcript_summaries": [row for row in _tenant_rows(self, "transcript_summaries", ctx.tenant_id) if row.get("case_id") == case_id],
    }


def organizations(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    _ensure_default_org_team(self, ctx)
    return _tenant_rows(self, "organizations", ctx.tenant_id)


def create_organization(self: LawPlatform, ctx, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    org = self.store.insert("organizations", {"id": new_id("org"), "tenant_id": ctx.tenant_id, "name": payload["name"], "status": payload.get("status", "active"), "settings": payload.get("settings", {}), "created_at": now_iso(), "updated_at": now_iso()})
    self.security.audit(ctx, "organization_created", "organization", org["id"], {"name": org["name"]})
    return org


def teams(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    _ensure_default_org_team(self, ctx)
    return _tenant_rows(self, "teams", ctx.tenant_id)


def create_team(self: LawPlatform, ctx, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    org, _team = _ensure_default_org_team(self, ctx)
    team = self.store.insert("teams", {"id": new_id("team"), "tenant_id": ctx.tenant_id, "organization_id": payload.get("organization_id") or org["id"], "name": payload["name"], "status": payload.get("status", "active"), "settings": payload.get("settings", {}), "created_at": now_iso(), "updated_at": now_iso()})
    self.security.audit(ctx, "team_created", "team", team["id"], {"name": team["name"]})
    return team


def update_team_policies(self: LawPlatform, ctx, team_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    team = self.store.get("teams", team_id)
    if not team or team.get("tenant_id") != ctx.tenant_id:
        raise AppError("VALIDATION_ERROR", "Team does not exist", 404)
    existing = self.store.find_one("tenant_policies", tenant_id=ctx.tenant_id, scope_type="team", scope_id=team_id)
    data = {"scope_type": "team", "scope_id": team_id, "policies": payload.get("policies", {}), "updated_at": now_iso()}
    if existing:
        policy = self.store.update("tenant_policies", existing["id"], data)
    else:
        policy = self.store.insert("tenant_policies", {"id": new_id("policy"), "tenant_id": ctx.tenant_id, "created_at": now_iso(), **data})
    self.security.audit(ctx, "team_policy_updated", "team", team_id, {"policy_keys": sorted(policy.get("policies", {}))})
    return policy


def platform_plugins(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    versions = _tenant_rows(self, "plugin_versions", ctx.tenant_id)
    by_plugin: dict[str, list[dict[str, Any]]] = {}
    for row in versions:
        by_plugin.setdefault(row["plugin_id"], []).append(row)
    return [{**plugin, "version_history": by_plugin.get(plugin["plugin_id"], [])} for plugin in self.plugins.list_plugins()]


def rollout_plugin(self: LawPlatform, ctx, plugin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    plugin = self.plugins.get(plugin_id)
    contract = self.plugins.run_contract_tests(plugin_id, include_feature_flag=False)
    status = "rolled_out" if contract["status"] == "passed" else "blocked"
    version = payload.get("version") or plugin.get("version")
    row = self.store.insert("plugin_versions", {"id": new_id("plugver"), "tenant_id": ctx.tenant_id, "plugin_id": plugin_id, "version": version, "status": status, "rollout_percent": payload.get("rollout_percent", 10), "contract_result": contract, "created_at": now_iso()})
    if status == "rolled_out":
        self.store.update("plugin_registry", plugin["id"], {"active_version": version, "last_rollout": row, "updated_at": now_iso()})
    self.security.audit(ctx, "plugin_rollout_recorded", "plugin", plugin_id, {"version": version, "status": status})
    return row


def rollback_plugin(self: LawPlatform, ctx, plugin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    plugin = self.plugins.enable_by_plugin_id(plugin_id, False)
    row = self.store.insert("plugin_versions", {"id": new_id("plugver"), "tenant_id": ctx.tenant_id, "plugin_id": plugin_id, "version": payload.get("rollback_to_version") or plugin.get("active_version") or plugin.get("version"), "status": "rolled_back", "rollback_state": plugin.get("last_rollback"), "created_at": now_iso()})
    self.security.audit(ctx, "plugin_rollback_recorded", "plugin", plugin_id, {"version": row["version"]})
    return row


def deployment_profiles(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    rows = _tenant_rows(self, "deployment_profiles", ctx.tenant_id)
    if rows:
        return rows
    defaults = [
        {"profile_name": "standard-cloud", "profile_type": "cloud", "environment_variables": ["DATABASE_URL", "OBJECT_STORE_BUCKET", "MODEL_POLICY"], "supports_customer_keys": False},
        {"profile_name": "private-deployment", "profile_type": "private", "environment_variables": ["DATABASE_URL", "OBJECT_STORE_BUCKET", "CUSTOMER_KMS_KEY", "MODEL_POLICY"], "supports_customer_keys": True},
    ]
    return [
        self.store.insert("deployment_profiles", {"id": new_id("deploy"), "tenant_id": ctx.tenant_id, "created_at": now_iso(), **row})
        for row in defaults
    ]


def migration_runs(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    return _tenant_rows(self, "migration_runs", ctx.tenant_id)


def run_migration(self: LawPlatform, ctx, version: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin"})
    dry_run = bool(payload.get("dry_run", True))
    run = self.store.insert("migration_runs", {"id": new_id("migration"), "tenant_id": ctx.tenant_id, "version": version, "status": "dry_run_passed" if dry_run else "succeeded", "dry_run": dry_run, "steps": payload.get("steps", ["schema_check", "config_check", "rollback_plan_check"]), "rollback_plan": payload.get("rollback_plan", "restore previous compatible version and config snapshot"), "created_at": now_iso()})
    self.security.audit(ctx, "migration_run_recorded", "migration", run["id"], {"version": version, "dry_run": dry_run, "status": run["status"]})
    return run


def platform_slo(self: LawPlatform, ctx) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    jobs = _tenant_rows(self, "jobs", ctx.tenant_id)
    deliveries = _tenant_rows(self, "notification_deliveries", ctx.tenant_id)
    files = self.store.list("case_files")
    metrics = {
        "availability": 1.0,
        "task_delay_status": "passed" if not [row for row in jobs if row.get("status") == "failed"] else "warning",
        "notification_delivery_rate": _ratio(len([row for row in deliveries if row.get("delivery_status") in {"recorded", "sent"}]), len(deliveries)),
        "parse_success_rate": _ratio(len([row for row in files if row.get("parse_status") in {"done", "review_required"}]), len(files)),
        "error_rate": _ratio(len([row for row in jobs if row.get("status") == "failed"]), len(jobs)),
    }
    rows = []
    for key, value in metrics.items():
        status = "passed" if value == 1.0 or value == "passed" else "warning"
        rows.append(self.store.insert("slo_metrics", {"id": new_id("slo"), "tenant_id": ctx.tenant_id, "metric_key": key, "metric_value": value, "status": status, "created_at": now_iso()}))
    return {"metrics": metrics, "records": rows}


def platform_costs(self: LawPlatform, ctx) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    source_cost = data_source_costs(self, ctx)
    model_cost = sum(float(row.get("cost") or 0) for row in _tenant_rows(self, "model_invocations", ctx.tenant_id))
    storage_cost = len(self.store.list("case_files")) * 0.01
    notification_cost = len(_tenant_rows(self, "notification_deliveries", ctx.tenant_id)) * 0.001
    costs = {"data_sources": source_cost["total_amount"], "models": model_cost, "storage": round(storage_cost, 2), "notifications": round(notification_cost, 3)}
    total = round(sum(costs.values()), 3)
    self.store.insert("cost_records", {"id": new_id("cost"), "tenant_id": ctx.tenant_id, "cost_type": "platform_total", "amount": total, "breakdown": costs, "created_at": now_iso()})
    return {"costs": costs, "total_amount": total}


def audit_archives(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "auditor"})
    logs = _tenant_rows(self, "audit_logs", ctx.tenant_id)
    digest = _json_hash(logs)
    existing = self.store.find_one("audit_archives", tenant_id=ctx.tenant_id, integrity_hash=digest)
    if not existing:
        existing = self.store.insert("audit_archives", {"id": new_id("archive"), "tenant_id": ctx.tenant_id, "archive_scope": "tenant", "record_count": len(logs), "integrity_hash": digest, "created_at": now_iso()})
    return _tenant_rows(self, "audit_archives", ctx.tenant_id)


def _ensure_knowledge(self: LawPlatform, ctx) -> None:
    if self.store.find_one("knowledge_nodes", tenant_id=ctx.tenant_id):
        return
    node_ids: dict[str, str] = {}
    for case in self.list_cases(ctx):
        node = self.store.insert("knowledge_nodes", {"id": new_id("knode"), "tenant_id": ctx.tenant_id, "node_type": "case", "title": case["case_name"], "source_ref": {"source_name": "case", "source_url": f"/api/cases/{case['id']}"}, "sensitivity_level": "L2", "authorization_scope": "tenant", "created_at": now_iso()})
        node_ids[f"case:{case['id']}"] = node["id"]
    for subject in _tenant_rows(self, "subjects", ctx.tenant_id):
        node = self.store.insert("knowledge_nodes", {"id": new_id("knode"), "tenant_id": ctx.tenant_id, "node_type": "subject", "title": subject["name"], "source_ref": {"source_name": "subject", "source_url": f"/api/subjects/{subject['id']}"}, "sensitivity_level": "L1", "authorization_scope": "tenant", "created_at": now_iso()})
        node_ids[f"subject:{subject['id']}"] = node["id"]
    for clue in self.store.list("asset_clues"):
        if clue.get("case_id") not in _case_ids(self, ctx):
            continue
        node = self.store.insert("knowledge_nodes", {"id": new_id("knode"), "tenant_id": ctx.tenant_id, "node_type": "asset_clue", "title": clue["title"], "source_ref": (clue.get("source_refs") or [{}])[0], "sensitivity_level": "L1", "authorization_scope": "case", "created_at": now_iso()})
        case_node = node_ids.get(f"case:{clue['case_id']}")
        if case_node:
            self.store.insert("knowledge_edges", {"id": new_id("kedge"), "tenant_id": ctx.tenant_id, "source_node_id": case_node, "target_node_id": node["id"], "relation_type": "contains_clue", "created_at": now_iso()})


def knowledge_nodes(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer", "auditor"})
    _ensure_knowledge(self, ctx)
    return _tenant_rows(self, "knowledge_nodes", ctx.tenant_id)


def knowledge_node(self: LawPlatform, ctx, node_id: str) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer", "auditor"})
    node = self.store.get("knowledge_nodes", node_id)
    if not node or node.get("tenant_id") != ctx.tenant_id:
        raise AppError("VALIDATION_ERROR", "Knowledge node does not exist", 404)
    return node


def knowledge_graph(self: LawPlatform, ctx) -> dict[str, Any]:
    return {"nodes": knowledge_nodes(self, ctx), "edges": _tenant_rows(self, "knowledge_edges", ctx.tenant_id)}


def extract_feedback_insights(self: LawPlatform, ctx, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "reviewer"})
    samples = feedback_samples(self, ctx)
    rejected = [row for row in samples if row.get("human_label") in {"rejected", "ignored"}]
    insight = self.store.insert("feedback_insights", {"id": new_id("insight"), "tenant_id": ctx.tenant_id, "insight_type": "noise_rule_candidate", "title": "无效/忽略反馈规则候选", "sample_count": len(samples), "recommendation": "下调重复或被忽略来源的提醒优先级。", "supporting_sample_ids": [row["id"] for row in rejected[:20]], "created_at": now_iso()})
    self.security.audit(ctx, "feedback_insight_extracted", "feedback_insight", insight["id"], {"sample_count": len(samples)})
    return insight


def evaluation_runs(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
    return _tenant_rows(self, "evaluation_runs", ctx.tenant_id)


def create_evaluation_run(self: LawPlatform, ctx, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "reviewer"})
    samples = feedback_samples(self, ctx)
    baseline = float(payload.get("baseline_score", 0.7))
    candidate = float(payload.get("candidate_score", baseline))
    run = self.store.insert("evaluation_runs", {"id": new_id("eval"), "tenant_id": ctx.tenant_id, "target_version": payload.get("target_version", "candidate"), "baseline_version": payload.get("baseline_version", "current"), "status": "passed" if candidate >= baseline else "blocked", "sample_count": len(samples), "scores": {"baseline": baseline, "candidate": candidate}, "created_at": now_iso()})
    self.security.audit(ctx, "evaluation_run_created", "evaluation_run", run["id"], {"status": run["status"], "target_version": run["target_version"]})
    return run


def business_leads(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer"})
    rows = _tenant_rows(self, "business_leads", ctx.tenant_id)
    if rows:
        return rows
    for record in self.store.list("external_records"):
        if record.get("authorization_status") not in {"authorized", "public", "manual"}:
            continue
        payload = record.get("normalized_payload") or {}
        self.store.insert("business_leads", {"id": new_id("lead"), "tenant_id": ctx.tenant_id, "title": f"{record.get('source_name')} 业务线索：{payload.get('project_name') or payload.get('asset_name') or payload.get('company_name') or record.get('record_type')}", "status": "pending", "trigger_reason": "公开/授权来源出现经营或风险事件", "potential_value": payload.get("estimated_value") or payload.get("contract_amount") or "待评估", "follow_up_risk": "需律师确认合规触达方式", "source_ref": {"source_name": record.get("source_name"), "source_url": record.get("source_url"), "source_time": record.get("record_time")}, "created_at": now_iso()})
    return _tenant_rows(self, "business_leads", ctx.tenant_id)


def review_business_lead(self: LawPlatform, ctx, lead_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer"})
    lead = self.store.get("business_leads", lead_id)
    if not lead or lead.get("tenant_id") != ctx.tenant_id:
        raise AppError("VALIDATION_ERROR", "Business lead does not exist", 404)
    updated = self.store.update("business_leads", lead_id, {"status": payload.get("status", "reviewed"), "review_comment": payload.get("comment"), "reviewed_by": ctx.actor_id, "updated_at": now_iso()})
    self.security.audit(ctx, "business_lead_reviewed", "business_lead", lead_id, {"status": updated["status"]})
    return updated


def policy_alerts(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer"})
    rows = _tenant_rows(self, "policy_alerts", ctx.tenant_id)
    if rows:
        return rows
    alert = self.store.insert("policy_alerts", {"id": new_id("policyalert"), "tenant_id": ctx.tenant_id, "title": "执行案件公开信息使用合规提示", "status": "pending", "industry": "通用", "region": "中国", "impact_targets": ["执行案件团队", "客户沟通"], "recommended_action": "对外发送前由律师审核，保留来源和授权记录。", "source_ref": {"source_name": "内部合规规则库", "source_url": "internal://policy/execution-data-use", "source_time": now_iso()}, "created_at": now_iso()})
    return [alert]


def review_policy_alert(self: LawPlatform, ctx, alert_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "lawyer", "reviewer"})
    alert = self.store.get("policy_alerts", alert_id)
    if not alert or alert.get("tenant_id") != ctx.tenant_id:
        raise AppError("VALIDATION_ERROR", "Policy alert does not exist", 404)
    updated = self.store.update("policy_alerts", alert_id, {"status": payload.get("status", "reviewed"), "review_comment": payload.get("comment"), "reviewed_by": ctx.actor_id, "updated_at": now_iso()})
    self.security.audit(ctx, "policy_alert_reviewed", "policy_alert", alert_id, {"status": updated["status"]})
    return updated


def management_dashboard(self: LawPlatform, ctx) -> dict[str, Any]:
    self.security.require_role(ctx, {"owner", "admin", "reviewer", "auditor"})
    cases = self.list_cases(ctx)
    case_ids = {case["id"] for case in cases}
    clues = [row for row in self.store.list("asset_clues") if row.get("case_id") in case_ids]
    reports = [row for row in self.store.list("reports") if row.get("case_id") in case_ids]
    costs = platform_costs(self, ctx)
    metrics = {
        "case_count": len(cases),
        "clue_confirmation_rate": _ratio(len([row for row in clues if row.get("review_status") in {"confirmed", "task_created"}]), len(clues)),
        "report_rejection_rate": _ratio(len([row for row in reports if row.get("review_comment") and row.get("generation_status") == "review_required"]), len(reports)),
        "recovery_status": "tracking_required",
        "cost_trend_total": costs["total_amount"],
    }
    for key, value in metrics.items():
        self.store.insert("management_metrics", {"id": new_id("mgmt"), "tenant_id": ctx.tenant_id, "metric_key": key, "metric_value": value, "created_at": now_iso()})
    return {"metrics": metrics, "cases": cases, "costs": costs}
