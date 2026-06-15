from fastapi.testclient import TestClient

from law_platform.store import create_memory_store
from law_platform.web import create_app
from test_qa_acceptance import AUDITOR, HEADERS, build_acceptance_dataset, complete_acceptance_payload, unwrap


def test_implementation_plan_exposes_08_delivery_blueprint():
    client = TestClient(create_app(create_memory_store()))
    plan = unwrap(client.get("/api/implementation-plan", headers=AUDITOR))

    assert plan["version"] == "08-IMPLEMENTATION_PLAN"
    assert plan["suggested_cycle_weeks"] == "10-14"
    assert len(plan["phases"]) == 5
    assert [sprint["key"] for sprint in plan["sprints"]] == ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]
    assert {dependency["key"] for dependency in plan["dependencies"]} == {
        "samples",
        "data_source_authorization",
        "data_classification",
        "ux_prototype",
    }
    assert plan["risks"]
    assert plan["test_status"] == "untested"

    dictionary = unwrap(client.get("/api/data-dictionary", headers=AUDITOR))
    assert "implementation_checkpoints" in dictionary["schemas"]


def test_implementation_status_marks_empty_workspace_as_phase_0_missing():
    client = TestClient(create_app(create_memory_store()))
    status = unwrap(client.get("/api/implementation-status", headers=AUDITOR))

    assert status["overall_status"] == "in_progress"
    assert status["current_phase"] == "phase_0"
    assert status["phase_results"]["phase_0"]["status"] == "missing"
    assert status["dependency_results"]["samples"]["status"] == "missing"
    assert status["dependency_results"]["data_source_authorization"]["status"] == "missing"
    assert status["risk_results"]["lawyer_adoption"]["status"] == "active"
    assert status["snapshot"]["cases"] == 0


def test_implementation_status_reaches_pilot_ready_after_full_p0_acceptance():
    client = TestClient(create_app(create_memory_store()))
    build_acceptance_dataset(client)
    run = unwrap(client.post("/api/qa/acceptance-runs", headers=HEADERS, json=complete_acceptance_payload()))
    assert run["status"] == "passed"

    status = unwrap(client.get("/api/implementation-status", headers=AUDITOR))
    assert status["overall_status"] == "ready_for_pilot"
    assert status["current_phase"] == "pilot_ready"
    assert all(result["status"] == "passed" for result in status["phase_results"].values())
    assert status["milestone_results"]["M5"]["status"] == "passed"

    checkpoint = unwrap(
        client.post(
            "/api/implementation-checkpoints",
            headers=HEADERS,
            json={
                "phase": "phase_4",
                "sprint": "S6",
                "milestone": "M5",
                "dependency_statuses": {"samples": "passed", "ux_prototype": "passed"},
                "risk_statuses": {"lawyer_adoption": "controlled"},
                "evidence_refs": {"qa_acceptance_run_id": run["id"]},
                "notes": "Pilot launch gate is ready.",
            },
        )
    )
    assert checkpoint["implementation_status"]["overall_status"] == "ready_for_pilot"

    checkpoints = unwrap(client.get("/api/implementation-checkpoints", headers=AUDITOR))
    assert checkpoints[-1]["id"] == checkpoint["id"]
    audit_logs = unwrap(client.get("/api/audit-logs", headers=HEADERS))
    assert any(row["action"] == "implementation_checkpoint_created" and row["object_id"] == checkpoint["id"] for row in audit_logs)
