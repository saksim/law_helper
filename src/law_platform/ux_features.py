from __future__ import annotations

from typing import Any

from .errors import AppError
from .models import now_iso
from .services import LawPlatform
from .ux_presenters import (
    action_status_label,
    clean_text,
    present_case_card,
    present_clue,
    present_event,
    present_file,
    present_source_ref,
    report_status_label,
    review_status_label,
)


def install_ux_features() -> None:
    if getattr(LawPlatform, "_ux_features_installed", False):
        return
    LawPlatform.home_dashboard = home_dashboard
    LawPlatform.case_workspace = case_workspace
    LawPlatform.mobile_clue = mobile_clue
    LawPlatform.mobile_case_upload_context = mobile_case_upload_context
    LawPlatform.mobile_notification = mobile_notification
    LawPlatform._ux_features_installed = True


def _subject_map(self: LawPlatform) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in self.store.list("subjects")}


def _case_map(self: LawPlatform) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in self.store.list("cases")}


def _visible_cases(self: LawPlatform, ctx) -> list[dict[str, Any]]:
    return self.list_cases(ctx)


def _target_for_event(self: LawPlatform, event: dict[str, Any]) -> dict[str, Any] | None:
    return self.store.get("monitor_targets", event.get("monitor_target_id"))


def _case_files(self: LawPlatform, case_id: str) -> list[dict[str, Any]]:
    return [row for row in self.store.list("case_files") if row.get("case_id") == case_id]


def _file_blocks(self: LawPlatform, file_id: str) -> list[dict[str, Any]]:
    return [row for row in self.store.list("document_blocks") if row.get("file_id") == file_id]


def _file_entities(self: LawPlatform, file_id: str) -> list[dict[str, Any]]:
    return [row for row in self.store.list("extracted_entities") if row.get("object_id") == file_id]


def _case_subject_ids(self: LawPlatform, case_id: str, clues: list[dict[str, Any]] | None = None) -> list[str]:
    ids: list[str] = []
    for relation in self.store.list("subject_relations"):
        if relation.get("source_record_id") == case_id and relation.get("source_subject_id"):
            ids.append(relation["source_subject_id"])
    for clue in clues or []:
        if clue.get("subject_id"):
            ids.append(clue["subject_id"])
    return sorted(set(ids))


def _deadline_items(self: LawPlatform, case_ids: set[str], limit: int = 8) -> list[dict[str, Any]]:
    files = [row for row in self.store.list("case_files") if row.get("case_id") in case_ids]
    file_to_case = {row["id"]: row.get("case_id") for row in files}
    case_lookup = _case_map(self)
    rows: list[dict[str, Any]] = []
    for entity in self.store.list("extracted_entities"):
        if entity.get("entity_type") not in {"date", "deadline"}:
            continue
        case_id = file_to_case.get(entity.get("object_id"))
        if not case_id:
            continue
        rows.append(
            {
                "case_id": case_id,
                "case_name": clean_text((case_lookup.get(case_id) or {}).get("case_name"), "相关案件"),
                "date": clean_text(entity.get("normalized_value"), "日期待核验"),
                "source": entity.get("source_ref"),
                "title": "材料中识别到关键日期",
            }
        )
    return sorted(rows, key=lambda row: row["date"])[:limit]


def _present_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": report["id"],
        "case_id": report.get("case_id"),
        "title": clean_text(report.get("title"), "资产线索报告"),
        "report_type": report.get("report_type"),
        "status": report.get("generation_status"),
        "status_label": report_status_label(report.get("generation_status")),
        "reviewed_by": report.get("reviewed_by"),
        "created_at": report.get("created_at"),
        "updated_at": report.get("updated_at"),
        "export_urls": {"md": f"/api/reports/{report['id']}/export?format=md", "html": f"/api/reports/{report['id']}/export?format=html"},
        "review_action_url": f"/api/reports/{report['id']}/review",
    }


