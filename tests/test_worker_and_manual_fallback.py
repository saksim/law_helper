from fastapi.testclient import TestClient

from law_platform.store import create_memory_store
from law_platform.web import create_app


HEADERS = {
    "Authorization": "Bearer user_owner",
    "X-Tenant-Id": "tenant_demo",
    "X-Request-Id": "req_worker",
    "X-Client-Type": "web",
}


def unwrap(response):
    assert response.status_code < 400, response.text
    return response.json()["data"]


def build_case_and_subject(client: TestClient):
    case = unwrap(client.post("/api/cases", headers=HEADERS, json={"case_name": "Worker fallback case", "amount": 1800000}))
    subject = unwrap(client.post("/api/subjects/resolve", headers=HEADERS, json={"case_id": case["id"], "name": "Alpha Tech Co"}))
    return case, subject["candidates"][0]["subject_id"]


def test_monitor_worker_schedules_and_runs_due_jobs():
    client = TestClient(create_app(create_memory_store()))
    case, subject_id = build_case_and_subject(client)
    target = unwrap(
        client.post(
            "/api/monitor-targets",
            headers=HEADERS,
            json={"case_id": case["id"], "subject_id": subject_id, "event_types": ["new_auction"], "notify_channels": ["in_app"]},
        )
    )

    scheduled = unwrap(client.post("/api/jobs/schedule-monitor-checks", headers=HEADERS))
    assert len(scheduled["created"]) == 1
    assert scheduled["created"][0]["payload"]["target_id"] == target["id"]

    queued = unwrap(client.get("/api/jobs?status=queued", headers=HEADERS))
    assert queued and queued[0]["job_type"] == "monitor_check"

    run = unwrap(client.post("/api/jobs/run-due", headers=HEADERS, json={"limit": 5}))
    assert run["processed"] == 1
    assert run["jobs"][0]["status"] == "succeeded"
    assert run["jobs"][0]["result"]["snapshot"]


def test_connector_failure_creates_alert_retry_job_and_manual_record_resolves_alert():
    client = TestClient(create_app(create_memory_store()))
    case, subject_id = build_case_and_subject(client)

    unwrap(client.post("/api/plugins/public_auction_connector/disable", headers=HEADERS))
    job = unwrap(
        client.post(
            f"/api/cases/{case['id']}/asset-clue-reports",
            headers=HEADERS,
            json={"subject_id": subject_id, "connector_ids": ["public_auction_connector", "execution_public_connector"]},
        )
    )
    assert job["status"] == "completed"
    assert job["connector_warnings"]
    assert job["connector_warnings"][0]["connector_id"] == "public_auction_connector"

    alerts = unwrap(client.get("/api/connector-alerts?status=open", headers=HEADERS))
    assert len(alerts) == 1
    assert alerts[0]["suggested_action"] == "manual_external_record"
    assert alerts[0]["manual_entry_endpoint"].endswith("/external-records/manual")

    retry_jobs = unwrap(client.get("/api/jobs?status=queued", headers=HEADERS))
    assert any(row["job_type"] == "connector_retry" and row["payload"]["alert_id"] == alerts[0]["id"] for row in retry_jobs)

    manual = unwrap(
        client.post(
            f"/api/cases/{case['id']}/external-records/manual",
            headers=HEADERS,
            json={
                "subject_id": subject_id,
                "connector_id": "manual_auction_entry",
                "source_name": "Manual auction notice",
                "source_url": "manual://auction/notice-1",
                "record_type": "auction",
                "normalized_payload": {"asset_name": "Factory asset", "starting_price": "pending verification", "status": "manual supplement"},
                "alert_id": alerts[0]["id"],
            },
        )
    )
    assert manual["external_record"]["authorization_status"] == "manual"
    assert manual["asset_clues"]
    assert manual["resolved_alert"]["status"] == "resolved"
    assert manual["resolved_alert"]["resolution"] == "manual_record_created"

    resolved = unwrap(client.get("/api/connector-alerts", headers=HEADERS))
    assert resolved[0]["manual_external_record_id"] == manual["external_record"]["id"]

    actions = {row["action"] for row in unwrap(client.get("/api/audit-logs", headers=HEADERS))}
    assert {"connector_failure_alert_created", "manual_external_record_created"} <= actions