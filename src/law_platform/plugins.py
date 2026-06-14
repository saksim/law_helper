from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import AppError
from .models import now_iso, new_id
from .store import Store


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    plugin_name: str
    plugin_type: str
    version: str
    owner: str
    status: str
    feature_flag: str
    supported_data_levels: list[str]
    required_permissions: list[str]
    compliance: dict[str, Any]
    contract_tests: list[str]
    rollback: dict[str, Any]

    def to_dict(self, enabled: bool = True) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["id"] = self.plugin_id
        data["enabled"] = enabled
        return data


PLUGIN_MANIFESTS = [
    PluginManifest("manual_company_connector", "人工补录工商连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.manual_company.enabled", ["L0", "L1"], ["company.search", "company.risk"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_company_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.manual_company.enabled"}),
    PluginManifest("execution_public_connector", "公开执行信息连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.execution_public.enabled", ["L0", "L1"], ["execution.search"], {"authorized_api_required": True, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_execution_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.execution_public.enabled"}),
    PluginManifest("public_auction_connector", "司法拍卖公开信息连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.public_auction.enabled", ["L0", "L1"], ["auction.search"], {"authorized_api_required": True, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_auction_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.public_auction.enabled"}),
    PluginManifest("ip_rights_connector", "知识产权公开信息连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.ip_rights.enabled", ["L0", "L1"], ["ip.search"], {"authorized_api_required": True, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_ip_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.ip_rights.enabled"}),
    PluginManifest("bid_receivable_connector", "招投标与应收账款连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.bid_receivable.enabled", ["L0", "L1"], ["bid.search", "receivable.search"], {"authorized_api_required": True, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_bid_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.bid_receivable.enabled"}),
    PluginManifest("basic_document_parser", "基础文档解析器", "DocumentParser", "1.0.0", "ai-team", "active", "parser.basic_document.enabled", ["L0", "L1", "L2", "L3", "L4"], ["file.parse"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["output_markdown", "preserve_page_mapping", "flag_low_confidence"], {"disable_feature_flag": "parser.basic_document.enabled"}),
    PluginManifest("execution_asset_clue_v1", "执行财产线索报告模板", "ReportTemplate", "1.0.0", "legal-team", "active", "report.execution_asset_clue_v1.enabled", ["L0", "L1", "L2"], ["report.generate"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["required_sections", "required_citations", "review_required_sections"], {"disable_feature_flag": "report.execution_asset_clue_v1.enabled"}),
    PluginManifest("in_app_notifier", "站内通知器", "Notifier", "1.0.0", "platform-team", "active", "notifier.in_app.enabled", ["L0", "L1", "L2"], ["notification.send"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["include_source_reference", "include_action_buttons", "deep_link_required"], {"disable_feature_flag": "notifier.in_app.enabled"}),
    PluginManifest("feishu_notifier", "飞书通知器", "Notifier", "1.0.0", "platform-team", "active", "notifier.feishu.enabled", ["L0", "L1", "L2"], ["notification.send"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["include_source_reference", "include_action_buttons", "deep_link_required"], {"disable_feature_flag": "notifier.feishu.enabled"}),
    PluginManifest("wecom_notifier", "企业微信通知器", "Notifier", "1.0.0", "platform-team", "active", "notifier.wecom.enabled", ["L0", "L1", "L2"], ["notification.send"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["include_source_reference", "include_action_buttons", "deep_link_required"], {"disable_feature_flag": "notifier.wecom.enabled"}),
    PluginManifest("email_notifier", "邮件通知器", "Notifier", "1.0.0", "platform-team", "active", "notifier.email.enabled", ["L0", "L1", "L2"], ["notification.send"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["include_source_reference", "include_action_buttons", "deep_link_required"], {"disable_feature_flag": "notifier.email.enabled"}),
]


class PluginService:
    def __init__(self, store: Store):
        self.store = store
        self.ensure_registry()

    def ensure_registry(self) -> None:
        existing = {plugin["plugin_id"]: plugin for plugin in self.store.list("plugin_registry")}
        rows = []
        for manifest in PLUGIN_MANIFESTS:
            row = existing.get(manifest.plugin_id, manifest.to_dict(enabled=True))
            rows.append(row)
        self.store.replace_collection("plugin_registry", rows)

    def list_plugins(self) -> list[dict[str, Any]]:
        self.ensure_registry()
        return self.store.list("plugin_registry")

    def get(self, plugin_id: str) -> dict[str, Any]:
        plugin = self.store.find_one("plugin_registry", plugin_id=plugin_id)
        if not plugin:
            raise AppError("VALIDATION_ERROR", "插件不存在", 404)
        return plugin

    def enable_by_plugin_id(self, plugin_id: str, enabled: bool) -> dict[str, Any]:
        plugins = self.store.list("plugin_registry")
        for plugin in plugins:
            if plugin["plugin_id"] == plugin_id:
                plugin["enabled"] = enabled
                self.store.replace_collection("plugin_registry", plugins)
                return plugin
        raise AppError("VALIDATION_ERROR", "插件不存在", 404)

    def run_contract_tests(self, plugin_id: str) -> dict[str, Any]:
        plugin = self.get(plugin_id)
        failures = []
        required = ["plugin_id", "plugin_name", "plugin_type", "version", "feature_flag", "supported_data_levels", "contract_tests"]
        for field in required:
            if not plugin.get(field):
                failures.append(f"missing_{field}")
        compliance = plugin.get("compliance") or {}
        if compliance.get("bypass_captcha_allowed"):
            failures.append("bypass_captcha_not_allowed")
        if not plugin.get("enabled", True):
            failures.append("feature_flag_disabled")
        if plugin.get("plugin_type") == "DataConnector" and "L1" not in plugin.get("supported_data_levels", []):
            failures.append("data_connector_must_support_L1")
        if plugin.get("plugin_type") == "Notifier" and "deep_link_required" not in plugin.get("contract_tests", []):
            failures.append("notifier_deep_link_required")
        return {"plugin_id": plugin_id, "status": "passed" if not failures else "failed", "failures": failures, "checked_at": now_iso()}

    def execute_connector(self, plugin_id: str, tenant_id: str, case: dict[str, Any], subject: dict[str, Any], actor_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        contract = self.run_contract_tests(plugin_id)
        if contract["status"] != "passed":
            run = self._plugin_run(tenant_id, case["id"], actor_id, plugin_id, "failed", {"contract": contract})
            self.store.insert("plugin_runs", run)
            raise AppError("CONNECTOR_UNAVAILABLE", "数据源暂时不可用，可稍后重试或人工补录", 503, contract)
        records = self._records_for(plugin_id, subject, case)
        run = self._plugin_run(tenant_id, case["id"], actor_id, plugin_id, "success", {"records_count": len(records), "duration_ms": 15})
        self.store.insert("plugin_runs", run)
        return run, records

    def _plugin_run(self, tenant_id: str, case_id: str, actor_id: str, plugin_id: str, status: str, metrics: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": new_id("run"),
            "run_id": new_id("pluginrun"),
            "tenant_id": tenant_id,
            "case_id": case_id,
            "actor_id": actor_id,
            "plugin_id": plugin_id,
            "status": status,
            "started_at": now_iso(),
            "finished_at": now_iso(),
            "warnings": [],
            "metrics": metrics,
        }

    def _records_for(self, plugin_id: str, subject: dict[str, Any], case: dict[str, Any]) -> list[dict[str, Any]]:
        fetched_at = now_iso()
        base = {"subject_id": subject["id"], "fetched_at": fetched_at, "authorization_status": "authorized", "raw_payload_ref": "store://manual-or-authorized-demo"}
        if plugin_id == "manual_company_connector":
            return [{**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "授权工商数据", "source_url": "https://example.local/company", "record_type": "company", "record_time": fetched_at, "normalized_payload": {"company_name": subject["name"], "aliases": [f"{subject['name']}（曾用名）"], "shareholders": [{"name": f"{subject['name']}投资平台", "ratio": "35%"}], "registered_capital": "1000万元"}}]
        if plugin_id == "execution_public_connector":
            return [{**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "执行公开信息", "source_url": "https://example.local/execution", "record_type": "execution", "record_time": fetched_at, "normalized_payload": {"case_name": case["case_name"], "amount": case.get("amount"), "status": "新增执行信息待核验"}}]
        if plugin_id == "public_auction_connector":
            return [{**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "司法拍卖公开信息", "source_url": "https://example.local/auction", "record_type": "auction", "record_time": fetched_at, "normalized_payload": {"asset_name": f"{subject['name']}相关不动产拍卖线索", "starting_price": "待核验", "status": "新增拍卖公告"}}]
        if plugin_id == "ip_rights_connector":
            return [{**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "知识产权公开信息", "source_url": "https://example.local/ip", "record_type": "ip", "record_time": fetched_at, "normalized_payload": {"right_name": f"{subject['name']}商标/软件著作权线索", "estimated_value": "待评估", "status": "可进一步核验权属和质押状态"}}]
        if plugin_id == "bid_receivable_connector":
            return [
                {**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "招投标公开信息", "source_url": "https://example.local/bid", "record_type": "bid", "record_time": fetched_at, "normalized_payload": {"project_name": f"{subject['name']}中标项目", "contract_amount": "待核验", "status": "存在经营回款线索"}},
                {**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "应收账款人工补录", "source_url": "manual://receivable", "record_type": "receivable", "record_time": fetched_at, "authorization_status": "manual", "normalized_payload": {"debtor": "项目付款方待核验", "estimated_value": "待核验", "status": "可作为保全/协执线索"}},
            ]
        return []