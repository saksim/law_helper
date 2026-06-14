from __future__ import annotations

from typing import Any


def flatten_snapshot(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in (payload or {}).items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(flatten_snapshot(value, path))
        else:
            flat[path] = value
    return flat


def diff_snapshots(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    old = flatten_snapshot(previous or {})
    new = flatten_snapshot(current or {})
    diffs: list[dict[str, Any]] = []
    for field in sorted(set(old) | set(new)):
        if old.get(field) != new.get(field):
            diffs.append({"field": field, "old_value": old.get(field), "new_value": new.get(field)})
    return diffs


def classify_monitor_event(diffs: list[dict[str, Any]]) -> tuple[str, str]:
    fields = " ".join(diff["field"] for diff in diffs)
    if "auction" in fields or "拍卖" in fields:
        return "new_auction", "critical"
    if "execution" in fields or "执行" in fields:
        return "new_execution", "high"
    if "equity" in fields or "shareholder" in fields or "股权" in fields:
        return "equity_freeze", "high"
    return "company_change", "medium"