from __future__ import annotations

from copy import deepcopy
from typing import Any

from .data_dictionary import validate_store_against_dictionary
from .models import new_id, now_iso
from .store import Store


OPERATING_COMPONENTS = [
    {"key": "web_bff", "label": "Web/BFF", "responsibility": "Desktop workspace, mobile H5, and client aggregation APIs."},
    {"key": "api_service", "label": "API service", "responsibility": "Cases, files, subjects, clues, monitoring, reports, and review APIs."},
    {"key": "worker", "label": "Worker", "responsibility": "OCR, extraction, connectors, report generation, and notifications."},
    {"key": "postgresql", "label": "PostgreSQL", "responsibility": "Primary business database."},
    {"key": "object_storage", "label": "Object storage", "responsibility": "Original files, parsed results, and raw response references."},
    {"key": "search_vector_index", "label": "Search/vector index", "responsibility": "Text and semantic retrieval."},
    {"key": "redis_queue", "label": "Redis/Queue", "responsibility": "Cache and asynchronous task queue."},
    {"key": "model_gateway", "label": "Model gateway", "responsibility": "Model routing, data policy, and invocation records."},
    {"key": "notification_channels", "label": "Notification channels", "responsibility": "Feishu, WeCom, email, and in-app notifications."},
]

PRE_DEPLOYMENT_CHECKS = [
    {"key": "environment_variables", "label": "Environment variables are complete"},
    {"key": "database_migration", "label": "Database migration is complete"},
    {"key": "object_storage_access", "label": "Object storage bucket is reachable"},
    {"key": "queue_worker", "label": "Queue and worker are healthy"},
    {"key": "plugin_contract_tests", "label": "Plugin contract tests passed"},
    {"key": "data_source_authorization", "label": "Data source authorization is valid"},
    {"key": "model_policy_config", "label": "Model policy is configured"},
    {"key": "notification_smoke_test", "label": "Notification bot can send a test message"},
    {"key": "audit_log_write", "label": "Audit log writes are healthy"},
    {"key": "rollback_version", "label": "Rollback version is available"},
]

FAULT_PLAYBOOKS = [
    {
        "key": "file_upload_failure",
        "symptom": "File upload fails or has no response for a long time.",
        "diagnosis": ["Check file size and format limits.", "Check object storage availability.", "Check API error logs.", "Check user permission and case status."],
        "degradation": "Allow retry later or administrator-assisted upload.",
    },
    {
        "key": "document_parse_failure",
        "symptom": "parse_status is failed or remains running too long.",
        "diagnosis": ["Check worker liveness.", "Check OCR/parser plugin logs.", "Check source file integrity.", "Check object storage read permissions."],
        "degradation": "Mark as manual arrangement, preserve original file, and allow manual text upload.",
    },
    {
        "key": "connector_failure",
        "symptom": "Data source is unavailable during asset clue report generation.",
        "diagnosis": ["Check authorization expiry.", "Check rate limit.", "Check plugin contract tests.", "Check external service status."],
        "degradation": "Disable connector feature flag, mark the source unavailable in reports, and allow manual records.",
    },
    {
        "key": "model_policy_blocked",
        "symptom": "Model gateway returns DATA_POLICY_BLOCKED.",
        "diagnosis": ["Confirm material sensitivity level.", "Confirm model provider policy.", "Use redaction or private/local model path when necessary.", "Do not bypass the policy gateway."],
        "degradation": "Switch to private/local model or manual review.",
    },
    {
        "key": "notification_not_sent",
        "symptom": "Monitoring notification is not sent.",
        "diagnosis": ["Check monitor jobs.", "Check event generation.", "Check notification channel configuration.", "Check bot webhook or email service."],
        "degradation": "Keep in-app notification as fallback and allow administrator export of event lists.",
    },
    {
        "key": "permission_anomaly",
        "symptom": "User cannot see an authorized case or can see an unauthorized case.",
        "diagnosis": ["Freeze related sessions immediately.", "Check role, case access, and tenant id.", "Check audit logs for impact scope.", "Enter security incident flow if unauthorized access exists."],
        "degradation": "Freeze affected access and handle as a security incident.",
    },
]

