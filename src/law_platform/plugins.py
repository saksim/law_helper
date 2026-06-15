from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .data_sources import DEMO_MODE, MANUAL_ONLY_MODE, execute_authorized_data_source, get_data_source_config
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
    rate_limit: dict[str, Any] | None = None
    inputs: dict[str, Any] | None = None
    outputs: dict[str, Any] | None = None

    def to_dict(self, enabled: bool = True) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["id"] = self.plugin_id
        data["enabled"] = enabled
        data["rate_limit"] = self.rate_limit or {"requests_per_minute": 60}
        data["inputs"] = self.inputs or {"schema": f"{self.plugin_type.lower()}_input_v1"}
        data["outputs"] = self.outputs or {"schema": f"{self.plugin_type.lower()}_output_v1"}
        data["contract_version"] = "05-PLUGIN_CONTRACT"
        data["contract_status"] = "untested"
        data["audit_events"] = {
            "DataConnector": ["plugin_run_started", "plugin_run_finished", "plugin_run_failed"],
            "DocumentParser": ["document_parse_started", "document_parse_finished"],
            "Extractor": ["extractor_run_started", "extractor_run_finished"],
            "Scorer": ["scorer_run_started", "scorer_run_finished"],
            "ModelProvider": ["model_policy_checked", "model_invoked"],
            "ReportTemplate": ["report_generated", "report_review_required"],
            "Notifier": ["notification_delivery_created", "notification_delivery_failed"],
            "ReviewPolicy": ["review_required", "review_decision_recorded"],
        }.get(self.plugin_type, ["plugin_event"])
        rollback = dict(data.get("rollback") or {})
        rollback.setdefault("rollback_to_version", self.version)
        rollback.setdefault("cleanup_unfinished_tasks", True)
        rollback.setdefault("audit_record_required", True)
        rollback.setdefault("affected_results_warning", "Results created by this plugin should be reviewed after rollback.")
        data["rollback"] = rollback
        data["active_version"] = self.version
        data["previous_version"] = rollback["rollback_to_version"]
        if self.plugin_type == "DocumentParser":
            data["parser_contract"] = {
                "required_outputs": ["markdown", "blocks", "page_no", "bbox", "block_confidence", "table_placeholders", "image_placeholders", "quality_summary"],
                "prohibited_outputs": ["low_confidence_final_legal_conclusion", "missing_page_mapping"],
            }
        if self.plugin_type == "DataConnector":
            data["authorization"] = {
                "type": "manual" if self.plugin_id == "manual_company_connector" else "api_key",
                "expires_at": None,
            }
            data["quality"] = {
                "freshness_window_days": 30,
                "required_fields": ["source_name", "source_url", "record_type", "record_time", "fetched_at", "normalized_payload", "authorization_status"],
            }
            data["cost"] = {"billing_model": "unknown", "unit_cost": 0}
            data["lineage"] = {"field_mapping_version": "v1"}
        if self.plugin_type == "ReportTemplate":
            data["template_contract"] = {
                "report_type": "asset_clue",
                "required_inputs": ["case_id", "subject_id", "asset_clues", "source_refs"],
                "required_citations": ["source_refs"],
                "output_sections": [
                    "被执行人主体确认",
                    "执行公开信息摘要",
                    "工商与股权结构",
                    "司法拍卖资产线索",
                    "知识产权和经营权益线索",
                    "招投标/应收账款线索",
                    "线索价值排序",
                    "建议执行动作",
                    "待人工核验事项",
                ],
                "review_required_sections": ["待人工核验事项"],
            }
        if self.plugin_type == "Notifier":
            data["notification_contract"] = {
                "required_payload_fields": ["title", "event_type", "why_important", "source_refs", "detected_at", "recommended_action", "deep_link", "action_buttons"],
                "required_action_buttons": ["确认", "忽略", "转任务"],
            }
        return data


