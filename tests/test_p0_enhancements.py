from fastapi.testclient import TestClient

from law_platform.store import create_memory_store
from law_platform.web import create_app


HEADERS = {
    "Authorization": "Bearer user_owner",
    "X-Tenant-Id": "tenant_demo",
    "X-Request-Id": "req_p0_plus",
    "X-Client-Type": "web",
}


def unwrap(response):
    assert response.status_code < 400, response.text
    return response.json()["data"]


def build_case(client: TestClient):
    case = unwrap(client.post("/api/cases", headers=HEADERS, json={"case_name": "P0 增强执行案件", "amount": 2200000, "responsible_lawyer_id": "user_lawyer"}))
    text = """
（2026）沪01执123号
上海市第一中级人民法院
案由：买卖合同纠纷
申请执行人：上海甲方有限公司
被执行人：某某科技有限公司
统一社会信用代码 91310000MA1K000000
执行依据：上海仲裁委员会裁决书
被执行人应于2026年7月1日前支付人民币2200000元。
"""
    upload = unwrap(
        client.post(
            f"/api/cases/{case['id']}/files",
            headers={k: v for k, v in HEADERS.items() if k != "Content-Type"},
            files={"file": ("judgment.txt", text, "text/plain")},
            data={"file_type": "judgment", "sensitivity_level": "L2"},
        )
    )
    return case, upload


def test_document_entities_are_written_back_to_case_overview():
    client = TestClient(create_app(create_memory_store()))
    case, upload = build_case(client)

    parse = unwrap(client.get(f"/api/files/{upload['id']}/parse-result", headers=HEADERS))
    extracted_types = set(parse["quality_summary"]["extracted_entity_types"])
    assert {"case_no", "court", "cause_of_action", "deadline", "execution_basis", "party", "amount"} <= extracted_types

    overview = unwrap(client.get(f"/bff/cases/{case['id']}/overview", headers=HEADERS))
    summary = overview["case"]["extracted_summary"]
    assert summary["cause_of_action"] == "买卖合同纠纷"
    assert summary["execution_basis"] == "上海仲裁委员会裁决书"
    assert summary["deadlines"]
    assert summary["parties"]


def test_report_covers_p0_clue_types_score_breakdown_review_and_export():
    client = TestClient(create_app(create_memory_store()))
    case, _upload = build_case(client)
    subject = unwrap(client.post("/api/subjects/resolve", headers=HEADERS, json={"case_id": case["id"], "name": "某某科技有限公司", "aliases": ["某某科技旧称"]}))
    subject_id = subject["candidates"][0]["subject_id"]

    job = unwrap(client.post(f"/api/cases/{case['id']}/asset-clue-reports", headers=HEADERS, json={"subject_id": subject_id}))
    report = unwrap(client.get(f"/api/reports/{job['report_id']}", headers=HEADERS))
    clue_types = {clue["clue_type"] for clue in report["asset_clues"]}
    assert {"equity", "related_subject", "execution", "auction", "ip", "bid", "receivable"} <= clue_types
    assert "知识产权和经营权益线索" in report["content_md"]
    assert "招投标/应收账款线索" in report["content_md"]
    for clue in report["asset_clues"]:
        assert set(clue["score_breakdown"]) == {"actionability", "value_scale", "freshness", "credibility", "relation_strength", "action_cost"}
        assert clue["verification_items"]
        assert clue["why_important"]

    edited = unwrap(
        client.post(
            f"/api/asset-clues/{report['asset_clues'][0]['id']}/review",
            headers=HEADERS,
            json={"review_status": "edited", "comment": "补充核验意见", "corrected_fields": {"estimated_value": "已人工核验"}, "usefulness": "useful"},
        )
    )
    assert edited["clue"]["estimated_value"] == "已人工核验"
    assert client.app.state.platform.store.list("feedback_records")

    reviewed_report = unwrap(client.post(f"/api/reports/{job['report_id']}/review", headers=HEADERS, json={"review_status": "confirmed", "comment": "可进入下一步"}))
    assert reviewed_report["generation_status"] == "confirmed"

    exported = client.get(f"/api/reports/{job['report_id']}/export?format=word", headers=HEADERS)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/msword")
    assert client.app.state.platform.store.list("report_exports")


def test_monitor_field_diff_creates_event_and_delivery_records_for_channels():
    client = TestClient(create_app(create_memory_store()))
    case, _upload = build_case(client)
    subject = unwrap(client.post("/api/subjects/resolve", headers=HEADERS, json={"case_id": case["id"], "name": "某某科技有限公司"}))
    subject_id = subject["candidates"][0]["subject_id"]
    target = unwrap(
        client.post(
            "/api/monitor-targets",
            headers=HEADERS,
            json={"case_id": case["id"], "subject_id": subject_id, "event_types": ["new_auction", "equity_freeze"], "notify_channels": ["in_app", "feishu", "wecom", "email"]},
        )
    )

    result = unwrap(
        client.post(
            f"/api/monitor-targets/{target['id']}/run-check",
            headers=HEADERS,
            json={"snapshot": {"auction": {"status": "新增拍卖公告"}, "equity": {"freeze": "新增股权冻结"}}, "title": "发现新增拍卖与股权冻结"},
        )
    )
    assert result["diffs"]
    assert result["event"]["field_diffs"]
    assert result["event"]["event_type"] in {"new_auction", "equity_freeze", "company_change"}

    deliveries = client.app.state.platform.store.list("notification_deliveries")
    channels = {delivery["channel"] for delivery in deliveries}
    assert {"in_app", "feishu", "wecom", "email"} <= channels
    assert all(delivery["deep_link"].startswith("/mobile/notifications/") for delivery in deliveries)