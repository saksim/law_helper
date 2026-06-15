from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .errors import AppError
from .models import now_iso, new_id
from .store import Store

SENSITIVITY_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}
ADMIN_ROLES = {"owner", "admin"}
CASE_ROLES = {"lawyer", "assistant", "reviewer"}
MOBILE_CLIENT_TYPES = {"mobile_h5", "mini_program"}
MOBILE_SENSITIVE_PLACEHOLDER = "敏感材料不在移动端展示，请在桌面端查看。"
SENSITIVE_FIELD_NAMES = {
    "id_card",
    "id_card_no",
    "id_card_number",
    "identity_number",
    "bank_account",
    "bank_card",
    "bank_card_no",
    "account_number",
}
ID_CARD_18_RE = re.compile(r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)")
ID_CARD_15_RE = re.compile(r"(?<!\d)(\d{6})\d{5}(\d{4})(?!\d)")
BANK_ACCOUNT_RE = re.compile(r"(?<!\d)(\d{4})\d{4,15}(\d{4})(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")


def sensitivity_rank(sensitivity_level: str | None) -> int:
    return SENSITIVITY_ORDER.get(sensitivity_level or "L4", 4)


def redact_sensitive_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = ID_CARD_18_RE.sub(lambda match: f"{match.group(1)}********{match.group(2)}", value)
    text = ID_CARD_15_RE.sub(lambda match: f"{match.group(1)}*****{match.group(2)}", text)
    text = BANK_ACCOUNT_RE.sub(lambda match: f"{match.group(1)}****{match.group(2)}", text)
    text = PHONE_RE.sub(lambda match: f"{match.group(1)}****{match.group(2)}", text)
    return text


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item) for item in value)
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in SENSITIVE_FIELD_NAMES and item:
                redacted[key] = "******"
            else:
                redacted[key] = redact_sensitive_data(item)
        return redacted
    return value


def mobile_should_hide_raw_material(ctx: RequestContext, sensitivity_level: str | None) -> bool:
    return ctx.client_type in MOBILE_CLIENT_TYPES and sensitivity_rank(sensitivity_level) >= 3


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    actor_id: str
    request_id: str
    client_type: str = "web"
    ip: str | None = None
    user_agent: str | None = None
    page: int = 1
    page_size: int = 50


