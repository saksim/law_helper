from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import new_id, now_iso
from .store import Store


P0_REQUIRED_SCOPES = [
    "案件工作台",
    "文档上传与解析",
    "案件要素抽取",
    "主体识别",
    "财产线索报告",
    "监控与通知",
    "人工复核",
    "权限与审计",
    "移动 H5 提醒处理",
]

P0_EXCLUDED_SCOPES = [
    "类案检索完整能力",
    "原生 App",
    "复杂图数据库能力",
    "业务开拓和经营看板",
]

TEST_MATRIX = [
    {"type": "unit", "label": "单元测试", "content": "字段归一化、状态流转、评分计算、权限判断"},
    {"type": "integration", "label": "集成测试", "content": "上传到解析、连接器到报告、监控到通知"},
    {"type": "contract", "label": "契约测试", "content": "API、插件、模型、通知渠道 schema"},
    {"type": "data", "label": "数据测试", "content": "来源保留、页码映射、去重、低置信度标记"},
    {"type": "security", "label": "安全测试", "content": "越权访问、敏感数据、模型策略、审计不可绕过"},
    {"type": "e2e", "label": "E2E", "content": "真实案件样本完整流程"},
    {"type": "usability", "label": "可用性测试", "content": "3-5 名律师真实任务测试"},
    {"type": "mobile", "label": "移动端测试", "content": "提醒详情、确认、忽略、转任务、深链"},
    {"type": "regression", "label": "回归测试", "content": "模型、连接器、模板升级后固定样本集"},
]

SAMPLE_REQUIREMENTS = {
    "real_pdf_count": 10,
    "execution_case_count": 5,
    "authorized_data_source_count": 2,
    "monitor_event_count": 20,
    "standard_report_count": 5,
}

FUNCTIONAL_GATES = [
    "document_parsing",
    "asset_clue_report",
    "monitor_notification",
    "permission_audit",
]

EXPERIENCE_GATES = [
    {"key": "lawyer_completion", "label": "5 名律师中至少 4 名无指导完成 P0 主流程"},
    {"key": "owner_30s", "label": "负责人 30 秒内说清最新线索、风险、待办"},
    {"key": "mobile_3_steps", "label": "手机 3 步内完成确认/忽略/转任务"},
    {"key": "source_judgement", "label": "用户能指出来源、时间、下一步动作"},
    {"key": "error_feedback", "label": "用户能驳回错误线索并写原因"},
]

PERFORMANCE_THRESHOLDS = {
    "desktop_home_seconds": 3.0,
    "mobile_notification_seconds": 2.0,
    "list_interaction_ms": 100,
    "upload_feedback_immediate": True,
    "long_task_progress_seconds": 1.0,
}

REQUIRED_EVIDENCE_TYPES = [
    "sample_list",
    "e2e_screenshots_or_recordings",
    "api_plugin_contract_results",
    "security_results",
    "usability_records",
    "defect_list",
    "release_risk_conclusion",
]

BLOCKING_CONDITIONS = [
    "报告无法回溯来源",
    "模型输出无引用法律结论",
    "用户可越权查看案件",
    "数据源访问绕过授权或平台限制",
    "敏感材料进入不合规外部模型",
    "移动端通知泄露完整敏感信息",
    "审计日志缺失关键操作",
]


def acceptance_plan_payload() -> dict[str, Any]:
    return {
        "version": "07-QA_ACCEPTANCE_PLAN",
        "risk_level": "P1",
        "risk_reason": "法律案件材料涉及敏感信息、法律责任、数据源合规和真实律师体验。",
        "required_scopes": P0_REQUIRED_SCOPES,
        "excluded_scopes": P0_EXCLUDED_SCOPES,
        "test_matrix": deepcopy(TEST_MATRIX),
        "sample_requirements": deepcopy(SAMPLE_REQUIREMENTS),
        "functional_gates": deepcopy(FUNCTIONAL_GATES),
        "experience_gates": deepcopy(EXPERIENCE_GATES),
        "performance_thresholds": deepcopy(PERFORMANCE_THRESHOLDS),
        "blocking_conditions": deepcopy(BLOCKING_CONDITIONS),
        "required_evidence_types": deepcopy(REQUIRED_EVIDENCE_TYPES),
        "release_rule": "所有 P0 功能、证据、体验、性能与安全门禁通过后才允许上线。",
        "test_status": "untested",
    }