def _present_task(task: dict[str, Any], case: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": task["id"],
        "case_id": task.get("case_id"),
        "case_name": clean_text((case or {}).get("case_name"), "相关案件"),
        "title": clean_text(task.get("title"), "待处理事项"),
        "status": task.get("status"),
        "status_label": "待处理" if task.get("status") == "open" else "已处理",
        "assigned_to": task.get("assigned_to"),
        "object_type": task.get("object_type"),
        "object_id": task.get("object_id"),
        "created_at": task.get("created_at"),
    }


def home_dashboard(self: LawPlatform, ctx) -> dict[str, Any]:
    cases = _visible_cases(self, ctx)
    case_ids = {case["id"] for case in cases}
    case_lookup = {case["id"]: case for case in cases}
    subjects = _subject_map(self)

    clues = [row for row in self.store.list("asset_clues") if row.get("case_id") in case_ids]
    presented_clues = [present_clue(clue, subjects.get(clue.get("subject_id"))) for clue in clues]
    today_key = now_iso()[:10]
    today_clues = [row for row in presented_clues if str(row.get("created_at") or "").startswith(today_key)]
    if not today_clues:
        today_clues = sorted(presented_clues, key=lambda row: row.get("created_at") or "", reverse=True)[:5]

    monitor_events = []
    for event in self.store.list("monitor_events"):
        target = _target_for_event(self, event)
        if target and target.get("case_id") in case_ids:
            monitor_events.append(present_event(event, target, subjects.get(target.get("subject_id")), case_lookup.get(target.get("case_id"))))

    connector_alerts = [
        {
            "id": alert["id"],
            "case_id": alert.get("case_id"),
            "case_name": clean_text((case_lookup.get(alert.get("case_id")) or {}).get("case_name"), "相关案件"),
            "title": "数据来源需要人工处理",
            "status": alert.get("status"),
            "connector_id": alert.get("connector_id"),
            "recommended_action": "补充授权配置，或录入人工来源记录后继续生成线索。",
            "verification_status": alert.get("verification_status", "untested"),
        }
        for alert in self.store.list("connector_alerts")
        if alert.get("case_id") in case_ids and alert.get("status") in {"open", "retry_exhausted"}
    ]

    reports = [row for row in self.store.list("reports") if row.get("case_id") in case_ids]
    pending_reports = [_present_report(row) for row in reports if row.get("generation_status") == "review_required"]
    tasks = [
        _present_task(task, case_lookup.get(task.get("case_id")))
        for task in self.store.list("tasks")
        if task.get("case_id") in case_ids and task.get("status") == "open" and task.get("assigned_to") in {ctx.actor_id, None, ""}
    ]
    if not tasks:
        tasks = [
            _present_task(task, case_lookup.get(task.get("case_id")))
            for task in self.store.list("tasks")
            if task.get("case_id") in case_ids and task.get("status") == "open"
        ][:6]

    case_counts: dict[str, dict[str, int]] = {case_id: {"clues": 0, "tasks": 0, "reports": 0} for case_id in case_ids}
    for clue in clues:
        case_counts.setdefault(clue["case_id"], {"clues": 0, "tasks": 0, "reports": 0})["clues"] += 1
    for task in self.store.list("tasks"):
        if task.get("case_id") in case_counts and task.get("status") == "open":
            case_counts[task["case_id"]]["tasks"] += 1
    for report in reports:
        case_counts.setdefault(report["case_id"], {"clues": 0, "tasks": 0, "reports": 0})["reports"] += 1

    deadlines = _deadline_items(self, case_ids)
    return {
        "navigation": [
            {"key": "home", "label": "首页"},
            {"key": "cases", "label": "案件"},
            {"key": "materials", "label": "材料"},
            {"key": "clues", "label": "线索"},
            {"key": "monitor", "label": "监控"},
            {"key": "tasks", "label": "任务"},
            {"key": "reports", "label": "报告"},
            {"key": "settings", "label": "设置"},
        ],
        "summary": {
            "case_count": len(cases),
            "today_new_clue_count": len(today_clues),
            "upcoming_deadline_count": len(deadlines),
            "pending_report_review_count": len(pending_reports),
            "monitor_exception_count": len([row for row in monitor_events if row.get("action_status") == "unread"]) + len(connector_alerts),
            "open_task_count": len(tasks),
        },
        "cases": [present_case_card(case, case_counts.get(case["id"])) for case in cases],
        "today_new_clues": sorted(today_clues, key=lambda row: row.get("score") or 0, reverse=True)[:6],
        "upcoming_deadlines": deadlines,
        "pending_report_reviews": pending_reports[:6],
        "monitor_exceptions": [row for row in monitor_events if row.get("action_status") == "unread"][:6] + connector_alerts[:6],
        "high_value_clues": sorted(presented_clues, key=lambda row: row.get("score") or 0, reverse=True)[:8],
        "my_tasks": tasks[:8],
        "ux_verification_status": "untested",
    }


