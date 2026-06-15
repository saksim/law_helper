from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import new_id, now_iso
from .store import Store


TEAM_ROLES = [
    {"role": "product_owner", "label": "产品/项目负责人", "allocation": 1, "responsibility": "需求、样本、验收、律师沟通"},
    {"role": "backend_platform", "label": "后端/平台工程师", "allocation": 1, "responsibility": "API、权限、插件、任务、审计、数据模型"},
    {"role": "ai_nlp", "label": "AI/NLP 工程师", "allocation": 1, "responsibility": "OCR、抽取、评分、报告、评估"},
    {"role": "frontend", "label": "前端工程师", "allocation": 1, "responsibility": "Web 工作台、移动 H5、报告与复核"},
    {"role": "data_engineer", "label": "数据工程师", "allocation": 0.5, "responsibility": "数据源、清洗、索引、监控数据"},
    {"role": "qa", "label": "QA", "allocation": 0.5, "responsibility": "测试矩阵、回归集、上线门禁"},
    {"role": "legal_expert", "label": "法律业务专家", "allocation": 0.5, "responsibility": "模板、线索价值、复核标准"},
]

PHASES = [
    {
        "key": "phase_0",
        "label": "Phase 0：样本驱动设计",
        "duration_weeks": "1-2",
        "deliverables": ["10 份 PDF 样本", "5 个执行案件样本", "数据源授权确认", "字段字典初版", "桌面和移动核心原型", "P0 验收集"],
        "exit_standard": "PRD、UX、数据字典、QA 验收计划冻结到可开发状态。",
    },
    {
        "key": "phase_1",
        "label": "Phase 1：平台内核与文档链路",
        "duration_weeks": "2-3",
        "deliverables": ["用户、角色、案件、文件基础模型", "文件上传与对象存储", "文档解析任务队列", "Markdown/JSON/坐标映射输出", "审计日志基础", "桌面案件工作台雏形"],
        "exit_standard": "真实 PDF 可上传、解析、查看、校对。",
    },
    {
        "key": "phase_2",
        "label": "Phase 2：主体与线索链路",
        "duration_weeks": "3-4",
        "deliverables": ["主体识别与候选确认", "2 到 3 个数据连接器", "external_records 规范化", "财产线索抽取与去重", "线索评分和报告模板", "报告复核状态"],
        "exit_standard": "5 个执行案件样本能生成可复核财产线索报告。",
    },
    {
        "key": "phase_3",
        "label": "Phase 3：监控通知与移动轻操作",
        "duration_weeks": "2-3",
        "deliverables": ["监控主体配置", "定时任务和快照", "字段 Diff 和事件分类", "飞书/企微/邮件/站内通知", "移动 H5 提醒详情", "确认/忽略/转任务"],
        "exit_standard": "监控事件能推送到手机并完成 3 步处理。",
    },
    {
        "key": "phase_4",
        "label": "Phase 4：安全、质量与试点上线",
        "duration_weeks": "2",
        "deliverables": ["数据分级策略", "模型网关策略", "权限和越权测试", "E2E 回归集", "律师可用性测试", "Runbook 和回滚演练"],
        "exit_standard": "QA 门禁通过，试点用户确认可用。",
    },
]

SPRINTS = [
    {"key": "S0", "goal": "施工准备", "outputs": ["样本", "原型", "字段", "验收集"]},
    {"key": "S1", "goal": "案件与文件", "outputs": ["案件", "上传", "存储", "审计"]},
    {"key": "S2", "goal": "文档解析", "outputs": ["OCR/解析", "Markdown/JSON", "校对"]},
    {"key": "S3", "goal": "主体与数据源", "outputs": ["主体消歧", "连接器", "外部记录"]},
    {"key": "S4", "goal": "线索报告", "outputs": ["线索抽取", "评分", "报告", "复核"]},
    {"key": "S5", "goal": "监控通知", "outputs": ["快照", "Diff", "通知", "移动详情"]},
    {"key": "S6", "goal": "安全与上线", "outputs": ["权限", "模型策略", "QA", "Runbook"]},
]