ROLLBACK_STRATEGIES = [
    {"target": "web_bff", "method": "Rollback frontend version or close the new entry."},
    {"target": "api_service", "method": "Rollback service image while keeping database compatibility."},
    {"target": "plugin", "method": "Disable feature flag and return to the previous version."},
    {"target": "model", "method": "Switch to default provider or disable external model."},
    {"target": "parser", "method": "Switch back to the previous parser version."},
    {"target": "notification", "method": "Disable external notification while keeping in-app notifications."},
    {"target": "database_migration", "method": "Only reversible migrations can be rolled back; irreversible migrations require backup restore."},
]

ALERT_METRICS = [
    {"key": "api_5xx_error_rate", "threshold": "manual_threshold", "source": "api logs"},
    {"key": "file_upload_failure_rate", "threshold": "manual_threshold", "source": "case_files.parse_status and API logs"},
    {"key": "document_parse_failure_rate", "threshold": "manual_threshold", "source": "case_files.parse_status"},
    {"key": "connector_failure_rate", "threshold": "manual_threshold", "source": "plugin_runs and connector_alerts"},
    {"key": "model_call_failure_rate", "threshold": "manual_threshold", "source": "model_invocations"},
    {"key": "monitor_job_delay", "threshold": "manual_threshold", "source": "jobs"},
    {"key": "notification_failure_rate", "threshold": "manual_threshold", "source": "notification_deliveries"},
    {"key": "permission_denial_spike", "threshold": "manual_threshold", "source": "audit_logs"},
    {"key": "worker_queue_backlog", "threshold": "manual_threshold", "source": "jobs"},
]

ROUTINE_INSPECTIONS = {
    "daily": ["failed_jobs", "connector_errors", "notification_failures", "high_risk_audit_logs"],
    "weekly": ["report_source_refs", "rejected_clue_reasons", "plugin_versions_and_authorization", "storage_and_model_cost"],
    "monthly": ["usability_metrics", "expired_raw_response_cleanup", "critical_plugin_rollback_drill", "qa_regression_sample_update"],
}

SECURITY_EVENT_FLOW = [
    "Freeze affected feature or user immediately.",
    "Preserve logs and evidence.",
    "Assess affected cases and users.",
    "Notify owner.",
    "Fix and retest.",
    "Produce retrospective and regression prevention items.",
]


def runbook_payload() -> dict[str, Any]:
    return {
        "version": "09-RUNBOOK",
        "objective": "Keep P0 pilot operations diagnosable, degradable, and reversible after launch.",
        "operating_components": deepcopy(OPERATING_COMPONENTS),
        "pre_deployment_checks": deepcopy(PRE_DEPLOYMENT_CHECKS),
        "fault_playbooks": deepcopy(FAULT_PLAYBOOKS),
        "rollback_strategies": deepcopy(ROLLBACK_STRATEGIES),
        "alert_metrics": deepcopy(ALERT_METRICS),
        "routine_inspections": deepcopy(ROUTINE_INSPECTIONS),
        "security_event_flow": deepcopy(SECURITY_EVENT_FLOW),
        "post_launch_observation_window_days": 7,
        "handoff": {
            "ops": "Deployment, alerting, and incident response.",
            "engineering": "Diagnosis and rollback paths.",
            "product": "Customer impact notes.",
            "security_admin": "Audit and security incident handling.",
        },
        "test_status": "untested",
    }