def case_workspace(self: LawPlatform, ctx, case_id: str) -> dict[str, Any]:
    case = self.security.require_case_access(ctx, case_id)
    subjects = _subject_map(self)
    clues_raw = [row for row in self.store.list("asset_clues") if row.get("case_id") == case_id]
    clues = [present_clue(row, subjects.get(row.get("subject_id"))) for row in clues_raw]
    files = _case_files(self, case_id)
    presented_files = [present_file(file, _file_blocks(self, file["id"]), _file_entities(self, file["id"])) for file in files]
    file_ids = {file["id"] for file in files}
    deadlines = _deadline_items(self, {case_id})
    reports = [_present_report(row) for row in self.store.list("reports") if row.get("case_id") == case_id]
    tasks = [_present_task(row, case) for row in self.store.list("tasks") if row.get("case_id") == case_id and row.get("status") == "open"]

    targets = [row for row in self.store.list("monitor_targets") if row.get("case_id") == case_id]
    target_lookup = {row["id"]: row for row in targets}
    events = [
        present_event(event, target_lookup.get(event.get("monitor_target_id")), subjects.get((target_lookup.get(event.get("monitor_target_id")) or {}).get("subject_id")), case)
        for event in self.store.list("monitor_events")
        if event.get("monitor_target_id") in target_lookup
    ]
    event_ids = {event["id"] for event in self.store.list("monitor_events") if event.get("monitor_target_id") in target_lookup}
    notification_ids = {note["id"] for note in self.store.list("notifications") if note.get("event_id") in event_ids}
    delivery_records = [
        {
            "id": row["id"],
            "notification_id": row.get("notification_id"),
            "channel": row.get("channel"),
            "delivery_status": row.get("delivery_status"),
            "config_status": row.get("config_status"),
            "verification_status": row.get("verification_status", "untested"),
            "deep_link": row.get("deep_link"),
            "created_at": row.get("created_at"),
        }
        for row in self.store.list("notification_deliveries")
        if row.get("notification_id") in notification_ids
    ]
    connector_alerts = [
        {
            "id": alert["id"],
            "title": "数据来源需要处理",
            "status": alert.get("status"),
            "recommended_action": "补充授权配置，或录入人工来源记录。",
            "verification_status": alert.get("verification_status", "untested"),
        }
        for alert in self.store.list("connector_alerts")
        if alert.get("case_id") == case_id and alert.get("status") in {"open", "retry_exhausted"}
    ]
    pending_reviews: list[dict[str, Any]] = []
    pending_reviews.extend(
        {"type": "clue", "id": clue["id"], "title": clue["title"], "status_label": clue["review_status_label"]}
        for clue in clues
        if clue.get("review_status") == "pending"
    )
    pending_reviews.extend(
        {"type": "material", "id": item["id"], "title": item["name"], "status_label": "有内容需要校对"}
        for item in presented_files
        if item.get("low_confidence_count")
    )
    pending_reviews.extend(
        {"type": "report", "id": report["id"], "title": report["title"], "status_label": report["status_label"]}
        for report in reports
        if report.get("status") == "review_required"
    )
    pending_reviews.extend({"type": "connector_alert", "id": alert["id"], "title": alert["title"], "status_label": "需处理"} for alert in connector_alerts)

    subject_ids = _case_subject_ids(self, case_id, clues_raw)
    source_entities = [row for row in self.store.list("extracted_entities") if row.get("object_id") in file_ids]
    users = {row["id"]: row for row in self.store.list("users") if row.get("tenant_id") == ctx.tenant_id}
    access_user_ids = sorted(set(case.get("access_user_ids") or []) | {case.get("responsible_lawyer_id")})
    access_users = [
        {
            "id": user_id,
            "name": clean_text((users.get(user_id) or {}).get("name"), user_id),
            "role": (users.get(user_id) or {}).get("role", "member"),
            "access_label": "可访问",
        }
        for user_id in access_user_ids
        if user_id
    ]
    recent_audit_logs = [
        {
            "id": log["id"],
            "actor_id": log.get("actor_id"),
            "actor_name": clean_text((users.get(log.get("actor_id")) or {}).get("name"), log.get("actor_id", "系统")),
            "action": log.get("action"),
            "object_type": log.get("object_type"),
            "object_id": log.get("object_id"),
            "created_at": log.get("created_at"),
        }
        for log in sorted(self.store.list("audit_logs"), key=lambda row: row.get("created_at") or "", reverse=True)
        if log.get("tenant_id") == ctx.tenant_id and (log.get("object_id") == case_id or (log.get("metadata") or {}).get("case_id") == case_id)
    ][:10]
    return {
        "case": present_case_card(case, {"clues": len(clues), "materials": len(files), "tasks": len(tasks), "reports": len(reports), "monitor_events": len(events)}),
        "tabs": [
            {"key": "overview", "label": "总览"},
            {"key": "materials", "label": "材料"},
            {"key": "clues", "label": "线索"},
            {"key": "monitor", "label": "监控"},
            {"key": "reports", "label": "报告"},
            {"key": "settings", "label": "设置"},
        ],
        "overview": {
            "today_highlights": sorted(clues, key=lambda row: row.get("score") or 0, reverse=True)[:5] + events[:3],
            "upcoming_deadlines": deadlines,
            "pending_reviews": pending_reviews[:8],
            "risks": connector_alerts,
            "tasks": tasks[:8],
            "extracted_summary": case.get("extracted_summary") or {},
        },
        "materials": {
            "files": presented_files,
            "low_confidence_review_count": sum(item.get("low_confidence_count") or 0 for item in presented_files),
            "extracted_entities": [
                {"id": row["id"], "type": row.get("entity_type"), "value": clean_text(row.get("normalized_value"), "待核验"), "source": row.get("source_ref")}
                for row in source_entities[:30]
            ],
            "mobile_upload_url": f"/mobile/cases/{case_id}/upload",
        },
        "clues": {"items": sorted(clues, key=lambda row: row.get("score") or 0, reverse=True), "filters": ["全部", "重点线索", "待确认", "已转任务", "已忽略"]},
        "monitor": {
            "delivery_records": delivery_records,
            "targets": [
                {
                    "id": target["id"],
                    "subject_id": target.get("subject_id"),
                    "subject_name": clean_text((subjects.get(target.get("subject_id")) or {}).get("name"), "相关主体"),
                    "frequency": target.get("frequency"),
                    "notify_channels": target.get("notify_channels") or [],
                    "status": target.get("status"),
                }
                for target in targets
            ],
            "events": events,
        },
        "reports": {
            "items": reports,
            "export_records": [
                {
                    "id": row["id"],
                    "report_id": row.get("report_id"),
                    "format": row.get("format"),
                    "exported_by": row.get("exported_by"),
                    "created_at": row.get("created_at"),
                }
                for row in self.store.list("report_exports")
                if row.get("report_id") in {report["id"] for report in reports}
            ],
        },
        "settings": {
            "subjects": [
                {
                    "id": subject_id,
                    "name": clean_text((subjects.get(subject_id) or {}).get("name"), "相关主体"),
                    "resolve_status": (subjects.get(subject_id) or {}).get("resolve_status"),
                    "review_status_label": review_status_label((subjects.get(subject_id) or {}).get("resolve_status")),
                }
                for subject_id in subject_ids
            ],
            "access_users": access_users,
            "recent_audit_logs": recent_audit_logs,
            "data_sources_url": "/api/data-source-configs",
            "notification_channels_url": "/api/notification-channels",
        },
        "usability_test_status": "untested",
    }