DEPENDENCIES = [
    {"key": "samples", "label": "样本", "risk_if_missing": "不能验证 OCR 和线索报告"},
    {"key": "data_source_authorization", "label": "数据源授权", "risk_if_missing": "不能承诺连接器能力"},
    {"key": "data_classification", "label": "数据分级", "risk_if_missing": "不能开放模型调用"},
    {"key": "ux_prototype", "label": "UX 原型", "risk_if_missing": "前端会按技术模块误建页面"},
]

MILESTONES = [
    {"key": "M1", "label": "样本和原型冻结", "acceptance": "产品、律师、研发确认 P0 主流程", "phase": "phase_0"},
    {"key": "M2", "label": "文档链路可跑通", "acceptance": "PDF 上传到校对闭环", "phase": "phase_1"},
    {"key": "M3", "label": "线索报告可复核", "acceptance": "5 个案件生成报告", "phase": "phase_2"},
    {"key": "M4", "label": "移动提醒闭环", "acceptance": "手机处理提醒并转任务", "phase": "phase_3"},
    {"key": "M5", "label": "试点上线", "acceptance": "QA、安全、可用性门禁通过", "phase": "phase_4"},
]

RISKS = [
    {"key": "data_source_authorization_delay", "risk": "数据源授权延迟", "mitigation": "先使用人工补录和模拟连接器"},
    {"key": "ocr_sample_quality", "risk": "OCR 样本质量差", "mitigation": "标注低置信度，缩小承诺范围"},
    {"key": "subject_resolution_unstable", "risk": "主体消歧不稳定", "mitigation": "引入人工确认候选主体"},
    {"key": "notification_noise", "risk": "提醒噪声过高", "mitigation": "增加忽略/重复反馈，先低频推送"},
    {"key": "lawyer_adoption", "risk": "律师不愿使用", "mitigation": "先做真实用户可用性测试和文案调整"},
]


def implementation_plan_payload() -> dict[str, Any]:
    return {
        "version": "08-IMPLEMENTATION_PLAN",
        "objective": "把平台蓝图推进为 P0 试点可用版。",
        "suggested_cycle_weeks": "10-14",
        "principles": ["先闭环，再增强", "先授权 API，再自动化页面", "先人工复核，再模型优化", "先结构和审计，再体验细节扩展"],
        "team": deepcopy(TEAM_ROLES),
        "phases": deepcopy(PHASES),
        "sprints": deepcopy(SPRINTS),
        "dependencies": deepcopy(DEPENDENCIES),
        "milestones": deepcopy(MILESTONES),
        "risks": deepcopy(RISKS),
        "handoff": {
            "研发负责人": "Sprint 和依赖管理",
            "产品负责人": "样本和验收推进",
            "QA": "阶段门禁和试点风险",
            "交付": "上线计划和客户沟通节奏",
        },
        "test_status": "untested",
    }