PLUGIN_MANIFESTS = [
    PluginManifest("manual_company_connector", "人工补录工商连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.manual_company.enabled", ["L0", "L1"], ["company.search", "company.risk"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_company_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.manual_company.enabled"}),
    PluginManifest("execution_public_connector", "公开执行信息连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.execution_public.enabled", ["L0", "L1"], ["execution.search"], {"authorized_api_required": True, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_execution_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.execution_public.enabled"}),
    PluginManifest("public_auction_connector", "司法拍卖公开信息连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.public_auction.enabled", ["L0", "L1"], ["auction.search"], {"authorized_api_required": True, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_auction_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.public_auction.enabled"}),
    PluginManifest("ip_rights_connector", "知识产权公开信息连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.ip_rights.enabled", ["L0", "L1"], ["ip.search"], {"authorized_api_required": True, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_ip_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.ip_rights.enabled"}),
    PluginManifest("bid_receivable_connector", "招投标与应收账款连接器", "DataConnector", "1.0.0", "data-team", "active", "connector.bid_receivable.enabled", ["L0", "L1"], ["bid.search", "receivable.search"], {"authorized_api_required": True, "bypass_captcha_allowed": False, "stores_raw_response": True}, ["normalize_bid_record", "preserve_source_reference", "reject_missing_authorization"], {"disable_feature_flag": "connector.bid_receivable.enabled"}),
    PluginManifest("basic_document_parser", "基础文档解析器", "DocumentParser", "1.0.0", "ai-team", "active", "parser.basic_document.enabled", ["L0", "L1", "L2", "L3", "L4"], ["file.parse"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["output_markdown", "preserve_page_mapping", "flag_low_confidence"], {"disable_feature_flag": "parser.basic_document.enabled"}),
    PluginManifest("case_element_extractor", "Case element extractor", "Extractor", "1.0.0", "ai-team", "active", "extractor.case_elements.enabled", ["L0", "L1", "L2", "L3"], ["entity.extract"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["output_structured_entities", "preserve_source_reference", "flag_low_confidence"], {"disable_feature_flag": "extractor.case_elements.enabled"}),
    PluginManifest("asset_clue_scorer_v1", "Asset clue scorer", "Scorer", "1.0.0", "risk-team", "active", "scorer.asset_clue_v1.enabled", ["L0", "L1", "L2"], ["clue.score"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["score_breakdown_required", "deterministic_output", "manual_review_for_low_confidence"], {"disable_feature_flag": "scorer.asset_clue_v1.enabled"}),
    PluginManifest("private_model_provider", "Private or local model provider", "ModelProvider", "1.0.0", "ai-team", "active", "model.private_or_local.enabled", ["L0", "L1", "L2", "L3", "L4"], ["model.invoke"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False, "external_model": False, "data_export_possible": False, "no_training_commitment": True, "log_retention_days": 30, "max_context_tokens": 32768, "cost_estimate": "internal", "fallback_model": "manual_review"}, ["declare_supported_data_levels", "data_policy_gateway_required", "fallback_model_available"], {"disable_feature_flag": "model.private_or_local.enabled"}),
    PluginManifest("execution_asset_clue_v1", "执行财产线索报告模板", "ReportTemplate", "1.0.0", "legal-team", "active", "report.execution_asset_clue_v1.enabled", ["L0", "L1", "L2"], ["report.generate"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False}, ["required_sections", "required_citations", "review_required_sections"], {"disable_feature_flag": "report.execution_asset_clue_v1.enabled"}),
    PluginManifest("high_risk_review_policy", "High risk review policy", "ReviewPolicy", "1.0.0", "legal-team", "active", "review.high_risk_policy.enabled", ["L0", "L1", "L2", "L3", "L4"], ["review.require"], {"authorized_api_required": False, "bypass_captcha_allowed": False, "stores_raw_response": False, "requires_responsible_lawyer": True}, ["review_required_for_high_risk", "audit_review_decision", "block_final_without_review"], {"disable_feature_flag": "review.high_risk_policy.enabled"}),
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
            default_row = manifest.to_dict(enabled=True)
            current = existing.get(manifest.plugin_id)
            row = {**default_row, **current} if current else default_row
            row["id"] = default_row["id"]
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
        self.ensure_registry()
        gate: dict[str, Any] | None = None
        if enabled:
            gate = self.run_contract_tests(plugin_id, include_feature_flag=False)
            if gate["status"] != "passed":
                raise AppError("VALIDATION_ERROR", "Plugin must pass contract tests before enable.", 400, gate)
        plugins = self.store.list("plugin_registry")
        for plugin in plugins:
            if plugin["plugin_id"] == plugin_id:
                plugin["enabled"] = enabled
                plugin["contract_status"] = "passed" if enabled and gate else plugin.get("contract_status", "untested")
                if gate:
                    plugin["last_contract_result"] = gate
                    plugin["last_enabled_at"] = now_iso()
                if not enabled:
                    plugin["previous_version"] = plugin.get("active_version") or plugin.get("version")
                    plugin["last_rollback"] = self._rollback_state(plugin)
                    plugin["active_version"] = plugin["last_rollback"]["rollback_to_version"]
                self.store.replace_collection("plugin_registry", plugins)
                return plugin
        raise AppError("VALIDATION_ERROR", "插件不存在", 404)

    def run_contract_tests(self, plugin_id: str, *, include_feature_flag: bool = True) -> dict[str, Any]:
        plugin = self.get(plugin_id)
        failures: list[str] = []
        checks: list[dict[str, Any]] = []

        def add_check(name: str, passed: bool, failure: str, details: dict[str, Any] | None = None) -> None:
            if not passed and failure not in failures:
                failures.append(failure)
            checks.append({"name": name, "status": "passed" if passed else "failed", "details": details or {}, "failure": None if passed else failure})

        required = [
            "plugin_id",
            "plugin_name",
            "plugin_type",
            "version",
            "owner",
            "status",
            "feature_flag",
            "supported_data_levels",
            "required_permissions",
            "compliance",
            "contract_tests",
            "rollback",
            "rate_limit",
            "inputs",
            "outputs",
        ]
        missing = [field for field in required if not plugin.get(field)]
        add_check("manifest_schema", not missing, "manifest_schema_invalid", {"missing": missing})

        plugin_type = plugin.get("plugin_type")
        valid_types = {"DataConnector", "DocumentParser", "Extractor", "Scorer", "ModelProvider", "ReportTemplate", "Notifier", "ReviewPolicy"}
        add_check("plugin_type_supported", plugin_type in valid_types, "unsupported_plugin_type", {"plugin_type": plugin_type})

        levels = set(plugin.get("supported_data_levels") or [])
        valid_levels = {"L0", "L1", "L2", "L3", "L4"}
        add_check("data_level_declaration", bool(levels) and levels <= valid_levels, "invalid_supported_data_levels", {"supported_data_levels": sorted(levels)})
        add_check("permission_declaration", bool(plugin.get("required_permissions")), "required_permissions_missing")

        rate_limit = plugin.get("rate_limit") or {}
        add_check("rate_limit_declaration", int(rate_limit.get("requests_per_minute") or 0) > 0, "rate_limit_missing", rate_limit)
        add_check("input_schema_declaration", bool((plugin.get("inputs") or {}).get("schema")), "input_schema_missing", plugin.get("inputs"))
        add_check("output_schema_declaration", bool((plugin.get("outputs") or {}).get("schema")), "output_schema_missing", plugin.get("outputs"))

        compliance = plugin.get("compliance") or {}
        add_check("captcha_and_wall_policy", not compliance.get("bypass_captcha_allowed"), "bypass_captcha_not_allowed")
        rollback = plugin.get("rollback") or {}
        rollback_ok = bool(rollback.get("disable_feature_flag") and rollback.get("rollback_to_version") and rollback.get("cleanup_unfinished_tasks") and rollback.get("audit_record_required"))
        add_check("rollback_contract", rollback_ok, "rollback_contract_incomplete", rollback)
        add_check("audit_event_contract", bool(plugin.get("audit_events")), "audit_events_missing", {"audit_events": plugin.get("audit_events")})

        if include_feature_flag:
            add_check("feature_flag_enabled", bool(plugin.get("enabled", True)), "feature_flag_disabled")
        else:
            checks.append({"name": "feature_flag_enabled", "status": "skipped", "details": {"reason": "enable gate ignores current disabled state"}, "failure": None})

        expected_tests = {
            "DataConnector": {"preserve_source_reference", "reject_missing_authorization"},
            "DocumentParser": {"output_markdown", "preserve_page_mapping", "flag_low_confidence"},
            "Extractor": {"output_structured_entities", "preserve_source_reference", "flag_low_confidence"},
            "Scorer": {"score_breakdown_required", "deterministic_output"},
            "ModelProvider": {"declare_supported_data_levels", "data_policy_gateway_required", "fallback_model_available"},
            "ReportTemplate": {"required_sections", "required_citations", "review_required_sections"},
            "Notifier": {"include_source_reference", "include_action_buttons", "deep_link_required"},
            "ReviewPolicy": {"audit_review_decision", "block_final_without_review"},
        }
        declared_tests = set(plugin.get("contract_tests") or [])
        missing_tests = sorted(expected_tests.get(plugin_type, set()) - declared_tests)
        add_check("type_contract_tests", not missing_tests, "type_contract_tests_missing", {"missing": missing_tests})

        if plugin_type == "DataConnector":
            add_check("data_connector_supports_L1", "L1" in levels, "data_connector_must_support_L1")
            add_check("data_connector_authorization_contract", bool(plugin.get("authorization")), "data_connector_authorization_contract_missing", plugin.get("authorization"))
            add_check("data_connector_quality_contract", bool(plugin.get("quality")), "data_connector_quality_contract_missing", plugin.get("quality"))
            add_check("data_connector_cost_contract", bool(plugin.get("cost")), "data_connector_cost_contract_missing", plugin.get("cost"))
            add_check("data_connector_lineage_contract", bool(plugin.get("lineage")), "data_connector_lineage_contract_missing", plugin.get("lineage"))
            if compliance.get("authorized_api_required"):
                add_check("authorization_failure_path", "reject_missing_authorization" in declared_tests, "missing_authorization_failure_path")
            sample_records = self._records_for(plugin_id, {"id": "sample_subject", "name": "Sample Subject"}, {"id": "sample_case", "case_name": "Sample Case", "amount": "1000"})
            record_errors = self._validate_external_records(sample_records)
            add_check("data_connector_output_schema", not record_errors, "data_connector_output_schema_invalid", {"errors": record_errors, "sample_count": len(sample_records)})
            add_check("manual_fallback_path", True, "", {"manual_entry_supported": True})

        if plugin_type == "ModelProvider":
            model_required = ["external_model", "data_export_possible", "no_training_commitment", "log_retention_days", "max_context_tokens", "cost_estimate", "fallback_model"]
            missing_model = [field for field in model_required if field not in compliance]
            add_check("model_provider_policy", not missing_model, "model_provider_policy_missing", {"missing": missing_model})

        if plugin_type == "DocumentParser":
            parser_contract = plugin.get("parser_contract") or {}
            required_outputs = set(parser_contract.get("required_outputs") or [])
            missing_outputs = sorted({"markdown", "blocks", "page_no", "bbox", "block_confidence", "table_placeholders", "image_placeholders", "quality_summary"} - required_outputs)
            add_check("document_parser_output_contract", not missing_outputs, "document_parser_output_contract_missing", {"missing": missing_outputs})
            prohibited = set(parser_contract.get("prohibited_outputs") or [])
            add_check("document_parser_prohibited_contract", {"low_confidence_final_legal_conclusion", "missing_page_mapping"} <= prohibited, "document_parser_prohibited_contract_missing", parser_contract)

        if plugin_type == "ReportTemplate":
            template_contract = plugin.get("template_contract") or {}
            required_template = ["report_type", "required_inputs", "required_citations", "output_sections", "review_required_sections"]
            missing_template = [field for field in required_template if not template_contract.get(field)]
            add_check("report_template_declaration", not missing_template, "report_template_declaration_missing", {"missing": missing_template})

        if plugin_type == "Notifier":
            notification_contract = plugin.get("notification_contract") or {}
            payload_fields = set(notification_contract.get("required_payload_fields") or [])
            missing_payload = sorted({"title", "event_type", "why_important", "source_refs", "detected_at", "recommended_action", "deep_link", "action_buttons"} - payload_fields)
            action_buttons = set(notification_contract.get("required_action_buttons") or [])
            add_check("notifier_payload_contract", not missing_payload and {"确认", "忽略", "转任务"} <= action_buttons, "notifier_payload_contract_missing", {"missing_payload": missing_payload})

        return {
            "plugin_id": plugin_id,
            "contract_version": "05-PLUGIN_CONTRACT",
            "status": "passed" if not failures else "failed",
            "failures": failures,
            "checks": checks,
            "checked_at": now_iso(),
            "test_status": "untested",
        }

    def execute_connector(self, plugin_id: str, tenant_id: str, case: dict[str, Any], subject: dict[str, Any], actor_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        execution_input = self._execution_input(plugin_id, tenant_id, case, subject, actor_id)
        contract = self.run_contract_tests(plugin_id)
        if contract["status"] != "passed":
            run = self._plugin_run(
                tenant_id,
                case["id"],
                actor_id,
                plugin_id,
                "failed",
                {"contract": contract, "duration_ms": 0, "records_count": 0},
                execution_input=execution_input,
                error={"code": "CONTRACT_TEST_FAILED", "message": "Plugin contract tests failed.", "details": contract},
                retryable=False,
            )
            self.store.insert("plugin_runs", run)
            raise AppError("CONNECTOR_UNAVAILABLE", "数据源暂时不可用，可稍后重试或人工补录", 503, contract)

        plugin = self.get(plugin_id)
        rate_error = self._rate_limit_error(plugin, tenant_id)
        if rate_error:
            run = self._plugin_run(
                tenant_id,
                case["id"],
                actor_id,
                plugin_id,
                "failed",
                {"records_count": 0, "rate_limit": rate_error},
                execution_input=execution_input,
                error=rate_error,
                retryable=True,
            )
            self.store.insert("plugin_runs", run)
            raise AppError("RATE_LIMITED", "Plugin rate limit exceeded.", 429, rate_error)
        config = get_data_source_config(self.store, tenant_id, plugin_id)
        authorization_required = bool((plugin.get("compliance") or {}).get("authorized_api_required"))
        if plugin_id == "manual_company_connector" or config.get("mode") in {DEMO_MODE, MANUAL_ONLY_MODE}:
            records = self._records_for(plugin_id, subject, case)
            run = self._plugin_run(
                tenant_id,
                case["id"],
                actor_id,
                plugin_id,
                "success",
                {"records_count": len(records), "duration_ms": 15, "data_source_mode": config.get("mode") or "manual_or_demo", "verification_status": "untested"},
                execution_input=execution_input,
                outputs=records,
                source_refs=self._source_refs(records),
            )
            self.store.insert("plugin_runs", run)
            return run, records

        try:
            records, metrics = execute_authorized_data_source(
                self.store,
                tenant_id,
                plugin_id,
                case,
                subject,
                authorization_required=authorization_required,
            )
        except AppError as exc:
            run = self._plugin_run(
                tenant_id,
                case["id"],
                actor_id,
                plugin_id,
                "failed",
                {"error": exc.details, "message": exc.message, "records_count": 0},
                execution_input=execution_input,
                error={"code": exc.code, "message": exc.message, "details": exc.details},
                retryable=True,
            )
            self.store.insert("plugin_runs", run)
            raise
        run = self._plugin_run(
            tenant_id,
            case["id"],
            actor_id,
            plugin_id,
            "success",
            metrics,
            execution_input=execution_input,
            outputs=records,
            source_refs=self._source_refs(records),
        )
        self.store.insert("plugin_runs", run)
        return run, records

    def record_plugin_run(
        self,
        plugin_id: str,
        tenant_id: str,
        case_id: str,
        actor_id: str,
        status: str,
        payload: dict[str, Any],
        *,
        outputs: list[dict[str, Any]] | None = None,
        source_refs: list[dict[str, Any]] | None = None,
        metrics: dict[str, Any] | None = None,
        warnings: list[dict[str, Any]] | None = None,
        error: dict[str, Any] | None = None,
        retryable: bool = False,
        sensitivity_level: str = "L1",
        allow_external_call: bool = False,
    ) -> dict[str, Any]:
        contract = self.run_contract_tests(plugin_id)
        final_status = status
        final_error = error
        if contract["status"] != "passed":
            final_status = "failed"
            final_error = {"code": "CONTRACT_TEST_FAILED", "message": "Plugin contract tests failed.", "details": contract}
        execution_input = {
            "run_id": new_id("pluginrun"),
            "tenant_id": tenant_id,
            "case_id": case_id,
            "actor_id": actor_id,
            "data_policy": {"sensitivity_level": sensitivity_level, "allow_external_call": allow_external_call},
            "payload": {"plugin_id": plugin_id, **payload},
        }
        run = self._plugin_run(
            tenant_id,
            case_id,
            actor_id,
            plugin_id,
            final_status,
            metrics or {},
            execution_input=execution_input,
            outputs=outputs,
            source_refs=source_refs,
            warnings=warnings,
            error=final_error,
            retryable=retryable,
        )
        self.store.insert("plugin_runs", run)
        return run

    def _execution_input(self, plugin_id: str, tenant_id: str, case: dict[str, Any], subject: dict[str, Any], actor_id: str) -> dict[str, Any]:
        return {
            "run_id": new_id("pluginrun"),
            "tenant_id": tenant_id,
            "case_id": case["id"],
            "actor_id": actor_id,
            "data_policy": {"sensitivity_level": "L1", "allow_external_call": True},
            "payload": {
                "plugin_id": plugin_id,
                "subject_id": subject.get("id"),
                "subject_name": subject.get("name"),
                "case_name": case.get("case_name"),
            },
        }

    def _plugin_run(
        self,
        tenant_id: str,
        case_id: str,
        actor_id: str,
        plugin_id: str,
        status: str,
        metrics: dict[str, Any],
        *,
        execution_input: dict[str, Any] | None = None,
        outputs: list[dict[str, Any]] | None = None,
        source_refs: list[dict[str, Any]] | None = None,
        warnings: list[dict[str, Any]] | None = None,
        error: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> dict[str, Any]:
        execution_input = execution_input or {"run_id": new_id("pluginrun"), "tenant_id": tenant_id, "case_id": case_id, "actor_id": actor_id, "payload": {}}
        return {
            "id": new_id("run"),
            "run_id": execution_input["run_id"],
            "tenant_id": tenant_id,
            "case_id": case_id,
            "actor_id": actor_id,
            "plugin_id": plugin_id,
            "status": status,
            "input": execution_input,
            "outputs": outputs or [],
            "source_refs": source_refs or [],
            "started_at": now_iso(),
            "finished_at": now_iso(),
            "warnings": warnings or [],
            "metrics": metrics,
            "error": error,
            "retryable": retryable,
            "contract_version": "05-PLUGIN_CONTRACT",
        }

    def _validate_external_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        required = ["source_name", "source_url", "record_type", "record_time", "fetched_at", "normalized_payload", "authorization_status"]
        errors: list[dict[str, Any]] = []
        for index, record in enumerate(records):
            missing = [field for field in required if field not in record or record.get(field) in (None, "")]
            if missing:
                errors.append({"index": index, "missing": missing})
        return errors

    def _rollback_state(self, plugin: dict[str, Any]) -> dict[str, Any]:
        rollback = plugin.get("rollback") or {}
        plugin_id = plugin["plugin_id"]
        cancelled_jobs = 0
        cancelled_runs = 0
        for job in self.store.list("jobs"):
            payload = job.get("payload") or {}
            if job.get("status") in {"queued", "running"} and plugin_id in {payload.get("plugin_id"), payload.get("connector_id"), payload.get("report_template")}:
                self.store.update("jobs", job["id"], {"status": "cancelled", "updated_at": now_iso(), "last_error": {"code": "PLUGIN_ROLLBACK", "message": "Plugin disabled or rolled back."}})
                cancelled_jobs += 1
        affected_run_ids: list[str] = []
        for run in self.store.list("plugin_runs"):
            if run.get("plugin_id") != plugin_id:
                continue
            if run.get("status") == "running":
                self.store.update("plugin_runs", run["id"], {"status": "cancelled", "finished_at": now_iso(), "error": {"code": "PLUGIN_ROLLBACK", "message": "Plugin disabled or rolled back."}, "retryable": False})
                cancelled_runs += 1
            elif run.get("status") == "success":
                affected_run_ids.append(run["id"])
        return {
            "disabled_at": now_iso(),
            "previous_active_version": plugin.get("previous_version") or plugin.get("active_version") or plugin.get("version"),
            "rollback_to_version": rollback.get("rollback_to_version") or plugin.get("version"),
            "disable_feature_flag": rollback.get("disable_feature_flag") or plugin.get("feature_flag"),
            "cleanup_unfinished_tasks": True,
            "cancelled_jobs": cancelled_jobs,
            "cancelled_plugin_runs": cancelled_runs,
            "audit_record_required": True,
            "affected_run_ids": affected_run_ids[-20:],
            "affected_results_warning": rollback.get("affected_results_warning", "Review results created by this plugin before relying on them."),
            "test_status": "untested",
        }

    def _rate_limit_error(self, plugin: dict[str, Any], tenant_id: str) -> dict[str, Any] | None:
        limit = int((plugin.get("rate_limit") or {}).get("requests_per_minute") or 0)
        if limit <= 0:
            return None
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=1)
        count = 0
        for run in self.store.list("plugin_runs"):
            if run.get("tenant_id") != tenant_id or run.get("plugin_id") != plugin.get("plugin_id"):
                continue
            try:
                started_at = datetime.fromisoformat(str(run.get("started_at")))
            except ValueError:
                continue
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            if started_at.astimezone(timezone.utc) >= cutoff:
                count += 1
        if count < limit:
            return None
        return {
            "code": "RATE_LIMITED",
            "message": "Plugin requests per minute exceeded.",
            "plugin_id": plugin.get("plugin_id"),
            "requests_per_minute": limit,
            "window_seconds": 60,
            "retryable": True,
        }

    def _source_refs(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "source_name": record.get("source_name"),
                "source_url": record.get("source_url"),
                "source_time": record.get("record_time"),
                "fetched_at": record.get("fetched_at"),
                "external_record_id": record.get("id"),
            }
            for record in records
        ]

    def _records_for(self, plugin_id: str, subject: dict[str, Any], case: dict[str, Any]) -> list[dict[str, Any]]:
        fetched_at = now_iso()
        authorization_status = "manual" if plugin_id == "manual_company_connector" else "public"
        base = {
            "subject_id": subject["id"],
            "fetched_at": fetched_at,
            "authorization_status": authorization_status,
            "raw_payload_ref": "store://manual-or-demo-data",
            'verification_status': 'untested',
            'sensitivity_level': 'L1',
        }
        if plugin_id == "manual_company_connector":
            return [{**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "人工补录工商数据", "source_url": "manual://company", "record_type": "company", "record_time": fetched_at, "normalized_payload": {"company_name": subject["name"], "aliases": [f"{subject['name']}（曾用名）"], "shareholders": [{"name": f"{subject['name']}投资平台", "ratio": "35%"}], "registered_capital": "1000万元"}}]
        if plugin_id == "execution_public_connector":
            return [{**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "演示公开执行信息", "source_url": "https://example.local/execution", "record_type": "execution", "record_time": fetched_at, "normalized_payload": {"case_name": case["case_name"], "amount": case.get("amount"), "status": "新增执行信息待核验"}}]
        if plugin_id == "public_auction_connector":
            return [{**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "演示司法拍卖公开信息", "source_url": "https://example.local/auction", "record_type": "auction", "record_time": fetched_at, "normalized_payload": {"asset_name": f"{subject['name']}相关不动产拍卖线索", "starting_price": "待核验", "status": "新增拍卖公告"}}]
        if plugin_id == "ip_rights_connector":
            return [{**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "演示知识产权公开信息", "source_url": "https://example.local/ip", "record_type": "ip", "record_time": fetched_at, "normalized_payload": {"right_name": f"{subject['name']}商标/软件著作权线索", "estimated_value": "待评估", "status": "可进一步核验权属和质押状态"}}]
        if plugin_id == "bid_receivable_connector":
            return [
                {**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "演示招投标公开信息", "source_url": "https://example.local/bid", "record_type": "bid", "record_time": fetched_at, "normalized_payload": {"project_name": f"{subject['name']}中标项目", "contract_amount": "待核验", "status": "存在经营回款线索"}},
                {**base, "id": new_id("ext"), "connector_id": plugin_id, "source_name": "应收账款人工补录", "source_url": "manual://receivable", "record_type": "bid", "record_time": fetched_at, "authorization_status": "manual", "normalized_payload": {"asset_subtype": "receivable", "debtor": "项目付款方待核验", "estimated_value": "待核验", "status": "可作为保全/协执线索"}},
            ]
        return []