def create_acceptance_run(store: Store, tenant_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = acceptance_snapshot(store, tenant_id)
    evaluation = evaluate_acceptance(snapshot, payload)
    run = {
        "id": new_id("qa"),
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "plan_version": "07-QA_ACCEPTANCE_PLAN",
        "risk_level": "P1",
        "status": evaluation["status"],
        "summary": evaluation["summary"],
        "sample_counts": evaluation["sample_counts"],
        "scope_results": evaluation["scope_results"],
        "test_matrix_results": evaluation["test_matrix_results"],
        "functional_gate_results": evaluation["functional_gate_results"],
        "experience_gate_results": evaluation["experience_gate_results"],
        "performance_gate_results": evaluation["performance_gate_results"],
        "evidence_results": evaluation["evidence_results"],
        "blocking_conditions": evaluation["blocking_conditions"],
        "defects": payload.get("defects") or [],
        "release_risk_conclusion": payload.get("release_risk_conclusion") or evaluation["summary"]["release_risk_conclusion"],
        "snapshot": snapshot,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    store.insert("qa_acceptance_runs", run)
    return run


def acceptance_snapshot(store: Store, tenant_id: str) -> dict[str, Any]:
    tenant_cases = [row for row in store.list("cases") if row.get("tenant_id") == tenant_id and not row.get("deleted_at")]
    case_ids = {row["id"] for row in tenant_cases}
    files = [row for row in store.list("case_files") if row.get("case_id") in case_ids]
    file_ids = {row["id"] for row in files}
    blocks = [row for row in store.list("document_blocks") if row.get("file_id") in file_ids]
    entities = [row for row in store.list("extracted_entities") if row.get("object_id") in file_ids]
    subject_ids = {row.get("source_subject_id") for row in store.list("subject_relations") if row.get("source_record_id") in case_ids}
    subjects = [row for row in store.list("subjects") if row.get("tenant_id") == tenant_id and row.get("id") in subject_ids]
    reports = [row for row in store.list("reports") if row.get("case_id") in case_ids]
    report_ids = {row["id"] for row in reports}
    clues = [row for row in store.list("asset_clues") if row.get("case_id") in case_ids]
    targets = [row for row in store.list("monitor_targets") if row.get("tenant_id") == tenant_id and row.get("case_id") in case_ids]
    target_ids = {row["id"] for row in targets}
    events = [row for row in store.list("monitor_events") if row.get("monitor_target_id") in target_ids]
    event_ids = {row["id"] for row in events}
    notifications = [row for row in store.list("notifications") if row.get("tenant_id") == tenant_id and row.get("event_id") in event_ids]
    deliveries = [row for row in store.list("notification_deliveries") if row.get("tenant_id") == tenant_id and row.get("notification_id") in {note["id"] for note in notifications}]
    reviews = [row for row in store.list("review_records") if row.get("tenant_id") == tenant_id]
    audits = [row for row in store.list("audit_logs") if row.get("tenant_id") == tenant_id]
    model_invocations = [row for row in store.list("model_invocations") if row.get("tenant_id") == tenant_id]
    exports = [row for row in store.list("report_exports") if row.get("tenant_id") == tenant_id and row.get("report_id") in report_ids]
    data_sources = [row for row in store.list("data_source_configs") if row.get("tenant_id") == tenant_id]
    plugin_results = [row for row in store.list("plugin_registry") if row.get("contract_status") == "passed"]
    return {
        "counts": {
            "cases": len(tenant_cases),
            "files": len(files),
            "document_blocks": len(blocks),
            "extracted_entities": len(entities),
            "subjects": len(subjects),
            "reports": len(reports),
            "confirmed_reports": len([row for row in reports if row.get("generation_status") in {"confirmed", "exported"}]),
            "asset_clues": len(clues),
            "monitor_targets": len(targets),
            "monitor_events": len(events),
            "notifications": len(notifications),
            "notification_deliveries": len(deliveries),
            "review_records": len(reviews),
            "audit_logs": len(audits),
            "model_invocations": len(model_invocations),
            "report_exports": len(exports),
            "authorized_data_sources": len([row for row in data_sources if _is_authorized_data_source(row)]),
            "passed_plugin_contracts": len(plugin_results),
        },
        "quality": {
            "files_with_page_mapping": len([row for row in files if (row.get("quality_summary") or {}).get("has_page_mapping")]),
            "files_with_low_confidence": len([row for row in files if (row.get("quality_summary") or {}).get("low_confidence_blocks")]),
            "clues_with_sources": len([row for row in clues if row.get("source_refs")]),
            "clues_with_scores": len([row for row in clues if row.get("actionability_score") is not None and row.get("confidence") is not None]),
            "clues_with_next_action": len([row for row in clues if row.get("recommended_action")]),
            "reports_with_source_refs": len([row for row in reports if _report_has_source_refs(row, clues)]),
            "audited_write_actions": _audited_write_actions(audits),
            "audit_integrity_hashes": len([row for row in audits if row.get("integrity_hash")]),
            "blocked_model_invocations": len([row for row in model_invocations if row.get("policy_blocked")]),
            "watermarked_exports": len([row for row in exports if row.get("watermark")]),
        },
    }


def evaluate_acceptance(snapshot: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    counts = snapshot["counts"]
    sample_counts = _sample_counts(counts, payload.get("sample_counts") or {})
    scope_results = _scope_results(counts)
    test_matrix_results = _test_matrix_results(payload.get("test_results") or {})
    functional_gate_results = _functional_gate_results(snapshot)
    experience_gate_results = _experience_gate_results(payload.get("usability_results") or {})
    performance_gate_results = _performance_gate_results(payload.get("performance_results") or {})
    evidence_results = _evidence_results(payload.get("evidence_refs") or {})
    blocking_conditions = _blocking_conditions(snapshot, payload.get("defects") or [])

    all_results = (
        list(sample_counts.values())
        + list(scope_results.values())
        + [row["status"] for row in test_matrix_results.values()]
        + list(functional_gate_results.values())
        + [row["status"] for row in experience_gate_results.values()]
        + [row["status"] for row in performance_gate_results.values()]
        + list(evidence_results.values())
    )
    hard_blockers = [item for item in blocking_conditions if item["status"] == "blocked"]
    failed = any(status == "failed" for status in all_results)
    needs_evidence = any(status in {"missing", "untested"} for status in all_results)
    if hard_blockers:
        status = "blocked"
    elif failed:
        status = "failed"
    elif needs_evidence:
        status = "needs_evidence"
    else:
        status = "passed"
    summary = {
        "status": status,
        "risk_level": "P1",
        "release_ready": status == "passed",
        "blocker_count": len(hard_blockers),
        "missing_evidence_count": sum(1 for status_value in evidence_results.values() if status_value == "missing"),
        "release_risk_conclusion": "允许进入上线评审" if status == "passed" else "禁止上线，需补齐阻断项或验收证据",
    }
    return {
        "status": status,
        "summary": summary,
        "sample_counts": sample_counts,
        "scope_results": scope_results,
        "test_matrix_results": test_matrix_results,
        "functional_gate_results": functional_gate_results,
        "experience_gate_results": experience_gate_results,
        "performance_gate_results": performance_gate_results,
        "evidence_results": evidence_results,
        "blocking_conditions": blocking_conditions,
    }


def _sample_counts(system_counts: dict[str, int], provided: dict[str, Any]) -> dict[str, str]:
    actual = {
        "real_pdf_count": int(provided.get("real_pdf_count", system_counts.get("files", 0)) or 0),
        "execution_case_count": int(provided.get("execution_case_count", system_counts.get("cases", 0)) or 0),
        "authorized_data_source_count": int(provided.get("authorized_data_source_count", system_counts.get("authorized_data_sources", 0)) or 0),
        "monitor_event_count": int(provided.get("monitor_event_count", system_counts.get("monitor_events", 0)) or 0),
        "standard_report_count": int(provided.get("standard_report_count", system_counts.get("confirmed_reports", 0)) or 0),
    }
    return {key: "passed" if actual[key] >= minimum else "missing" for key, minimum in SAMPLE_REQUIREMENTS.items()}


def _scope_results(counts: dict[str, int]) -> dict[str, str]:
    return {
        "案件工作台": "passed" if counts["cases"] > 0 else "missing",
        "文档上传与解析": "passed" if counts["files"] > 0 and counts["document_blocks"] > 0 else "missing",
        "案件要素抽取": "passed" if counts["extracted_entities"] > 0 else "missing",
        "主体识别": "passed" if counts["subjects"] > 0 else "missing",
        "财产线索报告": "passed" if counts["reports"] > 0 and counts["asset_clues"] > 0 else "missing",
        "监控与通知": "passed" if counts["monitor_targets"] > 0 and counts["monitor_events"] > 0 and counts["notifications"] > 0 else "missing",
        "人工复核": "passed" if counts["review_records"] > 0 else "missing",
        "权限与审计": "passed" if counts["audit_logs"] > 0 and counts["model_invocations"] > 0 else "missing",
        "移动 H5 提醒处理": "passed" if counts["notifications"] > 0 else "missing",
    }


def _test_matrix_results(test_results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for item in TEST_MATRIX:
        key = item["type"]
        value = test_results.get(key)
        if isinstance(value, dict):
            status = value.get("status", "untested")
            evidence = value.get("evidence")
        elif value is True:
            status = "passed"
            evidence = None
        elif value is False:
            status = "failed"
            evidence = None
        else:
            status = "untested"
            evidence = None
        results[key] = {"label": item["label"], "status": status, "evidence": evidence}
    return results


def _functional_gate_results(snapshot: dict[str, Any]) -> dict[str, str]:
    counts = snapshot["counts"]
    quality = snapshot["quality"]
    return {
        "document_parsing": "passed" if counts["files"] > 0 and quality["files_with_page_mapping"] == counts["files"] else "missing",
        "asset_clue_report": "passed"
        if counts["asset_clues"] > 0
        and quality["clues_with_sources"] == counts["asset_clues"]
        and quality["clues_with_scores"] == counts["asset_clues"]
        and quality["clues_with_next_action"] == counts["asset_clues"]
        else "missing",
        "monitor_notification": "passed" if counts["monitor_targets"] > 0 and counts["monitor_events"] > 0 and counts["notifications"] > 0 else "missing",
        "permission_audit": "passed" if counts["audit_logs"] > 0 and quality["audit_integrity_hashes"] == counts["audit_logs"] else "missing",
    }


def _experience_gate_results(usability: dict[str, Any]) -> dict[str, dict[str, Any]]:
    completed = int(usability.get("lawyers_completed_without_guidance", 0) or 0)
    total = int(usability.get("lawyers_total", 0) or 0)
    mobile_steps = usability.get("mobile_steps")
    return {
        "lawyer_completion": {"status": "passed" if total >= 5 and completed >= 4 else "untested", "actual": {"completed": completed, "total": total}},
        "owner_30s": {"status": "passed" if usability.get("owner_30s") is True else "untested", "actual": usability.get("owner_30s")},
        "mobile_3_steps": {"status": "passed" if isinstance(mobile_steps, int) and mobile_steps <= 3 else "untested", "actual": mobile_steps},
        "source_judgement": {"status": "passed" if usability.get("source_judgement") is True else "untested", "actual": usability.get("source_judgement")},
        "error_feedback": {"status": "passed" if usability.get("error_feedback") is True else "untested", "actual": usability.get("error_feedback")},
    }


def _performance_gate_results(performance: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "desktop_home_seconds": _threshold_result(performance.get("desktop_home_seconds"), PERFORMANCE_THRESHOLDS["desktop_home_seconds"], "lte"),
        "mobile_notification_seconds": _threshold_result(performance.get("mobile_notification_seconds"), PERFORMANCE_THRESHOLDS["mobile_notification_seconds"], "lte"),
        "list_interaction_ms": _threshold_result(performance.get("list_interaction_ms"), PERFORMANCE_THRESHOLDS["list_interaction_ms"], "lte"),
        "upload_feedback_immediate": {"status": "passed" if performance.get("upload_feedback_immediate") is True else "untested", "actual": performance.get("upload_feedback_immediate")},
        "long_task_progress_seconds": _threshold_result(performance.get("long_task_progress_seconds"), PERFORMANCE_THRESHOLDS["long_task_progress_seconds"], "lte"),
    }


def _threshold_result(actual: Any, expected: float, mode: str) -> dict[str, Any]:
    try:
        value = float(actual)
    except (TypeError, ValueError):
        return {"status": "untested", "actual": actual, "threshold": expected}
    if mode == "lte":
        return {"status": "passed" if value <= expected else "failed", "actual": value, "threshold": expected}
    return {"status": "failed", "actual": value, "threshold": expected}


def _evidence_results(evidence_refs: dict[str, Any]) -> dict[str, str]:
    return {key: "passed" if evidence_refs.get(key) else "missing" for key in REQUIRED_EVIDENCE_TYPES}


def _blocking_conditions(snapshot: dict[str, Any], defects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = snapshot["counts"]
    quality = snapshot["quality"]
    rows = [
        {"condition": "报告无法回溯来源", "status": "blocked" if counts["reports"] and quality["reports_with_source_refs"] < counts["reports"] else "clear"},
        {"condition": "模型输出无引用法律结论", "status": "blocked" if counts["reports"] and quality["reports_with_source_refs"] < counts["reports"] else "clear"},
        {"condition": "用户可越权查看案件", "status": _defect_status(defects, "unauthorized_access")},
        {"condition": "数据源访问绕过授权或平台限制", "status": _defect_status(defects, "data_source_policy_bypass")},
        {"condition": "敏感材料进入不合规外部模型", "status": _defect_status(defects, "external_model_sensitive_data")},
        {"condition": "移动端通知泄露完整敏感信息", "status": _defect_status(defects, "mobile_notification_sensitive_leak")},
        {"condition": "审计日志缺失关键操作", "status": "blocked" if counts["audit_logs"] == 0 else "clear"},
    ]
    for defect in defects:
        if defect.get("severity") in {"blocker", "critical"} and not any(row["condition"] == defect.get("title") for row in rows):
            rows.append({"condition": defect.get("title") or defect.get("code") or "阻断缺陷", "status": "blocked", "defect": defect})
    return rows


def _defect_status(defects: list[dict[str, Any]], code: str) -> str:
    return "blocked" if any(defect.get("code") == code and defect.get("status", "open") != "closed" for defect in defects) else "clear"


def _is_authorized_data_source(row: dict[str, Any]) -> bool:
    if not row.get("enabled") or row.get("mode") != "authorized_api":
        return False
    return bool(row.get("api_key") or any(_is_secret_key(key) and value for key, value in (row.get("headers") or {}).items()))


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ("api_key", "token", "secret", "password", "authorization", "x-api-key"))


def _report_has_source_refs(report: dict[str, Any], clues: list[dict[str, Any]]) -> bool:
    linked = [clue for clue in clues if clue.get("report_id") == report.get("id")]
    return bool(linked) and all(clue.get("source_refs") for clue in linked)


def _audited_write_actions(audits: list[dict[str, Any]]) -> list[str]:
    required = {
        "case_created",
        "file_uploaded_and_parsed",
        "asset_clue_report_generated",
        "asset_clue_reviewed",
        "monitor_target_created",
        "report_reviewed",
        "report_exported",
    }
    actions = {row.get("action") for row in audits}
    return sorted(actions & required)