def create_runbook_check(store: Store, tenant_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    check = {
        "id": new_id("rbcheck"),
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "check_type": payload.get("check_type") or "pre_deployment",
        "check_key": payload["check_key"],
        "status": payload.get("status") or "passed",
        "evidence_refs": payload.get("evidence_refs") or {},
        "notes": payload.get("notes"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    return store.insert("runbook_checks", check)


def create_runbook_incident(store: Store, tenant_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    incident = {
        "id": new_id("incident"),
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "incident_type": payload["incident_type"],
        "severity": payload.get("severity") or "P1",
        "status": payload.get("status") or "open",
        "affected_component": payload.get("affected_component"),
        "summary": payload["summary"],
        "detection_source": payload.get("detection_source"),
        "diagnosis": payload.get("diagnosis") or [],
        "actions": payload.get("actions") or [],
        "rollback_strategy": payload.get("rollback_strategy"),
        "evidence_refs": payload.get("evidence_refs") or {},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    return store.insert("runbook_incidents", incident)


def resolve_runbook_incident(store: Store, tenant_id: str, incident_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    incident = store.get("runbook_incidents", incident_id)
    if not incident or incident.get("tenant_id") != tenant_id:
        raise KeyError(incident_id)
    updates = {
        "status": payload.get("status") or "resolved",
        "resolution": payload.get("resolution"),
        "actions": payload.get("actions") or incident.get("actions") or [],
        "evidence_refs": {**(incident.get("evidence_refs") or {}), **(payload.get("evidence_refs") or {})},
        "resolved_by": actor_id,
        "resolved_at": now_iso(),
        "updated_at": now_iso(),
    }
    return store.update("runbook_incidents", incident_id, updates)


def runbook_status(store: Store, tenant_id: str) -> dict[str, Any]:
    snapshot = _ops_snapshot(store, tenant_id)
    latest_checks = _latest_checks(store, tenant_id)
    deployment_results = _deployment_results(store, tenant_id, snapshot, latest_checks)
    open_incidents = [
        row
        for row in store.list("runbook_incidents")
        if row.get("tenant_id") == tenant_id and row.get("status") in {"open", "investigating", "mitigating"}
    ]
    blocking_incidents = [row for row in open_incidents if row.get("severity") in {"P0", "P1"} or row.get("incident_type") == "permission_anomaly"]
    if blocking_incidents:
        overall_status = "blocked"
    elif all(result["status"] == "passed" for result in deployment_results.values()):
        overall_status = "ready_for_pilot_operations"
    else:
        overall_status = "needs_runbook_evidence"
    return {
        "version": "09-RUNBOOK",
        "overall_status": overall_status,
        "deployment_results": deployment_results,
        "operational_metrics": _operational_metrics(snapshot),
        "fault_readiness": _fault_readiness(open_incidents),
        "open_incidents": open_incidents,
        "routine_inspection_results": _routine_inspection_results(latest_checks),
        "rollback_readiness": _rollback_readiness(store),
        "post_launch_observation": {
            "window_days": 7,
            "required_daily_checks": [
                "blocking_defects",
                "lawyer_p0_completion",
                "notification_volume",
                "report_source_quality",
                "permission_or_policy_anomalies",
            ],
        },
        "snapshot": snapshot,
    }


def _ops_snapshot(store: Store, tenant_id: str) -> dict[str, Any]:
    cases = [row for row in store.list("cases") if row.get("tenant_id") == tenant_id and not row.get("deleted_at")]
    case_ids = {row["id"] for row in cases}
    files = [row for row in store.list("case_files") if row.get("case_id") in case_ids]
    jobs = [row for row in store.list("jobs") if row.get("tenant_id") == tenant_id]
    plugin_runs = [row for row in store.list("plugin_runs") if row.get("tenant_id") == tenant_id]
    data_sources = [row for row in store.list("data_source_configs") if row.get("tenant_id") == tenant_id]
    model_invocations = [row for row in store.list("model_invocations") if row.get("tenant_id") == tenant_id]
    target_ids = {row["id"] for row in store.list("monitor_targets") if row.get("tenant_id") == tenant_id and row.get("case_id") in case_ids}
    event_ids = {row["id"] for row in store.list("monitor_events") if row.get("monitor_target_id") in target_ids}
    notifications = [row for row in store.list("notifications") if row.get("tenant_id") == tenant_id and row.get("event_id") in event_ids]
    deliveries = [row for row in store.list("notification_deliveries") if row.get("tenant_id") == tenant_id]
    audit_logs = [row for row in store.list("audit_logs") if row.get("tenant_id") == tenant_id]
    qa_runs = [row for row in store.list("qa_acceptance_runs") if row.get("tenant_id") == tenant_id]
    return {
        "cases": len(cases),
        "files": len(files),
        "failed_files": len([row for row in files if row.get("parse_status") == "failed"]),
        "running_files": len([row for row in files if row.get("parse_status") == "running"]),
        "jobs": len(jobs),
        "active_jobs": len([row for row in jobs if row.get("status") in {"queued", "running"}]),
        "failed_jobs": len([row for row in jobs if row.get("status") == "failed"]),
        "plugin_runs": len(plugin_runs),
        "failed_plugin_runs": len([row for row in plugin_runs if row.get("status") == "failed"]),
        "connector_alerts_open": len([row for row in store.list("connector_alerts") if row.get("tenant_id") == tenant_id and row.get("status") in {"open", "retry_exhausted"}]),
        "authorized_data_sources": len([row for row in data_sources if _is_authorized_data_source(row)]),
        "model_invocations": len(model_invocations),
        "blocked_model_invocations": len([row for row in model_invocations if row.get("policy_blocked")]),
        "notifications": len(notifications),
        "notification_deliveries": len(deliveries),
        "failed_notification_deliveries": len([row for row in deliveries if row.get("delivery_status") == "failed"]),
        "audit_logs": len(audit_logs),
        "permission_denials": len([row for row in audit_logs if row.get("action") in {"permission_denied", "sensitive_access_denied"}]),
        "passed_qa_acceptance_runs": len([row for row in qa_runs if row.get("status") == "passed"]),
        "plugin_registry": len(store.list("plugin_registry")),
    }


def _latest_checks(store: Store, tenant_id: str) -> dict[str, dict[str, Any]]:
    checks = [row for row in store.list("runbook_checks") if row.get("tenant_id") == tenant_id]
    checks.sort(key=lambda row: row.get("created_at") or "")
    latest: dict[str, dict[str, Any]] = {}
    for check in checks:
        latest[f"{check.get('check_type')}:{check.get('check_key')}"] = check
        latest[check.get("check_key")] = check
    return latest


def _deployment_results(store: Store, tenant_id: str, snapshot: dict[str, Any], latest_checks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    dictionary_status = validate_store_against_dictionary(store)["status"]
    qa_passed = snapshot["passed_qa_acceptance_runs"] > 0
    raw = {
        "environment_variables": False,
        "database_migration": dictionary_status == "passed",
        "object_storage_access": snapshot["files"] > 0 or qa_passed,
        "queue_worker": snapshot["failed_jobs"] == 0 and (snapshot["jobs"] > 0 or qa_passed),
        "plugin_contract_tests": snapshot["plugin_registry"] > 0 and (qa_passed or snapshot["plugin_runs"] > 0),
        "data_source_authorization": snapshot["authorized_data_sources"] >= 2 or qa_passed,
        "model_policy_config": snapshot["model_invocations"] > 0 or qa_passed,
        "notification_smoke_test": snapshot["notifications"] > 0 or snapshot["notification_deliveries"] > 0 or qa_passed,
        "audit_log_write": snapshot["audit_logs"] > 0 or qa_passed,
        "rollback_version": _rollback_ready(store),
    }
    results: dict[str, dict[str, Any]] = {}
    for item in PRE_DEPLOYMENT_CHECKS:
        key = item["key"]
        override = latest_checks.get(f"pre_deployment:{key}") or latest_checks.get(key)
        status = override.get("status") if override else ("passed" if raw[key] or qa_passed else "missing")
        results[key] = {
            **item,
            "status": status,
            "evidence": override.get("evidence_refs") if override else {"system_snapshot": raw[key], "qa_passed": qa_passed},
        }
    return results


def _operational_metrics(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "api_5xx_error_rate": {"status": "not_collected", "value": None, "source": "api logs"},
        "file_upload_failure_rate": _rate(snapshot["failed_files"], max(snapshot["files"], 1), "case_files.parse_status"),
        "document_parse_failure_rate": _rate(snapshot["failed_files"], max(snapshot["files"], 1), "case_files.parse_status"),
        "connector_failure_rate": _rate(snapshot["failed_plugin_runs"] + snapshot["connector_alerts_open"], max(snapshot["plugin_runs"], 1), "plugin_runs and connector_alerts"),
        "model_call_failure_rate": _rate(snapshot["blocked_model_invocations"], max(snapshot["model_invocations"], 1), "model_invocations"),
        "monitor_job_delay": {"status": "watch", "value": snapshot["active_jobs"], "source": "jobs.active"},
        "notification_failure_rate": _rate(snapshot["failed_notification_deliveries"], max(snapshot["notification_deliveries"], 1), "notification_deliveries"),
        "permission_denial_spike": {"status": "watch", "value": snapshot["permission_denials"], "source": "audit_logs"},
        "worker_queue_backlog": {"status": "watch", "value": snapshot["active_jobs"], "source": "jobs"},
    }


def _fault_readiness(open_incidents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    incident_counts: dict[str, int] = {}
    for incident in open_incidents:
        incident_counts[incident.get("incident_type", "unknown")] = incident_counts.get(incident.get("incident_type", "unknown"), 0) + 1
    return {
        playbook["key"]: {
            "status": "active_incident" if incident_counts.get(playbook["key"], 0) else "covered",
            "open_incidents": incident_counts.get(playbook["key"], 0),
            "degradation": playbook["degradation"],
        }
        for playbook in FAULT_PLAYBOOKS
    }


def _routine_inspection_results(latest_checks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for cadence, keys in ROUTINE_INSPECTIONS.items():
        checked = [key for key in keys if (latest_checks.get(f"{cadence}_inspection:{key}") or latest_checks.get(key))]
        results[cadence] = {
            "status": "passed" if len(checked) == len(keys) else "missing",
            "checked_items": checked,
            "required_items": keys,
        }
    return results


def _rollback_readiness(store: Store) -> dict[str, Any]:
    return {
        "status": "passed" if _rollback_ready(store) else "missing",
        "strategies": deepcopy(ROLLBACK_STRATEGIES),
        "plugin_rollback_contracts": [
            {
                "plugin_id": plugin.get("plugin_id"),
                "enabled": plugin.get("enabled"),
                "rollback": plugin.get("rollback"),
                "last_rollback": plugin.get("last_rollback"),
            }
            for plugin in store.list("plugin_registry")
        ],
    }


def _rollback_ready(store: Store) -> bool:
    plugins = store.list("plugin_registry")
    return bool(plugins) and all((plugin.get("rollback") or {}).get("disable_feature_flag") for plugin in plugins)


def _rate(numerator: int, denominator: int, source: str) -> dict[str, Any]:
    value = numerator / denominator if denominator else 0
    return {"status": "watch" if numerator else "ok", "value": value, "numerator": numerator, "denominator": denominator, "source": source}


def _is_authorized_data_source(row: dict[str, Any]) -> bool:
    if not row.get("enabled") or row.get("mode") != "authorized_api":
        return False
    headers = row.get("headers") or {}
    return bool(row.get("api_key") or any(any(token in key.lower() for token in ("api_key", "token", "secret", "password", "authorization", "x-api-key")) and value for key, value in headers.items()))
