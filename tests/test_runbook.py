from fastapi.testclient import TestClient

from law_platform.store import create_memory_store
from law_platform.web import create_app
from test_qa_acceptance import AUDITOR, HEADERS, build_acceptance_dataset, complete_acceptance_payload, unwrap


def test_runbook_exposes_09_operations_manual_and_dictionary_schema():
    client = TestClient(create_app(create_memory_store()))
    runbook = unwrap(client.get("/api/runbook", headers=AUDITOR))

    assert runbook["version"] == "09-RUNBOOK"
    assert runbook["post_launch_observation_window_days"] == 7
    assert {component["key"] for component in runbook["operating_components"]} >= {
        "web_bff",
        "api_service",
        "worker",
        "model_gateway",
        "notification_channels",
    }
    assert "permission_anomaly" in {playbook["key"] for playbook in runbook["fault_playbooks"]}
    assert "plugin" in {strategy["target"] for strategy in runbook["rollback_strategies"]}
    assert "worker_queue_backlog" in {metric["key"] for metric in runbook["alert_metrics"]}

    dictionary = unwrap(client.get("/api/data-dictionary", headers=AUDITOR))
    assert "runbook_checks" in dictionary["schemas"]
    assert "runbook_incidents" in dictionary["schemas"]


def test_runbook_status_requires_deployment_evidence_and_records_checks():
    client = TestClient(create_app(create_memory_store()))
    status = unwrap(client.get("/api/runbook/status", headers=AUDITOR))

    assert status["overall_status"] == "needs_runbook_evidence"
    assert status["deployment_results"]["environment_variables"]["status"] == "missing"

    check = unwrap(
        client.post(
            "/api/runbook/checks",
            headers=HEADERS,
            json={
                "check_key": "environment_variables",
                "check_type": "pre_deployment",
                "status": "passed",
                "evidence_refs": {"env": "ops://env/p0"},
                "notes": "P0 environment variables verified.",
            },
        )
    )
    assert check["check_key"] == "environment_variables"
    assert check["runbook_status"]["deployment_results"]["environment_variables"]["status"] == "passed"

    checks = unwrap(client.get("/api/runbook/checks", headers=AUDITOR))
    assert checks[-1]["id"] == check["id"]
    audit_logs = unwrap(client.get("/api/audit-logs", headers=HEADERS))
    assert any(row["action"] == "runbook_check_recorded" and row["object_id"] == check["id"] for row in audit_logs)


def test_runbook_ready_after_p0_acceptance_and_blocks_on_p1_incident():
    client = TestClient(create_app(create_memory_store()))
    build_acceptance_dataset(client)
    qa_run = unwrap(client.post("/api/qa/acceptance-runs", headers=HEADERS, json=complete_acceptance_payload()))
    assert qa_run["status"] == "passed"

    status = unwrap(client.get("/api/runbook/status", headers=AUDITOR))
    assert status["overall_status"] == "ready_for_pilot_operations"
    assert all(result["status"] == "passed" for result in status["deployment_results"].values())

    incident = unwrap(
        client.post(
            "/api/runbook/incidents",
            headers=HEADERS,
            json={
                "incident_type": "permission_anomaly",
                "severity": "P1",
                "affected_component": "api_service",
                "summary": "Unauthorized case visibility suspected.",
                "detection_source": "audit_logs",
                "diagnosis": ["Freeze session", "Check tenant id", "Review audit scope"],
                "actions": ["Session frozen"],
                "rollback_strategy": "Freeze affected access and enter security flow.",
                "evidence_refs": {"audit": "audit://permission/001"},
            },
        )
    )
    assert incident["runbook_status"]["overall_status"] == "blocked"
    assert incident["runbook_status"]["fault_readiness"]["permission_anomaly"]["status"] == "active_incident"

    resolved = unwrap(
        client.post(
            f"/api/runbook/incidents/{incident['id']}/resolve",
            headers=HEADERS,
            json={
                "resolution": "Role mapping corrected and regression checked.",
                "actions": ["Role mapping corrected", "Access regression completed"],
                "evidence_refs": {"regression": "qa://security/access-regression"},
            },
        )
    )
    assert resolved["status"] == "resolved"
    assert resolved["runbook_status"]["overall_status"] == "ready_for_pilot_operations"

    incidents = unwrap(client.get("/api/runbook/incidents", headers=AUDITOR))
    assert incidents[-1]["id"] == incident["id"]
    audit_logs = unwrap(client.get("/api/audit-logs", headers=HEADERS))
    actions = {row["action"] for row in audit_logs}
    assert {"runbook_incident_created", "runbook_incident_resolved"} <= actions
