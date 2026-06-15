from fastapi.testclient import TestClient

from law_platform.store import create_memory_store
from law_platform.web import create_app


HEADERS = {
    "Authorization": "Bearer user_owner",
    "X-Tenant-Id": "tenant_demo",
    "X-Request-Id": "req_qa_acceptance",
    "X-Client-Type": "web",
}

AUDITOR = {
    "Authorization": "Bearer user_auditor",
    "X-Tenant-Id": "tenant_demo",
    "X-Request-Id": "req_qa_auditor",
    "X-Client-Type": "web",
}


def unwrap(response):
    assert response.status_code < 400, response.text
    return response.json()["data"]


def build_acceptance_dataset(client: TestClient) -> str:
    case = unwrap(client.post("/api/cases", headers=HEADERS, json={"case_name": "QA 验收执行案件", "amount": 1800000, "responsible_lawyer_id": "user_lawyer"}))
    content = """
（2026）沪01执456号
上海市第一中级人民法院
案由：买卖合同纠纷
申请执行人：上海甲方有限公司
被执行人：某某科技有限公司
统一社会信用代码 91310000MA1K000000
执行依据：上海仲裁委员会裁决书
被执行人应于2026年7月1日前支付人民币1800000元。
"""
    unwrap(
        client.post(
            f"/api/cases/{case['id']}/files",
            headers={key: value for key, value in HEADERS.items() if key != "Content-Type"},
            files={"file": ("judgment.txt", content, "text/plain")},
            data={"file_type": "judgment", "sensitivity_level": "L2"},
        )
    )
    subject = unwrap(client.post("/api/subjects/resolve", headers=HEADERS, json={"case_id": case["id"], "name": "某某科技有限公司"}))
    subject_id = subject["candidates"][0]["subject_id"]
    job = unwrap(client.post(f"/api/cases/{case['id']}/asset-clue-reports", headers=HEADERS, json={"subject_id": subject_id}))
    report = unwrap(client.get(f"/api/reports/{job['report_id']}", headers=HEADERS))
    unwrap(
        client.post(
            f"/api/asset-clues/{report['asset_clues'][0]['id']}/review",
            headers=HEADERS,
            json={"review_status": "confirmed", "comment": "验收样本确认", "next_action": "create_task"},
        )
    )
    unwrap(client.post(f"/api/reports/{job['report_id']}/review", headers=HEADERS, json={"review_status": "confirmed", "comment": "验收样本报告确认"}))
    exported = client.get(f"/api/reports/{job['report_id']}/export?format=md", headers=HEADERS)
    assert exported.status_code == 200
    unwrap(
        client.post(
            "/api/monitor-targets",
            headers=HEADERS,
            json={"case_id": case["id"], "subject_id": subject_id, "event_types": ["new_auction"], "notify_channels": ["in_app"]},
        )
    )
    for connector_id in ["execution_public_connector", "public_auction_connector"]:
        unwrap(
            client.put(
                f"/api/data-source-configs/{connector_id}",
                headers=HEADERS,
                json={"enabled": True, "mode": "authorized_api", "base_url": "https://authorized.example", "api_key": f"key-{connector_id}"},
            )
        )
    return case["id"]