def mobile_clue(self: LawPlatform, ctx, clue_id: str) -> dict[str, Any]:
    clue = self.store.get("asset_clues", clue_id)
    if not clue:
        raise AppError("VALIDATION_ERROR", "线索不存在", 404)
    case = self.security.require_case_access(ctx, clue["case_id"], "view_mobile_clue")
    subject = self.store.get("subjects", clue.get("subject_id")) if clue.get("subject_id") else None
    data = present_clue(clue, subject)
    data.update(
        {
            "case_name": clean_text(case.get("case_name"), "相关案件"),
            "action_buttons": [
                {"key": "confirm", "label": "确认", "review_status": "confirmed"},
                {"key": "ignore", "label": "忽略", "review_status": "rejected"},
                {"key": "task", "label": "转任务", "review_status": "pending", "next_action": "create_task"},
                {"key": "share_owner", "label": "转交负责人", "review_status": "pending", "next_action": "create_task"},
            ],
            "usability_test_status": "untested",
        }
    )
    return data


def mobile_case_upload_context(self: LawPlatform, ctx, case_id: str) -> dict[str, Any]:
    case = self.security.require_case_access(ctx, case_id, "mobile_upload")
    return {
        "case": present_case_card(case),
        "accepted_channels": ["拍照上传", "选择文件"],
        "sensitivity_options": ["L2", "L3", "L4"],
        "submit_copy": "上传后会开始整理材料，完成后提醒你校对重点内容。",
        "success_copy": "材料已收到，整理完成后会通知你。",
        "usability_test_status": "untested",
    }