def create_implementation_checkpoint(store: Store, tenant_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    checkpoint = {
        "id": new_id("impl"),
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "phase": payload.get("phase"),
        "sprint": payload.get("sprint"),
        "milestone": payload.get("milestone"),
        "dependency_statuses": payload.get("dependency_statuses") or {},
        "risk_statuses": payload.get("risk_statuses") or {},
        "evidence_refs": payload.get("evidence_refs") or {},
        "notes": payload.get("notes"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    store.insert("implementation_checkpoints", checkpoint)
    return checkpoint


def implementation_status(store: Store, tenant_id: str) -> dict[str, Any]:
    snapshot = _snapshot(store, tenant_id)
    latest_qa_run = _latest_qa_run(store, tenant_id)
    latest_checkpoint = _latest_checkpoint(store, tenant_id)
    dependency_results = _dependency_results(snapshot, latest_qa_run, latest_checkpoint)
    phase_results = _phase_results(snapshot, latest_qa_run, dependency_results)
    milestone_results = _milestone_results(phase_results)
    risk_results = _risk_results(snapshot, latest_qa_run, dependency_results)
    first_open_phase = next((phase["key"] for phase in PHASES if phase_results[phase["key"]]["status"] != "passed"), None)
    overall_status = "ready_for_pilot" if not first_open_phase else "blocked" if _has_blocking_dependency(dependency_results) else "in_progress"
    return {
        "version": "08-IMPLEMENTATION_PLAN",
        "overall_status": overall_status,
        "current_phase": first_open_phase or "pilot_ready",
        "cycle_weeks": "10-14",
        "phase_results": phase_results,
        "sprint_results": _sprint_results(phase_results),
        "dependency_results": dependency_results,
        "milestone_results": milestone_results,
        "risk_results": risk_results,
        "latest_qa_acceptance_run": latest_qa_run,
        "latest_checkpoint": latest_checkpoint,
        "snapshot": snapshot,
        "handoff_targets": implementation_plan_payload()["handoff"],
    }


def _snapshot(store: Store, tenant_id: str) -> dict[str, Any]:
    cases = [row for row in store.list("cases") if row.get("tenant_id") == tenant_id and not row.get("deleted_at")]
    case_ids = {row["id"] for row in cases}
    files = [row for row in store.list("case_files") if row.get("case_id") in case_ids]
    file_ids = {row["id"] for row in files}
    blocks = [row for row in store.list("document_blocks") if row.get("file_id") in file_ids]
    entities = [row for row in store.list("extracted_entities") if row.get("object_id") in file_ids]
    reports = [row for row in store.list("reports") if row.get("case_id") in case_ids]
    report_ids = {row["id"] for row in reports}
    clues = [row for row in store.list("asset_clues") if row.get("case_id") in case_ids]
    external_records = [row for row in store.list("external_records") if row.get("id") in {ref.get("external_record_id") for clue in clues for ref in clue.get("source_refs", [])}]
    subjects = [row for row in store.list("subjects") if row.get("tenant_id") == tenant_id]
    targets = [row for row in store.list("monitor_targets") if row.get("tenant_id") == tenant_id and row.get("case_id") in case_ids]
    target_ids = {row["id"] for row in targets}
    events = [row for row in store.list("monitor_events") if row.get("monitor_target_id") in target_ids]
    event_ids = {row["id"] for row in events}
    notifications = [row for row in store.list("notifications") if row.get("tenant_id") == tenant_id and row.get("event_id") in event_ids]
    audits = [row for row in store.list("audit_logs") if row.get("tenant_id") == tenant_id]
    data_sources = [row for row in store.list("data_source_configs") if row.get("tenant_id") == tenant_id]
    qa_runs = [row for row in store.list("qa_acceptance_runs") if row.get("tenant_id") == tenant_id]
    return {
        "cases": len(cases),
        "files": len(files),
        "document_blocks": len(blocks),
        "extracted_entities": len(entities),
        "subjects": len(subjects),
        "external_records": len(external_records),
        "asset_clues": len(clues),
        "reports": len(reports),
        "confirmed_reports": len([row for row in reports if row.get("generation_status") in {"confirmed", "exported"}]),
        "report_exports": len([row for row in store.list("report_exports") if row.get("tenant_id") == tenant_id and row.get("report_id") in report_ids]),
        "monitor_targets": len(targets),
        "monitor_events": len(events),
        "notifications": len(notifications),
        "audit_logs": len(audits),
        "authorized_data_sources": len([row for row in data_sources if _is_authorized_data_source(row)]),
        "qa_acceptance_runs": len(qa_runs),
        "passed_qa_acceptance_runs": len([row for row in qa_runs if row.get("status") == "passed"]),
    }


def _phase_results(snapshot: dict[str, int], latest_qa_run: dict[str, Any] | None, dependencies: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    qa_passed = bool(latest_qa_run and latest_qa_run.get("status") == "passed")
    return {
        "phase_0": _result(qa_passed or all(dependencies[key]["status"] == "passed" for key in ("samples", "ux_prototype")), "样本、原型、字段和验收集冻结"),
        "phase_1": _result(snapshot["cases"] > 0 and snapshot["files"] > 0 and snapshot["document_blocks"] > 0 and snapshot["audit_logs"] > 0, "案件、上传、解析和审计链路可跑通"),
        "phase_2": _result(snapshot["subjects"] > 0 and snapshot["external_records"] > 0 and snapshot["asset_clues"] > 0 and snapshot["reports"] > 0, "主体、数据源、线索和报告链路可复核"),
        "phase_3": _result(snapshot["monitor_targets"] > 0 and snapshot["monitor_events"] > 0 and snapshot["notifications"] > 0, "监控事件可推送并进入移动轻操作"),
        "phase_4": _result(qa_passed, "安全、质量、可用性和上线门禁通过"),
    }


def _sprint_results(phase_results: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping = {"S0": "phase_0", "S1": "phase_1", "S2": "phase_1", "S3": "phase_2", "S4": "phase_2", "S5": "phase_3", "S6": "phase_4"}
    return {sprint["key"]: {"goal": sprint["goal"], "status": phase_results[mapping[sprint["key"]]]["status"], "outputs": sprint["outputs"]} for sprint in SPRINTS}


def _dependency_results(snapshot: dict[str, int], latest_qa_run: dict[str, Any] | None, latest_checkpoint: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    overrides = (latest_checkpoint or {}).get("dependency_statuses") or {}
    qa_passed = bool(latest_qa_run and latest_qa_run.get("status") == "passed")
    raw = {
        "samples": "passed" if qa_passed else "missing",
        "data_source_authorization": "passed" if snapshot["authorized_data_sources"] >= 2 or qa_passed else "missing",
        "data_classification": "passed" if snapshot["audit_logs"] > 0 or qa_passed else "missing",
        "ux_prototype": "passed" if qa_passed else "missing",
    }
    results: dict[str, dict[str, Any]] = {}
    for dependency in DEPENDENCIES:
        key = dependency["key"]
        status = overrides.get(key, raw[key])
        results[key] = {**dependency, "status": status}
    return results


def _milestone_results(phase_results: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        milestone["key"]: {**milestone, "status": phase_results[milestone["phase"]]["status"]}
        for milestone in MILESTONES
    }


def _risk_results(snapshot: dict[str, int], latest_qa_run: dict[str, Any] | None, dependencies: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    qa_passed = bool(latest_qa_run and latest_qa_run.get("status") == "passed")
    active = {
        "data_source_authorization_delay": dependencies["data_source_authorization"]["status"] != "passed",
        "ocr_sample_quality": snapshot["files"] == 0,
        "subject_resolution_unstable": snapshot["subjects"] == 0,
        "notification_noise": snapshot["monitor_events"] > 0 and snapshot["notifications"] == 0,
        "lawyer_adoption": not qa_passed,
    }
    return {risk["key"]: {**risk, "status": "active" if active[risk["key"]] else "controlled"} for risk in RISKS}


def _latest_qa_run(store: Store, tenant_id: str) -> dict[str, Any] | None:
    rows = [row for row in store.list("qa_acceptance_runs") if row.get("tenant_id") == tenant_id]
    return sorted(rows, key=lambda row: row.get("created_at") or "")[-1] if rows else None


def _latest_checkpoint(store: Store, tenant_id: str) -> dict[str, Any] | None:
    rows = [row for row in store.list("implementation_checkpoints") if row.get("tenant_id") == tenant_id]
    return sorted(rows, key=lambda row: row.get("created_at") or "")[-1] if rows else None


def _has_blocking_dependency(dependencies: dict[str, dict[str, Any]]) -> bool:
    return any(row["status"] == "blocked" for row in dependencies.values())


def _result(passed: bool, evidence: str) -> dict[str, str]:
    return {"status": "passed" if passed else "missing", "evidence": evidence}


def _is_authorized_data_source(row: dict[str, Any]) -> bool:
    if not row.get("enabled") or row.get("mode") != "authorized_api":
        return False
    headers = row.get("headers") or {}
    return bool(row.get("api_key") or any(any(token in key.lower() for token in ("api_key", "token", "secret", "password", "authorization", "x-api-key")) and value for key, value in headers.items()))
