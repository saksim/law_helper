from fastapi.testclient import TestClient

from law_platform.store import create_memory_store
from law_platform.web import create_app


HEADERS = {
    "Authorization": "Bearer user_owner",
    "X-Tenant-Id": "tenant_demo",
    "X-Request-Id": "req_p1_p2",
    "X-Client-Type": "admin",
}


def unwrap(response):
    assert response.status_code < 400, response.text
    return response.json()["data"]


def build_case_bundle(client: TestClient):
    case = unwrap(client.post("/api/cases", headers=HEADERS, json={"case_name": "P1/P2 执行案件", "amount": 3600000, "cause_of_action": "买卖合同纠纷"}))
    text = """
（2026）沪01执999号
上海市第一中级人民法院
申请执行人：上海甲方有限公司
被执行人：某某科技有限公司
被执行人应于2026年8月1日前支付人民币3600000元。
"""
    upload = unwrap(
        client.post(
            f"/api/cases/{case['id']}/files",
            headers={k: v for k, v in HEADERS.items() if k != "Content-Type"},
            files={"file": ("judgment.txt", text, "text/plain")},
            data={"file_type": "judgment", "sensitivity_level": "L2"},
        )
    )
    subject = unwrap(client.post("/api/subjects/resolve", headers=HEADERS, json={"case_id": case["id"], "name": "某某科技有限公司"}))
    subject_id = subject["candidates"][0]["subject_id"]
    report_job = unwrap(client.post(f"/api/cases/{case['id']}/asset-clue-reports", headers=HEADERS, json={"subject_id": subject_id}))
    report = unwrap(client.get(f"/api/reports/{report_job['report_id']}", headers=HEADERS))
    return case, upload, subject_id, report


def test_p1_production_enhancement_and_data_source_governance():
    client = TestClient(create_app(create_memory_store()))
    case, _upload, subject_id, report = build_case_bundle(client)

    reviewed = unwrap(
        client.post(
            f"/api/asset-clues/{report['asset_clues'][0]['id']}/review",
            headers=HEADERS,
            json={"review_status": "rejected", "comment": "重复提醒", "usefulness": "not_useful"},
        )
    )
    assert reviewed["clue"]["review_status"] == "rejected"

    target = unwrap(client.post("/api/monitor-targets", headers=HEADERS, json={"case_id": case["id"], "subject_id": subject_id, "event_types": ["new_auction"]}))
    event = unwrap(
        client.post(
            f"/api/monitor-targets/{target['id']}/run-check",
            headers=HEADERS,
            json={"snapshot": {"auction": {"status": "新增拍卖公告", "asset": "厂房"}}},
        )
    )["event"]
    assert event["semantic_summary"]
    unwrap(client.post(f"/api/monitor-events/{event['id']}/ignore", headers=HEADERS))

    dashboard = unwrap(client.get("/bff/team/operations-dashboard", headers=HEADERS))
    assert dashboard["summary"]["case_count"] >= 1
    assert "clue_confirmation_rate" in dashboard["quality"]["metrics"]

    samples = unwrap(client.get("/api/quality/feedback-samples", headers=HEADERS))
    assert {sample["object_type"] for sample in samples} >= {"asset_clue", "monitor_event"}

    failed_health = unwrap(client.post("/api/data-sources/execution_public_connector/health-check", headers=HEADERS, json={"status": "failed", "message": "授权过期"}))
    assert failed_health["status"] == "failed"
    alerts = unwrap(client.get("/api/system-alerts?status=open", headers=HEADERS))
    assert any(alert["source_id"] == "execution_public_connector" for alert in alerts)
    resolved = unwrap(client.post(f"/api/system-alerts/{alerts[-1]['id']}/resolve", headers=HEADERS, json={"resolution": "已更新授权"}))
    assert resolved["status"] == "resolved"

    catalog = unwrap(client.get("/api/data-sources/catalog", headers=HEADERS))
    assert any(row["source_id"] == "execution_public_connector" for row in catalog)
    mapping = unwrap(client.put("/api/data-sources/execution_public_connector/field-mappings", headers=HEADERS, json={"mapping_version": "v2", "mappings": {"caseNo": "normalized_payload.case_no"}}))
    assert mapping["mapping_version"] == "v2"
    quality = unwrap(client.get("/api/data-sources/execution_public_connector/quality", headers=HEADERS))
    assert quality["score"] >= 0
    costs = unwrap(client.get("/api/data-sources/costs", headers=HEADERS))
    assert "sources" in costs

    manual = unwrap(
        client.post(
            f"/api/cases/{case['id']}/external-records/manual",
            headers=HEADERS,
            json={
                "subject_id": subject_id,
                "record_type": "auction",
                "source_name": "人工核验拍卖记录",
                "normalized_payload": {"asset_name": "厂房", "status": "待拍卖"},
                "attachments": [{"attachment_type": "screenshot", "uri": "oss://evidence/manual-auction.png"}],
            },
        )
    )
    assert manual["external_record"]["authorization_status"] == "manual"
    assert client.app.state.platform.store.list("manual_record_attachments")

    unwrap(client.put("/api/data-source-configs/manual_company_connector", headers=HEADERS, json={"enabled": True, "mode": "manual_only", "api_key": "secret-key"}))
    rotation = unwrap(client.post("/api/configs/manual_company_connector/rotate", headers=HEADERS, json={"config_type": "data_source"}))
    assert rotation["masked_config"]["api_key"].startswith("***")

    backup = unwrap(client.post("/api/backup-checks", headers=HEADERS, json={"status": "passed", "restore_drill_status": "passed"}))
    assert backup["status"] == "passed"