def mobile_notification(self: LawPlatform, ctx, notification_id: str) -> dict[str, Any]:
    notification = self.store.get("notifications", notification_id)
    if not notification:
        raise AppError("VALIDATION_ERROR", "提醒不存在", 404)
    event = self.store.get("monitor_events", notification.get("event_id"))
    if not event:
        raise AppError("VALIDATION_ERROR", "提醒关联的动态不存在", 404)
    target = self.store.get("monitor_targets", event.get("monitor_target_id"))
    if not target:
        raise AppError("VALIDATION_ERROR", "提醒关联的监控对象不存在", 404)
    case = self.security.require_case_access(ctx, target["case_id"], "view_notification")
    subject = self.store.get("subjects", target.get("subject_id")) if target.get("subject_id") else None
    event_data = present_event(event, target, subject, case)
    return {
        "id": notification["id"],
        "event_id": event["id"],
        "case_id": case["id"],
        "case_name": clean_text(case.get("case_name"), "相关案件"),
        "title": event_data["title"],
        "event_type": event_data["event_type"],
        "event_type_label": event_data["event_type_label"],
        "why_important": clean_text(notification.get("why_important"), event_data["why_important"]),
        "source_refs": [present_source_ref(ref) for ref in event.get("source_refs", [])],
        "detected_at": event.get("detected_at"),
        "recommended_action": event_data["recommended_action"],
        "deep_link": notification.get("deep_link") or f"/mobile/notifications/{notification_id}",
        "desktop_restore_url": event_data.get("desktop_restore_url"),
        "action_buttons": ["确认", "忽略", "转任务"],
        "action_status": event.get("action_status"),
        "action_status_label": action_status_label(event.get("action_status")),
        "usability_test_status": "untested",
    }