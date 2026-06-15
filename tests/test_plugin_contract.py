from fastapi.testclient import TestClient

from law_platform.models import now_iso
from law_platform.store import create_memory_store
from law_platform.web import create_app
from law_platform.worker import enqueue_job


HEADERS = {"Authorization": "Bearer user_owner", "X-Tenant-Id": "tenant_demo", "X-Request-Id": "req_plugin", "X-Client-Type": "admin"}


def unwrap(response):
    assert response.status_code < 400, response.text
    return response.json()["data"]


def test_plugin_contract_tests_and_feature_flag_rollback_path():
    store = create_memory_store()
    client = TestClient(create_app(store))
    plugins = unwrap(client.get("/api/plugins", headers=HEADERS))
    assert {plugin["plugin_type"] for plugin in plugins} >= {"DataConnector", "DocumentParser", "Extractor", "Scorer", "ModelProvider", "ReportTemplate", "Notifier", "ReviewPolicy"}

    parser = next(plugin for plugin in plugins if plugin["plugin_id"] == "basic_document_parser")
    assert "table_placeholders" in parser["parser_contract"]["required_outputs"]
    template = next(plugin for plugin in plugins if plugin["plugin_id"] == "execution_asset_clue_v1")
    assert {"report_type", "required_inputs", "required_citations", "output_sections", "review_required_sections"} <= set(template["template_contract"])
    notifier = next(plugin for plugin in plugins if plugin["plugin_id"] == "in_app_notifier")
    assert {"title", "event_type", "why_important", "source_refs", "detected_at", "recommended_action", "deep_link", "action_buttons"} <= set(notifier["notification_contract"]["required_payload_fields"])

    passed = unwrap(client.post("/api/plugins/manual_company_connector/contract-tests", headers=HEADERS))
    assert passed["status"] == "passed"
    assert not passed["failures"]

    enqueue_job(store, "tenant_demo", None, "connector_retry", {"connector_id": "manual_company_connector"}, "user_owner")
    store.insert(
        "plugin_runs",
        {
            "id": "run_manual_running",
            "run_id": "pluginrun_manual_running",
            "tenant_id": "tenant_demo",
            "case_id": None,
            "actor_id": "user_owner",
            "plugin_id": "manual_company_connector",
            "status": "running",
            "started_at": now_iso(),
            "metrics": {},
        },
    )

    disabled = unwrap(client.post("/api/plugins/manual_company_connector/disable", headers=HEADERS))
    assert disabled["last_rollback"]["rollback_to_version"] == disabled["version"]
    assert disabled["last_rollback"]["cancelled_jobs"] == 1
    assert disabled["last_rollback"]["cancelled_plugin_runs"] == 1
    assert store.list("jobs")[0]["status"] == "cancelled"
    assert store.get("plugin_runs", "run_manual_running")["status"] == "cancelled"
    failed = unwrap(client.post("/api/plugins/manual_company_connector/contract-tests", headers=HEADERS))
    assert failed["status"] == "failed"
    assert "feature_flag_disabled" in failed["failures"]

    unwrap(client.post("/api/plugins/manual_company_connector/enable", headers=HEADERS))
    passed_again = unwrap(client.post("/api/plugins/manual_company_connector/contract-tests", headers=HEADERS))
    assert passed_again["status"] == "passed"

    all_plugins = unwrap(client.get("/api/plugins", headers=HEADERS))
    for plugin in all_plugins:
        result = unwrap(client.post(f"/api/plugins/{plugin['plugin_id']}/contract-tests", headers=HEADERS))
        assert result["status"] == "passed"