def test_p1_case_assistance_flow():
    client = TestClient(create_app(create_memory_store()))
    case, _upload, _subject_id, _report = build_case_bundle(client)

    similar = unwrap(client.post(f"/api/cases/{case['id']}/similar-cases/search", headers=HEADERS, json={}))
    assert similar["similar_cases"][0]["source_ref"]
    assert similar["legal_argument"]["source_ref"]

    matrix = unwrap(client.post(f"/api/cases/{case['id']}/evidence-matrix", headers=HEADERS, json={"fact_claims": ["主体身份", "执行金额"]}))
    assert matrix["matrix_rows"]
    evidence = unwrap(client.patch(f"/api/evidence-items/{matrix['evidence_items'][0]['id']}", headers=HEADERS, json={"status": "confirmed"}))
    assert evidence["status"] == "confirmed"

    draft = unwrap(client.post(f"/api/cases/{case['id']}/draft-documents", headers=HEADERS, json={"title": "执行申请初稿"}))
    assert draft["review_status"] == "pending"
    check = unwrap(client.post(f"/api/draft-documents/{draft['id']}/quality-check", headers=HEADERS, json={}))
    assert {issue["issue_type"] for issue in check["issues"]} >= {"subject_consistency", "amount_consistency", "date_consistency", "evidence_number_consistency"}

    transcript = unwrap(
        client.post(
            f"/api/cases/{case['id']}/transcript-summaries",
            headers=HEADERS,
            json={"transcript_text": "律师：请说明财产情况。\n被执行人：目前有厂房资产。\n律师：需要补充权属证明。"},
        )
    )
    assert transcript["review_status"] == "pending"

    assistance = unwrap(client.get(f"/bff/cases/{case['id']}/case-assistance", headers=HEADERS))
    assert assistance["similar_cases"]
    assert assistance["evidence_matrix"]["matrix_rows"]
    assert assistance["draft_documents"]


def test_p2_platformization_and_knowledge_growth():
    client = TestClient(create_app(create_memory_store()))
    case, _upload, _subject_id, report = build_case_bundle(client)
    unwrap(client.post(f"/api/asset-clues/{report['asset_clues'][0]['id']}/review", headers=HEADERS, json={"review_status": "confirmed", "comment": "可跟进", "usefulness": "useful"}))

    org = unwrap(client.post("/api/organizations", headers=HEADERS, json={"name": "第二演示律所"}))
    team = unwrap(client.post("/api/teams", headers=HEADERS, json={"name": "执行二组", "organization_id": org["id"]}))
    policy = unwrap(client.put(f"/api/teams/{team['id']}/policies", headers=HEADERS, json={"policies": {"model_provider": "private", "notification_channel": "wecom"}}))
    assert policy["policies"]["model_provider"] == "private"

    rollout = unwrap(client.post("/api/platform/plugins/execution_asset_clue_v1/rollout", headers=HEADERS, json={"version": "1.0.1", "rollout_percent": 20}))
    assert rollout["status"] == "rolled_out"
    rollback = unwrap(client.post("/api/platform/plugins/execution_asset_clue_v1/rollback", headers=HEADERS, json={"rollback_to_version": "1.0.0"}))
    assert rollback["status"] == "rolled_back"

    profiles = unwrap(client.get("/api/platform/deployments/profiles", headers=HEADERS))
    assert any(profile["supports_customer_keys"] for profile in profiles)
    migration = unwrap(client.post("/api/platform/migrations/v1.1.0/run", headers=HEADERS, json={"dry_run": True}))
    assert migration["status"] == "dry_run_passed"
    slo = unwrap(client.get("/api/platform/slo", headers=HEADERS))
    assert "availability" in slo["metrics"]
    archive = unwrap(client.get("/api/platform/audit-archives", headers=HEADERS))
    assert archive[-1]["integrity_hash"]

    graph = unwrap(client.get("/api/knowledge/graph", headers=HEADERS))
    assert graph["nodes"]
    node = unwrap(client.get(f"/api/knowledge/nodes/{graph['nodes'][0]['id']}", headers=HEADERS))
    assert node["source_ref"]

    insight = unwrap(client.post("/api/feedback/insights/extract", headers=HEADERS, json={}))
    assert insight["sample_count"] >= 1
    evaluation = unwrap(client.post("/api/evaluations/runs", headers=HEADERS, json={"target_version": "prompt-v2", "baseline_score": 0.7, "candidate_score": 0.73}))
    assert evaluation["status"] == "passed"

    leads = unwrap(client.get("/api/business-leads", headers=HEADERS))
    assert leads
    reviewed_lead = unwrap(client.post(f"/api/business-leads/{leads[0]['id']}/review", headers=HEADERS, json={"status": "valid", "comment": "可由律师跟进"}))
    assert reviewed_lead["status"] == "valid"

    policies = unwrap(client.get("/api/policy-alerts", headers=HEADERS))
    reviewed_policy = unwrap(client.post(f"/api/policy-alerts/{policies[0]['id']}/review", headers=HEADERS, json={"status": "approved", "comment": "可作为内部提示"}))
    assert reviewed_policy["status"] == "approved"

    management = unwrap(client.get("/bff/management/dashboard", headers=HEADERS))
    assert management["metrics"]["case_count"] >= 1
    assert "cost_trend_total" in management["metrics"]
