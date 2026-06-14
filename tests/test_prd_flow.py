from fastapi.testclient import TestClient

from law_platform.store import create_memory_store
from law_platform.web import create_app


HEADERS = {
    "Authorization": "Bearer user_owner",
    "X-Tenant-Id": "tenant_demo",
    "X-Request-Id": "req_test",
    "X-Client-Type": "web",
}


def client():
    return TestClient(create_app(create_memory_store()))


def unwrap(response):
    assert response.status_code < 400, response.text
    return response.json()["data"]


def test_execution_case_main_flow_has_sources_reviews_monitoring_and_audit():
    c = client()
    case = unwrap(
        c.post(
            "/api/cases",
            headers=HEADERS,
            json={
                "case_name": "A 公司执行案件",
                "case_type": "execution",
                "cause_of_action": "买卖合同纠纷",
                "amount": 1200000,
                "responsible_lawyer_id": "user_lawyer",
            },
        )
    )

    file_response = unwrap(
        c.post(
            f"/api/cases/{case['id']}/files",
            headers={k: v for k, v in HEADERS.items() if k != "Content-Type"},
            files={"file": ("judgment.txt", "（2026）沪01执123号\n上海市第一中级人民法院\n被执行人某某科技有限公司应支付人民币1200000元。", "text/plain")},
            data={"file_type": "judgment", "sensitivity_level": "L2"},
        )
    )
    parse = unwrap(c.get(f"/api/files/{file_response['id']}/parse-result", headers=HEADERS))
    assert parse["blocks"]
    assert parse["quality_summary"]["has_page_mapping"] is True

    subject_result = unwrap(
        c.post(
            "/api/subjects/resolve",
            headers=HEADERS,
            json={"case_id": case["id"], "name": "某某科技有限公司"},
        )
    )
    subject_id = subject_result["candidates"][0]["subject_id"]

    job = unwrap(
        c.post(
            f"/api/cases/{case['id']}/asset-clue-reports",
            headers=HEADERS,
            json={
                "subject_id": subject_id,
                "connector_ids": ["manual_company_connector", "execution_public_connector", "public_auction_connector"],
                "report_template": "execution_asset_clue_v1",
            },
        )
    )
    assert job["status"] == "completed"

    report = unwrap(c.get(f"/api/reports/{job['report_id']}", headers=HEADERS))
    assert report["generation_status"] == "review_required"
    assert "待人工核验事项" in report["content_md"]
    assert report["asset_clues"]
    assert all(clue["source_refs"] for clue in report["asset_clues"])
    assert all(clue["recommended_action"] for clue in report["asset_clues"])

    reviewed = unwrap(
        c.post(
            f"/api/asset-clues/{report['asset_clues'][0]['id']}/review",
            headers=HEADERS,
            json={"review_status": "confirmed", "comment": "优先核验", "next_action": "create_task"},
        )
    )
    assert reviewed["task"]["status"] == "open"

    target = unwrap(
        c.post(
            "/api/monitor-targets",
            headers=HEADERS,
            json={"case_id": case["id"], "subject_id": subject_id, "event_types": ["new_auction"], "notify_channels": ["in_app"]},
        )
    )
    events = unwrap(c.get("/api/monitor-events", headers=HEADERS))
    event = next(row for row in events if row["id"] == target["initial_event_id"])
    assert event["source_refs"]

    notification_id = c.app.state.platform.store.list("notifications")[0]["id"]
    mobile = unwrap(c.get(f"/bff/mobile/notifications/{notification_id}", headers={**HEADERS, "X-Client-Type": "mobile_h5"}))
    assert mobile["event_id"] == event["id"]
    assert mobile["why_important"]
    assert mobile["recommended_action"]
    assert mobile["action_buttons"] == ["确认", "忽略", "转任务"]

    converted = unwrap(c.post(f"/api/monitor-events/{event['id']}/convert-to-task", headers=HEADERS))
    assert converted["task"]["object_type"] == "monitor_event"

    overview = unwrap(c.get(f"/bff/cases/{case['id']}/overview", headers=HEADERS))
    assert overview["today_highlights"]
    assert overview["pending_reviews"]
    assert overview["tasks"]

    audit_logs = unwrap(c.get("/api/audit-logs", headers=HEADERS))
    actions = {row["action"] for row in audit_logs}
    assert {"case_created", "file_uploaded_and_parsed", "asset_clue_report_generated", "monitor_target_created"} <= actions
