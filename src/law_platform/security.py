from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import AppError
from .models import now_iso, new_id
from .store import Store

SENSITIVITY_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}
ADMIN_ROLES = {"owner", "admin"}
CASE_ROLES = {"lawyer", "assistant", "reviewer"}


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    actor_id: str
    request_id: str
    client_type: str = "web"
    ip: str | None = None
    user_agent: str | None = None


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
        user = self.user(ctx)
        level = SENSITIVITY_ORDER.get(sensitivity_level, 4)
        if level <= 2:
            return
        if user.get("role") in {"owner", "admin", "lawyer", "reviewer"}:
            return
        self.audit(ctx, "sensitive_access_denied", "user", ctx.actor_id, {"sensitivity_level": sensitivity_level})
        raise AppError("PERMISSION_DENIED", "敏感材料需要额外权限", 403)

    def allow_external_model(self, sensitivity_level: str) -> bool:
        level = SENSITIVITY_ORDER.get(sensitivity_level, 4)
        return level <= 2

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
            "policy_blocked": not allowed,
            "created_at": now_iso(),
        }
        self.store.insert("model_invocations", invocation)
        if not allowed:
            self.audit(ctx, "model_policy_blocked", "case", case_id, {"sensitivity_level": sensitivity_level})
            raise AppError("DATA_POLICY_BLOCKED", "该数据等级禁止进入外部模型", 403)
        return invocation

    def audit(self, ctx: RequestContext, action: str, object_type: str, object_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        log = {
            "id": new_id("audit"),
            "tenant_id": ctx.tenant_id,
            "actor_id": ctx.actor_id,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "ip": ctx.ip,
            "user_agent": ctx.user_agent,
            "metadata": metadata or {},
            "created_at": now_iso(),
        }
        self.store.insert("audit_logs", log)
        return log
