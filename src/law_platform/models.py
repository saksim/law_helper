from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

TENANT_ID = "tenant_demo"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def money_to_text(value: Decimal | int | float | str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        return f"{Decimal(str(value)):,.2f}"
    except Exception:
        return str(value)


def seed_data() -> dict[str, list[dict[str, Any]]]:
    return {
        "tenants": [
            {
                "id": TENANT_ID,
                "name": "演示律所",
                "status": "active",
                "settings": {"default_notice_channel": "in_app"},
            }
        ],
        "users": [
            {"id": "user_owner", "tenant_id": TENANT_ID, "name": "负责人", "role": "owner", "status": "active"},
            {"id": "user_admin", "tenant_id": TENANT_ID, "name": "管理员", "role": "admin", "status": "active"},
            {"id": "user_lawyer", "tenant_id": TENANT_ID, "name": "承办律师", "role": "lawyer", "status": "active"},
            {"id": "user_assistant", "tenant_id": TENANT_ID, "name": "律师助理", "role": "assistant", "status": "active"},
            {"id": "user_reviewer", "tenant_id": TENANT_ID, "name": "业务专家", "role": "reviewer", "status": "active"},
            {"id": "user_auditor", "tenant_id": TENANT_ID, "name": "审计员", "role": "auditor", "status": "active"},
            {"id": "user_other", "tenant_id": TENANT_ID, "name": "未授权律师", "role": "lawyer", "status": "active"},
        ],
        "cases": [],
        "case_files": [],
        "document_blocks": [],
        "extracted_entities": [],
        "subjects": [],
        "subject_relations": [],
        "external_records": [],
        "asset_clues": [],
        "asset_clue_scores": [],
        "reports": [],
        "report_exports": [],
        "monitor_targets": [],
        "monitor_snapshots": [],
        "monitor_events": [],
        "notifications": [],
        "notification_deliveries": [],
        "tasks": [],
        "plugin_registry": [],
        "plugin_runs": [],
        "review_records": [],
        "feedback_records": [],
        "model_invocations": [],
        "audit_logs": [],
    }