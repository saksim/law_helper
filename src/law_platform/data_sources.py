from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from typing import Any

from .errors import AppError
from .models import new_id, now_iso
from .store import Store

CONFIG_COLLECTION = "data_source_configs"
AUTHORIZED_MODE = "authorized_api"
DEMO_MODE = "demo"
MANUAL_ONLY_MODE = "manual_only"
SECRET_KEYS = {"api_key", "token", "secret", "password", "authorization", "x-api-key"}


def default_data_source_config(tenant_id: str, connector_id: str) -> dict[str, Any]:
    return {
        "id": f"{tenant_id}:{connector_id}",
        "tenant_id": tenant_id,
        "connector_id": connector_id,
        "enabled": False,
        "mode": MANUAL_ONLY_MODE,
        "base_url": None,
        "path": "",
        "method": "POST",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer",
        "api_key": None,
        "headers": {},
        "query_params": {},
        "timeout_seconds": 10,
        "records_path": "records",
        "source_name": None,
        "default_record_type": _default_record_type(connector_id),
        "verification_status": "untested",
        "verification_note": "External data-source configuration has not been live-tested.",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def list_data_source_configs(store: Store, tenant_id: str, connector_ids: list[str]) -> list[dict[str, Any]]:
    existing = {row["connector_id"]: row for row in store.list(CONFIG_COLLECTION) if row.get("tenant_id") == tenant_id}
    return [mask_config(existing.get(connector_id) or default_data_source_config(tenant_id, connector_id)) for connector_id in connector_ids]


def get_data_source_config(store: Store, tenant_id: str, connector_id: str) -> dict[str, Any]:
    return store.find_one(CONFIG_COLLECTION, tenant_id=tenant_id, connector_id=connector_id) or default_data_source_config(tenant_id, connector_id)


def upsert_data_source_config(store: Store, tenant_id: str, connector_id: str, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
    existing = store.find_one(CONFIG_COLLECTION, tenant_id=tenant_id, connector_id=connector_id)
    base = existing or default_data_source_config(tenant_id, connector_id)
    updates = deepcopy(payload)
    if "api_key" not in updates and existing and existing.get("api_key"):
        updates["api_key"] = existing["api_key"]
    config = {**base, **updates}
    config["id"] = base["id"]
    config["tenant_id"] = tenant_id
    config["connector_id"] = connector_id
    config["updated_by"] = actor_id
    config["updated_at"] = now_iso()
    config.setdefault("created_at", now_iso())
    _validate_config(config)
    saved = store.update(CONFIG_COLLECTION, existing["id"], config) if existing else store.insert(CONFIG_COLLECTION, config)
    return mask_config(saved)


def mask_config(config: dict[str, Any]) -> dict[str, Any]:
    masked = deepcopy(config)
    if masked.get("api_key"):
        value = str(masked["api_key"])
        masked["api_key"] = "****" + value[-4:] if len(value) > 4 else "****"
    headers = {}
    for key, value in (masked.get("headers") or {}).items():
        headers[key] = "****" if _is_secret_key(key) and value else value
    masked["headers"] = headers
    masked["authorization_status"] = "authorized" if _has_authorization(config) and config.get("enabled") else "missing"
    return masked


def execute_authorized_data_source(
    store: Store,
    tenant_id: str,
    connector_id: str,
    case: dict[str, Any],
    subject: dict[str, Any],
    *,
    authorization_required: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = get_data_source_config(store, tenant_id, connector_id)
    mode = config.get("mode") or MANUAL_ONLY_MODE
    if mode != AUTHORIZED_MODE:
        raise AppError(
            "CONNECTOR_UNAVAILABLE",
            "Data source is not configured for authorized API access.",
            503,
            {"reason": "DATA_SOURCE_CONFIG_REQUIRED", "connector_id": connector_id, "mode": mode, "manual_entry_supported": True, "verification_status": "untested"},
        )
    if not config.get("enabled"):
        raise AppError(
            "CONNECTOR_UNAVAILABLE",
            "Data source is disabled.",
            503,
            {"reason": "DATA_SOURCE_DISABLED", "connector_id": connector_id, "manual_entry_supported": True, "verification_status": "untested"},
        )
    if not config.get("base_url"):
        raise AppError(
            "CONNECTOR_UNAVAILABLE",
            "Data source base URL is missing.",
            503,
            {"reason": "DATA_SOURCE_CONFIG_INCOMPLETE", "connector_id": connector_id, "manual_entry_supported": True, "verification_status": "untested"},
        )
    if authorization_required and not _has_authorization(config):
        raise AppError(
            "CONNECTOR_UNAVAILABLE",
            "Data source authorization is missing.",
            503,
            {"reason": "AUTHORIZATION_MISSING", "connector_id": connector_id, "manual_entry_supported": True, "verification_status": "untested"},
        )

    request_payload = _request_payload(tenant_id, connector_id, case, subject)
    request = _build_request(config, request_payload)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=int(config.get("timeout_seconds") or 10)) as response:
            body = response.read()
            status_code = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raise AppError(
            "CONNECTOR_UNAVAILABLE",
            "Authorized data source returned an error.",
            503,
            {"reason": "HTTP_ERROR", "status_code": exc.code, "connector_id": connector_id, "verification_status": "untested"},
        ) from exc
    except Exception as exc:
        raise AppError(
            "CONNECTOR_UNAVAILABLE",
            "Authorized data source is unavailable.",
            503,
            {"reason": exc.__class__.__name__, "connector_id": connector_id, "verification_status": "untested"},
        ) from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    parsed = _parse_response(body, content_type)
    raw_ref = f"store://authorized-data-sources/{tenant_id}/{connector_id}/{new_id('raw')}"
    records = _normalize_records(config, connector_id, subject, parsed, raw_ref)
    metrics = {
        "records_count": len(records),
        "duration_ms": duration_ms,
        "status_code": status_code,
        "raw_payload_ref": raw_ref,
        "data_source_mode": AUTHORIZED_MODE,
        "verification_status": "untested",
    }
    return records, metrics


def _validate_config(config: dict[str, Any]) -> None:
    mode = config.get("mode") or MANUAL_ONLY_MODE
    if mode not in {AUTHORIZED_MODE, DEMO_MODE, MANUAL_ONLY_MODE}:
        raise AppError("VALIDATION_ERROR", "Unsupported data source mode", 400, {"mode": mode})
    method = (config.get("method") or "POST").upper()
    if method not in {"GET", "POST"}:
        raise AppError("VALIDATION_ERROR", "Unsupported data source method", 400, {"method": method})
    config["method"] = method
    timeout = int(config.get("timeout_seconds") or 10)
    if timeout < 1 or timeout > 60:
        raise AppError("VALIDATION_ERROR", "timeout_seconds must be between 1 and 60", 400)
    config["timeout_seconds"] = timeout
    config["verification_status"] = "untested"


def _build_request(config: dict[str, Any], payload: dict[str, Any]) -> urllib.request.Request:
    method = (config.get("method") or "POST").upper()
    url = _join_url(str(config.get("base_url") or ""), str(config.get("path") or ""))
    headers = {"Accept": "application/json", **(config.get("headers") or {})}
    api_key = config.get("api_key")
    if api_key:
        prefix = (config.get("auth_prefix") or "").strip()
        headers[config.get("auth_header") or "Authorization"] = f"{prefix} {api_key}".strip()
    if method == "GET":
        query = {**(config.get("query_params") or {}), **_query_payload(payload)}
        separator = "&" if urllib.parse.urlsplit(url).query else "?"
        url = url + separator + urllib.parse.urlencode(query)
        data = None
    else:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return urllib.request.Request(url=url, data=data, headers=headers, method=method)


def _normalize_records(config: dict[str, Any], connector_id: str, subject: dict[str, Any], parsed: Any, raw_ref: str) -> list[dict[str, Any]]:
    fetched_at = now_iso()
    items = _records_from_response(parsed, config.get("records_path") or "records")
    records = []
    for index, item in enumerate(items):
        payload = item if isinstance(item, dict) else {"value": item}
        normalized_payload = payload.get("normalized_payload") if isinstance(payload.get("normalized_payload"), dict) else payload
        record_type = payload.get("record_type") or config.get("default_record_type") or _default_record_type(connector_id)
        records.append(
            {
                "id": new_id("ext"),
                "connector_id": connector_id,
                "source_name": payload.get("source_name") or config.get("source_name") or connector_id,
                "source_url": payload.get("source_url") or payload.get("url") or config.get("base_url"),
                "subject_id": subject["id"],
                "record_type": record_type,
                "record_time": payload.get("record_time") or payload.get("published_at") or payload.get("updated_at") or fetched_at,
                "fetched_at": fetched_at,
                "normalized_payload": normalized_payload,
                "raw_payload_ref": f"{raw_ref}/records/{index}",
                "authorization_status": "authorized",
                "verification_status": "untested",
            }
        )
    return records


def _records_from_response(parsed: Any, records_path: str) -> list[Any]:
    value = parsed
    if isinstance(parsed, dict):
        value = _get_path(parsed, records_path)
        if value is None:
            for key in ("records", "data", "items", "results"):
                if isinstance(parsed.get(key), list):
                    value = parsed[key]
                    break
        if value is None:
            value = [parsed]
    if isinstance(value, list):
        return value
    return [value]


def _parse_response(body: bytes, content_type: str) -> Any:
    text = body.decode("utf-8", errors="replace")
    if "json" in content_type.lower() or text.strip().startswith(("{", "[")):
        return json.loads(text)
    return {"records": [{"raw_text": text}]}


def _request_payload(tenant_id: str, connector_id: str, case: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "connector_id": connector_id,
        "subject": {
            "id": subject.get("id"),
            "name": subject.get("name"),
            "unified_social_credit_code": subject.get("unified_social_credit_code"),
            "aliases": subject.get("aliases") or [],
        },
        "case": {
            "id": case.get("id"),
            "case_name": case.get("case_name"),
            "case_type": case.get("case_type"),
            "stage": case.get("stage"),
            "amount": case.get("amount"),
        },
        "requested_at": now_iso(),
    }


def _query_payload(payload: dict[str, Any]) -> dict[str, Any]:
    subject = payload.get("subject") or {}
    case = payload.get("case") or {}
    return {
        "subject_name": subject.get("name") or "",
        "unified_social_credit_code": subject.get("unified_social_credit_code") or "",
        "case_id": case.get("id") or "",
    }


def _get_path(data: dict[str, Any], path: str) -> Any:
    if not path:
        return data
    value: Any = data
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _join_url(base_url: str, path: str) -> str:
    if not path:
        return base_url
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _has_authorization(config: dict[str, Any]) -> bool:
    if config.get("api_key"):
        return True
    headers = config.get("headers") or {}
    return any(_is_secret_key(key) and bool(value) for key, value in headers.items())


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in SECRET_KEYS)


def _default_record_type(connector_id: str) -> str:
    if "auction" in connector_id:
        return "auction"
    if "execution" in connector_id:
        return "execution"
    if "ip" in connector_id:
        return "ip"
    if "bid" in connector_id or "receivable" in connector_id:
        return "bid"
    return "company"