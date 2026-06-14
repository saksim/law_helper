from fastapi.testclient import TestClient

from law_platform.store import create_memory_store
from law_platform.web import create_app


HEADERS = {"Authorization": "Bearer user_owner", "X-Tenant-Id": "tenant_demo", "X-Request-Id": "req_plugin", "X-Client-Type": "admin"}


def unwrap(response):
    assert response.status_code < 400, response.text
    return response.json()["data"]


def test_plugin_contract_tests_and_feature_flag_rollback_path():
    client = TestClient(create_app(create_memory_store()))
    plugins = unwrap(client.get("/api/plugins", headers=HEADERS))
    assert {plugin["plugin_type"] for plugin in plugins} >= {"DataConnector", "DocumentParser", "ReportTemplate", "Notifier"}

    passed = unwrap(client.post("/api/plugins/manual_company_connector/contract-tests", headers=HEADERS))
    assert passed["status"] == "passed"

    unwrap(client.post("/api/plugins/manual_company_connector/disable", headers=HEADERS))
    failed = unwrap(client.post("/api/plugins/manual_company_connector/contract-tests", headers=HEADERS))
    assert failed["status"] == "failed"
    assert "feature_flag_disabled" in failed["failures"]

    unwrap(client.post("/api/plugins/manual_company_connector/enable", headers=HEADERS))
    passed_again = unwrap(client.post("/api/plugins/manual_company_connector/contract-tests", headers=HEADERS))
    assert passed_again["status"] == "passed"