def complete_acceptance_payload() -> dict:
    passed_tests = {
        "unit": {"status": "passed", "evidence": "python -m pytest tests/test_security_policy.py"},
        "integration": {"status": "passed", "evidence": "python -m pytest tests/test_prd_flow.py tests/test_p0_enhancements.py"},
        "contract": {"status": "passed", "evidence": "python -m pytest tests/test_plugin_contract.py"},
        "data": {"status": "passed", "evidence": "/api/data-dictionary/validate"},
        "security": {"status": "passed", "evidence": "tests/test_security_policy.py"},
        "e2e": {"status": "passed", "evidence": "标准执行案件 E2E 录屏 qa://e2e/001"},
        "usability": {"status": "passed", "evidence": "5 名律师任务记录 qa://ux/001"},
        "mobile": {"status": "passed", "evidence": "移动提醒 3 步处理记录 qa://mobile/001"},
        "regression": {"status": "passed", "evidence": "固定样本回归 qa://regression/001"},
    }
    return {
        "sample_counts": {
            "real_pdf_count": 10,
            "execution_case_count": 5,
            "authorized_data_source_count": 2,
            "monitor_event_count": 20,
            "standard_report_count": 5,
        },
        "test_results": passed_tests,
        "usability_results": {
            "lawyers_completed_without_guidance": 4,
            "lawyers_total": 5,
            "owner_30s": True,
            "mobile_steps": 3,
            "source_judgement": True,
            "error_feedback": True,
        },
        "performance_results": {
            "desktop_home_seconds": 2.4,
            "mobile_notification_seconds": 1.2,
            "list_interaction_ms": 80,
            "upload_feedback_immediate": True,
            "long_task_progress_seconds": 0.8,
        },
        "evidence_refs": {
            "sample_list": "qa://samples/p0-2026-06",
            "e2e_screenshots_or_recordings": "qa://e2e/001",
            "api_plugin_contract_results": "qa://contracts/001",
            "security_results": "qa://security/001",
            "usability_records": "qa://ux/001",
            "defect_list": "qa://defects/001",
            "release_risk_conclusion": "qa://release-risk/001",
        },
        "defects": [],
        "release_risk_conclusion": "P0 验收通过，可进入上线评审。",
    }


def test_qa_acceptance_plan_exposes_07_gates_and_auditor_can_read():
    client = TestClient(create_app(create_memory_store()))
    plan = unwrap(client.get("/api/qa/acceptance-plan", headers=AUDITOR))

    assert plan["version"] == "07-QA_ACCEPTANCE_PLAN"
    assert plan["risk_level"] == "P1"
    assert "案件工作台" in plan["required_scopes"]
    assert "原生 App" in plan["excluded_scopes"]
    assert plan["sample_requirements"]["real_pdf_count"] == 10
    assert "审计日志缺失关键操作" in plan["blocking_conditions"]


def test_qa_acceptance_run_blocks_without_required_evidence():
    client = TestClient(create_app(create_memory_store()))
    run = unwrap(client.post("/api/qa/acceptance-runs", headers=HEADERS, json={}))

    assert run["status"] == "blocked"
    assert run["summary"]["release_ready"] is False
    assert run["evidence_results"]["sample_list"] == "missing"
    assert any(item["condition"] == "审计日志缺失关键操作" and item["status"] == "blocked" for item in run["blocking_conditions"])


def test_qa_acceptance_run_passes_with_full_p0_evidence_and_gate_results():
    client = TestClient(create_app(create_memory_store()))
    build_acceptance_dataset(client)
    run = unwrap(client.post("/api/qa/acceptance-runs", headers=HEADERS, json=complete_acceptance_payload()))

    assert run["status"] == "passed"
    assert run["summary"]["release_ready"] is True
    assert all(status == "passed" for status in run["scope_results"].values())
    assert all(status == "passed" for status in run["sample_counts"].values())
    assert all(result["status"] == "passed" for result in run["test_matrix_results"].values())
    assert all(result["status"] == "passed" for result in run["experience_gate_results"].values())
    assert all(result["status"] == "passed" for result in run["performance_gate_results"].values())
    assert all(status == "clear" for status in [item["status"] for item in run["blocking_conditions"]])

    runs = unwrap(client.get("/api/qa/acceptance-runs", headers=AUDITOR))
    assert runs[-1]["id"] == run["id"]
    audit_logs = unwrap(client.get("/api/audit-logs", headers=HEADERS))
    assert any(row["action"] == "qa_acceptance_run_created" and row["object_id"] == run["id"] for row in audit_logs)
