from fastapi.testclient import TestClient

from law_platform.security import RequestContext, SecurityService
from law_platform.store import create_memory_store
from law_platform.web import create_app


OWNER = {"Authorization": "Bearer user_owner", "X-Tenant-Id": "tenant_demo", "X-Request-Id": "req_owner", "X-Client-Type": "web"}
OTHER = {"Authorization": "Bearer user_other", "X-Tenant-Id": "tenant_demo", "X-Request-Id": "req_other", "X-Client-Type": "web"}
ASSISTANT = {"Authorization": "Bearer user_assistant", "X-Tenant-Id": "tenant_demo", "X-Request-Id": "req_assistant", "X-Client-Type": "web"}


def unwrap(response):
    assert response.status_code < 400, response.text
    return response.json()["data"]


def build_report(client: TestClient):
    case = unwrap(client.post("/api/cases", headers=OWNER, json={"case_name": "安全导出案件", "responsible_lawyer_id": "user_lawyer"}))
    subject = unwrap(client.post("/api/subjects/resolve", headers=OWNER, json={"case_id": case["id"], "name": "某某科技有限公司"}))
    subject_id = subject["candidates"][0]["subject_id"]
    job = unwrap(client.post(f"/api/cases/{case['id']}/asset-clue-reports", headers=OWNER, json={"subject_id": subject_id}))
    return case, job["report_id"], subject_id


def test_case_access_is_explicit_and_audited_on_denial():
    client = TestClient(create_app(create_memory_store()))
    case = unwrap(client.post("/api/cases", headers=OWNER, json={"case_name": "权限测试案件", "responsible_lawyer_id": "user_lawyer"}))

    denied = client.get(f"/api/cases/{case['id']}", headers=OTHER)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    audit = unwrap(client.get("/api/audit-logs", headers=OWNER))
    assert any(row["action"] == "permission_denied" and row["object_id"] == case["id"] for row in audit)


def test_l4_sensitive_upload_blocks_assistant_and_model_policy_blocks_external_provider():
    store = create_memory_store()
    client = TestClient(create_app(store))
    case = unwrap(client.post("/api/cases", headers=OWNER, json={"case_name": "敏感材料案件", "responsible_lawyer_id": "user_lawyer"}))

    denied = client.post(
        f"/api/cases/{case['id']}/files",
        headers={k: v for k, v in ASSISTANT.items() if k != "Content-Type"},
        files={"file": ("bank.txt", "银行流水和身份证信息", "text/plain")},
        data={"file_type": "evidence", "sensitivity_level": "L4"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    security = SecurityService(store)
    ctx = RequestContext(tenant_id="tenant_demo", actor_id="user_owner", request_id="req_policy")
    try:
        security.check_model_policy(ctx, case["id"], "L4", provider_external=True)
    except Exception as exc:
        assert getattr(exc, "code", "") == "DATA_POLICY_BLOCKED"
    else:
        raise AssertionError("L4 external model call should be blocked")

    invocations = unwrap(client.get("/api/model-invocations", headers=OWNER))
    assert invocations[-1]["policy_blocked"] is True


def test_sensitive_material_view_is_gated_and_redacted_by_default():
    client = TestClient(create_app(create_memory_store()))
    case = unwrap(client.post("/api/cases", headers=OWNER, json={"case_name": "敏感展示案件", "responsible_lawyer_id": "user_lawyer"}))
    raw_id = "110101199003074512"
    raw_bank = "6222020202020202020"
    uploaded = unwrap(
        client.post(
            f"/api/cases/{case['id']}/files",
            headers={k: v for k, v in OWNER.items() if k != "Content-Type"},
            files={"file": ("secret.txt", f"身份证号 {raw_id}\n银行账号 {raw_bank}", "text/plain")},
            data={"file_type": "evidence", "sensitivity_level": "L4"},
        )
    )

    denied = client.get(f"/api/files/{uploaded['id']}/parse-result", headers=ASSISTANT)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    parsed = unwrap(client.get(f"/api/files/{uploaded['id']}/parse-result", headers=OWNER))
    combined = "\n".join(block["text"] for block in parsed["blocks"])
    assert raw_id not in combined
    assert raw_bank not in combined
    assert "110101********4512" in combined
    assert "6222****2020" in combined

    mobile_headers = {**OWNER, "X-Client-Type": "mobile_h5"}
    mobile = unwrap(client.get(f"/api/files/{uploaded['id']}/parse-result", headers=mobile_headers))
    assert all(block["mobile_raw_hidden"] for block in mobile["blocks"])
    assert {block["text"] for block in mobile["blocks"]} == {"敏感材料不在移动端展示，请在桌面端查看。"}


def test_report_export_requires_review_and_records_watermark_integrity():
    client = TestClient(create_app(create_memory_store()))
    _case, report_id, _subject_id = build_report(client)

    draft_export = client.get(f"/api/reports/{report_id}/export?format=md", headers=OWNER)
    assert draft_export.status_code == 409
    assert draft_export.json()["error"]["code"] == "REVIEW_REQUIRED"

    unwrap(client.post(f"/api/reports/{report_id}/review", headers=OWNER, json={"review_status": "confirmed"}))
    exported = client.get(f"/api/reports/{report_id}/export?format=md", headers=OWNER)
    assert exported.status_code == 200
    assert "导出水印" in exported.text
    assert "操作人=user_owner" in exported.text

    export_record = client.app.state.platform.store.list("report_exports")[-1]
    assert export_record["watermark"] in exported.text
    audit = unwrap(client.get("/api/audit-logs", headers=OWNER))
    assert any(row["action"] == "report_exported" for row in audit)
    assert all(row.get("integrity_hash") for row in audit)


def test_monitor_events_and_mobile_notifications_are_least_privilege_and_redacted():
    client = TestClient(create_app(create_memory_store()))
    case, _report_id, subject_id = build_report(client)
    target = unwrap(
        client.post(
            "/api/monitor-targets",
            headers=OWNER,
            json={"case_id": case["id"], "subject_id": subject_id, "event_types": ["new_auction"], "notify_channels": ["in_app"]},
        )
    )

    other_events = unwrap(client.get("/api/monitor-events", headers=OTHER))
    assert all(event["monitor_target_id"] != target["id"] for event in other_events)

    raw_id = "110101199003074512"
    raw_bank = "6222020202020202020"
    unwrap(
        client.post(
            f"/api/monitor-targets/{target['id']}/run-check",
            headers=OWNER,
            json={"snapshot": {"auction": {"status": "新增", "bank_account": raw_bank}}, "title": f"发现身份证{raw_id}和银行账号{raw_bank}"},
        )
    )
    notification_id = client.app.state.platform.store.list("notifications")[-1]["id"]
    mobile = unwrap(client.get(f"/bff/mobile/notifications/{notification_id}", headers={**OWNER, "X-Client-Type": "mobile_h5"}))
    serialized = str(mobile)
    assert raw_id not in serialized
    assert raw_bank not in serialized
    assert "110101********4512" in serialized
    assert "6222****2020" in serialized
