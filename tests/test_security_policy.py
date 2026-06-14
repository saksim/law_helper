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