class SecurityService:
    def __init__(self, store: Store):
        self.store = store

    def user(self, ctx: RequestContext) -> dict[str, Any]:
        user = self.store.get("users", ctx.actor_id)
        if not user or user.get("tenant_id") != ctx.tenant_id or user.get("status") != "active":
            raise AppError("PERMISSION_DENIED", "用户无效或不属于当前租户", 403)
        return user

    def require_role(self, ctx: RequestContext, roles: set[str]) -> dict[str, Any]:
        user = self.user(ctx)
        if user.get("role") not in roles:
            self.audit(ctx, "permission_denied", "user", ctx.actor_id, {"required_roles": sorted(roles)})
            raise AppError("PERMISSION_DENIED", "权限不足", 403)
        return user

    def require_case_access(self, ctx: RequestContext, case_id: str, action: str = "read") -> dict[str, Any]:
        user = self.user(ctx)
        case = self.store.get("cases", case_id)
        if not case or case.get("tenant_id") != ctx.tenant_id or case.get("deleted_at"):
            raise AppError("VALIDATION_ERROR", "案件不存在", 404)
        if user.get("role") in ADMIN_ROLES:
            return case
        access_users = set(case.get("access_user_ids") or [])
        if user.get("role") in CASE_ROLES and (ctx.actor_id in access_users or case.get("responsible_lawyer_id") == ctx.actor_id):
            return case
        self.audit(ctx, "permission_denied", "case", case_id, {"action": action})
        raise AppError("PERMISSION_DENIED", "无权访问该案件", 403)

    def require_sensitive_access(self, ctx: RequestContext, sensitivity_level: str) -> None:
        if self.can_access_sensitivity(ctx, sensitivity_level):
            return
        self.audit(ctx, "sensitive_access_denied", "user", ctx.actor_id, {"sensitivity_level": sensitivity_level})
        raise AppError("PERMISSION_DENIED", "敏感材料需要额外权限", 403)

    def can_access_sensitivity(self, ctx: RequestContext, sensitivity_level: str | None) -> bool:
        user = self.user(ctx)
        level = sensitivity_rank(sensitivity_level)
        return level <= 2 or user.get("role") in {"owner", "admin", "lawyer", "reviewer"}

    def protect_material_text(self, ctx: RequestContext, value: Any, sensitivity_level: str | None) -> Any:
        if mobile_should_hide_raw_material(ctx, sensitivity_level):
            return MOBILE_SENSITIVE_PLACEHOLDER
        return redact_sensitive_text(value)

    def protect_material_record(self, ctx: RequestContext, record: dict[str, Any], sensitivity_level: str | None) -> dict[str, Any]:
        protected = redact_sensitive_data(record)
        if mobile_should_hide_raw_material(ctx, sensitivity_level):
            protected = deepcopy(protected)
            protected["text"] = MOBILE_SENSITIVE_PLACEHOLDER
            protected["markdown"] = MOBILE_SENSITIVE_PLACEHOLDER
            protected["mobile_raw_hidden"] = True
        return protected

    def redact_record(self, value: Any) -> Any:
        return redact_sensitive_data(value)

    def allow_external_model(self, sensitivity_level: str) -> bool:
        return sensitivity_rank(sensitivity_level) <= 2

    def check_model_policy(self, ctx: RequestContext, case_id: str, sensitivity_level: str, provider_external: bool) -> dict[str, Any]:
        allowed = (not provider_external) or self.allow_external_model(sensitivity_level)
        invocation = {
            "id": new_id("model"),
            "tenant_id": ctx.tenant_id,
            "actor_id": ctx.actor_id,
            "case_id": case_id,
            "provider": "external" if provider_external else "private_or_local",
            "sensitivity_level": sensitivity_level,
            "input_summary": "policy check",
            "output_summary": "allowed" if allowed else "blocked",
            "cost": 0,
            "duration_ms": 0,
            "policy_blocked": not allowed,
            "review_status": "pending",
            "prompt_injection_guard": {
                "system_instruction_separated": True,
                "case_material_treated_as_untrusted": True,
                "tool_scope_minimized": True,
                "external_action_requires_human_confirmation": True,
                "sensitive_output_check_required": True,
            },
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.insert("model_invocations", invocation)
        self.audit(ctx, "model_policy_checked", "case", case_id, {"sensitivity_level": sensitivity_level, "provider_external": provider_external, "allowed": allowed})
        if not allowed:
            self.audit(ctx, "model_policy_blocked", "case", case_id, {"sensitivity_level": sensitivity_level})
            raise AppError("DATA_POLICY_BLOCKED", "该数据等级禁止进入外部模型", 403)
        return invocation

    def export_watermark(self, ctx: RequestContext, report_id: str, export_id: str, export_format: str, created_at: str) -> str:
        return (
            "导出水印："
            f"租户={ctx.tenant_id}；操作人={ctx.actor_id}；报告={report_id}；"
            f"导出={export_id}；格式={export_format}；时间={created_at}。"
            "仅供授权案件处理使用，禁止转发给未授权人员。"
        )

    def audit(self, ctx: RequestContext, action: str, object_type: str, object_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        safe_metadata = redact_sensitive_data(metadata or {})
        tenant_logs = [row for row in self.store.list("audit_logs") if row.get("tenant_id") == ctx.tenant_id]
        prev_hash = tenant_logs[-1].get("integrity_hash") if tenant_logs else None
        log = {
            "id": new_id("audit"),
            "tenant_id": ctx.tenant_id,
            "actor_id": ctx.actor_id,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "ip": ctx.ip,
            "user_agent": ctx.user_agent,
            "metadata": safe_metadata,
            "created_at": now_iso(),
        }
        log["prev_integrity_hash"] = prev_hash
        log["integrity_hash"] = _hash_payload({key: value for key, value in log.items() if key != "integrity_hash"})
        self.store.insert("audit_logs", log)
        return log
