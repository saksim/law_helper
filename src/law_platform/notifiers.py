from __future__ import annotations

import json
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from typing import Any

from .models import new_id, now_iso
from .store import Store

PLUGIN_BY_CHANNEL = {
    "in_app": "in_app_notifier",
    "feishu": "feishu_notifier",
    "wecom": "wecom_notifier",
    "email": "email_notifier",
}
SECRET_FIELDS = {"webhook_url", "smtp_password", "verification_token", "signing_secret"}


def plugin_id_for_channel(channel: str) -> str:
    return PLUGIN_BY_CHANNEL.get(channel, "in_app_notifier")


def get_channel_config(store: Store, tenant_id: str, channel: str) -> dict[str, Any] | None:
    return store.find_one("notification_channel_configs", tenant_id=tenant_id, channel=channel)


def list_channel_configs(store: Store, tenant_id: str) -> list[dict[str, Any]]:
    rows = [row for row in store.list("notification_channel_configs") if row.get("tenant_id") == tenant_id]
    return [mask_config(row) for row in rows]


def upsert_channel_config(store: Store, tenant_id: str, channel: str, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
    existing = get_channel_config(store, tenant_id, channel)
    config = {
        **(existing or {}),
        "id": existing.get("id") if existing else new_id("nchan"),
        "tenant_id": tenant_id,
        "channel": channel,
        "enabled": bool(payload.get("enabled", existing.get("enabled") if existing else False)),
        "webhook_url": payload.get("webhook_url", existing.get("webhook_url") if existing else None),
        "smtp_host": payload.get("smtp_host", existing.get("smtp_host") if existing else None),
        "smtp_port": int(payload.get("smtp_port", existing.get("smtp_port") if existing else 465) or 465),
        "smtp_username": payload.get("smtp_username", existing.get("smtp_username") if existing else None),
        "smtp_password": payload.get("smtp_password", existing.get("smtp_password") if existing else None),
        "from_email": payload.get("from_email", existing.get("from_email") if existing else None),
        "to_emails": payload.get("to_emails", existing.get("to_emails") if existing else []),
        "verification_token": payload.get("verification_token", existing.get("verification_token") if existing else None),
        "signing_secret": payload.get("signing_secret", existing.get("signing_secret") if existing else None),
        "send_timeout_seconds": int(payload.get("send_timeout_seconds", existing.get("send_timeout_seconds") if existing else 5) or 5),
        "verification_status": "untested",
        "updated_by": actor_id,
        "updated_at": now_iso(),
    }
    if not existing:
        config["created_at"] = now_iso()
        store.insert("notification_channel_configs", config)
    else:
        config = store.update("notification_channel_configs", existing["id"], config)
    return mask_config(config)


def mask_config(config: dict[str, Any]) -> dict[str, Any]:
    masked = dict(config)
    for field in SECRET_FIELDS:
        if masked.get(field):
            masked[field] = "***"
    return masked


def notification_payload(notification: dict[str, Any], event: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": notification.get("title"),
        "event_id": event.get("id"),
        "event_type": event.get("event_type"),
        "importance": event.get("importance"),
        "why_important": notification.get("why_important"),
        "source_refs": event.get("source_refs") or [],
        "detected_at": event.get("detected_at"),
        "recommended_action": event.get("recommended_action"),
        "deep_link": notification.get("deep_link"),
        "action_buttons": notification.get("action_buttons") or ["确认", "忽略", "转任务"],
        "case_id": target.get("case_id"),
        "monitor_target_id": target.get("id"),
    }


def dispatch_notification(channel: str, plugin_id: str, contract: dict[str, Any], config: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any]:
    base = {"plugin_id": plugin_id, "provider": channel, "verification_status": "untested"}
    if contract.get("status") != "passed":
        return {**base, "status": "failed", "config_status": "plugin_contract_failed", "error": contract}
    if channel == "in_app":
        return {**base, "status": "recorded", "config_status": "internal"}
    if not config or not config.get("enabled"):
        return {**base, "status": "configuration_required", "config_status": "missing_or_disabled"}
    try:
        if channel in {"feishu", "wecom"}:
            return {**base, **send_webhook(channel, config, payload)}
        if channel == "email":
            return {**base, **send_email(config, payload)}
    except Exception as exc:
        return {**base, "status": "failed", "config_status": "configured", "error": str(exc)}
    return {**base, "status": "failed", "config_status": "unsupported_channel", "error": f"Unsupported channel: {channel}"}


def send_webhook(channel: str, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return {"status": "configuration_required", "config_status": "missing_webhook_url"}
    body = feishu_body(payload) if channel == "feishu" else wecom_body(payload)
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(config.get("send_timeout_seconds") or 5)) as response:
        response_body = response.read(500).decode("utf-8", errors="replace")
        return {"status": "sent", "config_status": "configured", "provider_status": response.status, "provider_response": response_body}


def send_email(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    host = config.get("smtp_host")
    sender = config.get("from_email")
    recipients = config.get("to_emails") or []
    if not host or not sender or not recipients:
        return {"status": "configuration_required", "config_status": "missing_smtp_or_recipients"}
    message = EmailMessage()
    message["Subject"] = payload.get("title") or "案件提醒"
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(format_text(payload))
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, int(config.get("smtp_port") or 465), context=context, timeout=int(config.get("send_timeout_seconds") or 5)) as smtp:
        if config.get("smtp_username"):
            smtp.login(config["smtp_username"], config.get("smtp_password") or "")
        smtp.send_message(message)
    return {"status": "sent", "config_status": "configured", "provider_response": "smtp_sent"}


def feishu_body(payload: dict[str, Any]) -> dict[str, Any]:
    return {"msg_type": "text", "content": {"text": format_text(payload)}}


def wecom_body(payload: dict[str, Any]) -> dict[str, Any]:
    return {"msgtype": "text", "text": {"content": format_text(payload)}}


def format_text(payload: dict[str, Any]) -> str:
    sources = "；".join(source.get("source_name", "") for source in payload.get("source_refs") or [] if source.get("source_name"))
    return "\n".join(
        part
        for part in [
            payload.get("title") or "案件提醒",
            f"重要性：{payload.get('importance')}",
            f"为什么重要：{payload.get('why_important')}",
            f"来源：{sources}" if sources else None,
            f"下一步：{payload.get('recommended_action')}",
            f"打开：{payload.get('deep_link')}",
        ]
        if part
    )


def validate_callback(config: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any]:
    if not config or not config.get("enabled"):
        return {"status": "configuration_required", "verification_status": "untested", "challenge": payload.get("challenge")}
    expected = config.get("verification_token")
    actual = payload.get("token") or payload.get("verification_token")
    if expected and actual != expected:
        return {"status": "rejected", "verification_status": "untested", "reason": "token_mismatch"}
    return {"status": "validated", "verification_status": "untested", "challenge": payload.get("challenge")}
