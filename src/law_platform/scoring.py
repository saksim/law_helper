from __future__ import annotations

from datetime import datetime
from typing import Any


def score_external_record(record: dict[str, Any], case: dict[str, Any]) -> dict[str, int]:
    record_type = record.get("record_type", "")
    payload = record.get("normalized_payload") or {}
    actionability = {
        "auction": 88,
        "execution": 80,
        "company": 66,
        "ip": 62,
        "bid": 72,
        "receivable": 74,
        "related_subject": 64,
    }.get(record_type, 55)
    value_scale = 60
    if case.get("amount"):
        value_scale = 78
    if payload.get("estimated_value") or payload.get("starting_price") or payload.get("contract_amount"):
        value_scale = max(value_scale, 82)
    freshness = 80 if record.get("record_time") else 65
    credibility = 88 if record.get("authorization_status") == "authorized" else 62
    relation_strength = 82 if record.get("subject_id") else 55
    action_cost = {
        "auction": 70,
        "execution": 76,
        "company": 58,
        "ip": 52,
        "bid": 62,
        "receivable": 66,
        "related_subject": 50,
    }.get(record_type, 55)
    return {
        "actionability": actionability,
        "value_scale": value_scale,
        "freshness": freshness,
        "credibility": credibility,
        "relation_strength": relation_strength,
        "action_cost": action_cost,
    }


def total_score(breakdown: dict[str, int]) -> int:
    weights = {
        "actionability": 0.25,
        "value_scale": 0.2,
        "freshness": 0.15,
        "credibility": 0.2,
        "relation_strength": 0.12,
        "action_cost": 0.08,
    }
    return int(round(sum(breakdown[key] * weights[key] for key in weights)))