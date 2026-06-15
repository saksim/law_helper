from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel

from .errors import AppError
from .models import new_id, now_iso
from .p0_features import install_p0_features
from .security import RequestContext
from .services import LawPlatform
from .store import Store
from .ux_features import install_ux_features
from .ux_views_v2 import desktop_html, mobile_clue_html, mobile_notification_html, mobile_upload_html


class CaseCreate(BaseModel):
    case_name: str
    case_type: str = "execution"
    cause_of_action: str | None = None
    amount: float | None = None
    responsible_lawyer_id: str = "user_lawyer"
    risk_level: str = "medium"
    stage: str = "execution"


class CasePatch(BaseModel):
    case_name: str | None = None
    cause_of_action: str | None = None
    stage: str | None = None
    risk_level: str | None = None
    status: str | None = None


class BlockReview(BaseModel):
    review_status: str
    corrected_text: str | None = None
    reason: str | None = None


class SubjectResolve(BaseModel):
    name: str
    unified_social_credit_code: str | None = None
    case_id: str | None = None



class CaseSubjectAttach(BaseModel):
    subject_id: str | None = None
    name: str | None = None
    unified_social_credit_code: str | None = None
    aliases: list[str] | None = None


class ReportCreate(BaseModel):
    subject_id: str
    connector_ids: list[str] | None = None
    report_template: str = "execution_asset_clue_v1"


class ClueReview(BaseModel):
    review_status: str
    comment: str | None = None
    next_action: str | None = None
    corrected_fields: dict[str, Any] | None = None
    usefulness: str | None = None


class MonitorTargetCreate(BaseModel):
    case_id: str
    subject_id: str
    event_types: list[str] | None = None
    frequency: str = "daily"
    notify_channels: list[str] | None = None


class ReportReview(BaseModel):
    review_status: str = "confirmed"
    comment: str | None = None


class MonitorCheck(BaseModel):
    snapshot: dict[str, Any] | None = None
    title: str | None = None


class ManualExternalRecordCreate(BaseModel):
    subject_id: str | None = None
    connector_id: str = "manual_external_record"
    source_name: str = "Manual external record"
    source_url: str | None = None
    record_type: str
    record_time: str | None = None
    normalized_payload: dict[str, Any]
    alert_id: str | None = None


class ConnectorAlertResolve(BaseModel):
    resolution: str = "resolved"
    manual_external_record_id: str | None = None


class RunDueJobsRequest(BaseModel):
    limit: int = 20


class NotificationChannelConfigUpdate(BaseModel):
    enabled: bool = False
    webhook_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    from_email: str | None = None
    to_emails: list[str] | None = None
    verification_token: str | None = None
    signing_secret: str | None = None
    send_timeout_seconds: int | None = None


class NotificationCallbackValidate(BaseModel):
    payload: dict[str, Any]


class DataSourceConfigUpdate(BaseModel):
    enabled: bool | None = None
    mode: str | None = None
    base_url: str | None = None
    path: str | None = None
    method: str | None = None
    auth_header: str | None = None
    auth_prefix: str | None = None
    api_key: str | None = None
    headers: dict[str, Any] | None = None
    query_params: dict[str, Any] | None = None
    timeout_seconds: int | None = None
    records_path: str | None = None
    source_name: str | None = None
    default_record_type: str | None = None


class QAAcceptanceRunCreate(BaseModel):
    sample_counts: dict[str, Any] | None = None
    test_results: dict[str, Any] | None = None
    usability_results: dict[str, Any] | None = None
    performance_results: dict[str, Any] | None = None
    evidence_refs: dict[str, Any] | None = None
    defects: list[dict[str, Any]] | None = None
    release_risk_conclusion: str | None = None


class ImplementationCheckpointCreate(BaseModel):
    phase: str | None = None
    sprint: str | None = None
    milestone: str | None = None
    dependency_statuses: dict[str, Any] | None = None
    risk_statuses: dict[str, Any] | None = None
    evidence_refs: dict[str, Any] | None = None
    notes: str | None = None


class RunbookCheckCreate(BaseModel):
    check_key: str
    status: str = "passed"
    check_type: str = "pre_deployment"
    evidence_refs: dict[str, Any] | None = None
    notes: str | None = None


class RunbookIncidentCreate(BaseModel):
    incident_type: str
    summary: str
    severity: str = "P1"
    status: str = "open"
    affected_component: str | None = None
    detection_source: str | None = None
    diagnosis: list[str] | None = None
    actions: list[str] | None = None
    rollback_strategy: str | None = None
    evidence_refs: dict[str, Any] | None = None


class RunbookIncidentResolve(BaseModel):
    status: str = "resolved"
    resolution: str | None = None
    actions: list[str] | None = None
    evidence_refs: dict[str, Any] | None = None


def model_data(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(exclude_none=True) if hasattr(model, "model_dump") else model.dict(exclude_none=True)



CLIENT_TYPES = {'web', 'mobile_h5', 'mini_program', 'bot', 'admin'}


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def paginate_rows(rows: list[Any], page: int, page_size: int) -> tuple[list[Any], dict[str, Any]]:
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return rows[start:end], {
        'page': page,
        'page_size': page_size,
        'total': total,
        'has_next': end < total,
        'test_status': 'untested',
    }


def create_app(store: Store | None = None) -> FastAPI:
    store = store or Store(Path(".runtime/law_platform_store.json"))
    install_p0_features()
    install_ux_features()
    platform = LawPlatform(store)
    app = FastAPI(title="Execution Case Asset Clue Workspace", version="0.1.0")
    app.state.platform = platform

    def ctx(request: Request) -> RequestContext:
        auth = request.headers.get('Authorization', '')
        if not auth.lower().startswith('bearer '):
            raise AppError('PERMISSION_DENIED', 'Authorization Bearer token is required', 401, {'test_status': 'untested'})
        actor_id = auth.split(' ', 1)[1].strip()
        if not actor_id:
            raise AppError('PERMISSION_DENIED', 'Authorization Bearer token is required', 401, {'test_status': 'untested'})
        tenant_id = request.headers.get('X-Tenant-Id')
        if not tenant_id:
            raise AppError('VALIDATION_ERROR', 'X-Tenant-Id is required', 400, {'test_status': 'untested'})
        client_type = request.headers.get('X-Client-Type', 'web')
        if client_type not in CLIENT_TYPES:
            raise AppError('VALIDATION_ERROR', 'Unsupported X-Client-Type', 400, {'allowed': sorted(CLIENT_TYPES), 'test_status': 'untested'})
        request_id = request.headers.get('X-Request-Id') or new_id('req')
        page = _bounded_int(request.query_params.get('page'), 1, 1, 10000)
        page_size = _bounded_int(request.query_params.get('page_size'), 50, 1, 100)
        return RequestContext(
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            client_type=client_type,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get('User-Agent'),
            page=page,
            page_size=page_size,
        )

    def ok(context: RequestContext, data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        response_meta = {'server_time': now_iso(), **(meta or {})}
        if isinstance(data, list):
            data, pagination = paginate_rows(data, context.page, context.page_size)
            response_meta['pagination'] = pagination
        return {'request_id': context.request_id, 'data': data, 'meta': response_meta}

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = request.headers.get('X-Request-Id') or new_id('req')
        return JSONResponse(
            status_code=exc.status_code,
            content={"request_id": request_id, "error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )


    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = request.headers.get('X-Request-Id') or new_id('req')
        return JSONResponse(
            status_code=400,
            content={'request_id': request_id, 'error': {'code': 'VALIDATION_ERROR', 'message': 'Request validation failed', 'details': {'errors': exc.errors(), 'test_status': 'untested'}}},
        )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return desktop_html()

    @app.get("/mobile/notifications/{notification_id}", response_class=HTMLResponse)
    def mobile_notification_view(notification_id: str) -> str:
        return mobile_notification_html(notification_id)

    @app.get("/mobile/clues/{clue_id}", response_class=HTMLResponse)
    def mobile_clue_view(clue_id: str) -> str:
        return mobile_clue_html(clue_id)

    @app.get("/mobile/cases/{case_id}/upload", response_class=HTMLResponse)
    def mobile_upload_view(case_id: str) -> str:
        return mobile_upload_html(case_id)

    @app.get("/healthz")
    def healthz(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, {"status": "ok"})

    @app.post("/api/cases")
    def create_case(payload: CaseCreate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.create_case(context, model_data(payload)))

    @app.get("/api/cases")
    def list_cases(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.list_cases(context))

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.get_case(context, case_id))

    @app.patch("/api/cases/{case_id}")
    def update_case(case_id: str, payload: CasePatch, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.update_case(context, case_id, model_data(payload)))

    @app.post("/api/cases/{case_id}/files")
    async def upload_file(
        case_id: str,
        file: UploadFile = File(...),
        file_type: str = Form("other"),
        sensitivity_level: str = Form("L2"),
        context: RequestContext = Depends(ctx),
    ) -> dict[str, Any]:
        content = await file.read()
        return ok(context, platform.upload_file(context, case_id, file.filename or "uploaded_file", content, file_type, sensitivity_level, context.client_type))

    @app.get("/api/files/{file_id}/parse-result")
    def parse_result(file_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.parse_result(context, file_id))

    @app.get("/api/files/{file_id}/markdown", response_class=PlainTextResponse)
    def file_markdown(file_id: str, context: RequestContext = Depends(ctx)) -> str:
        file = platform.store.get("case_files", file_id)
        if not file:
            raise AppError("VALIDATION_ERROR", "文件不存在", 404)
        platform.security.require_case_access(context, file["case_id"])
        platform.security.require_sensitive_access(context, file.get("sensitivity_level", "L4"))
        platform.security.audit(context, "material_markdown_viewed", "case_file", file_id, {"case_id": file["case_id"], "sensitivity_level": file.get("sensitivity_level"), "client_type": context.client_type})
        return platform.security.protect_material_text(context, file.get("markdown", ""), file.get("sensitivity_level"))

    @app.post("/api/document-blocks/{block_id}/review")
    def review_block(block_id: str, payload: BlockReview, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.review_block(context, block_id, model_data(payload)))

    @app.post("/api/subjects/resolve")
    def resolve_subject(payload: SubjectResolve, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.resolve_subject(context, model_data(payload)))

    @app.get("/api/subjects/{subject_id}")
    def get_subject(subject_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.get_subject(context, subject_id))


    @app.post('/api/cases/{case_id}/subjects')
    def attach_subject(case_id: str, payload: CaseSubjectAttach, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.attach_subject_to_case(context, case_id, model_data(payload)))
    @app.post("/api/cases/{case_id}/asset-clue-reports")
    def create_report(case_id: str, payload: ReportCreate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.generate_asset_clue_report(context, case_id, model_data(payload)))

    @app.get("/api/reports/{report_id}")
    def get_report(report_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.get_report(context, report_id))

    @app.post("/api/asset-clues/{clue_id}/review")
    def review_clue(clue_id: str, payload: ClueReview, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.review_clue(context, clue_id, model_data(payload)))

    @app.post("/api/monitor-targets")
    def create_monitor_target(payload: MonitorTargetCreate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.create_monitor_target(context, model_data(payload)))

    @app.get("/api/monitor-targets")
    def list_monitor_targets(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.list_monitor_targets(context))

    @app.get("/api/monitor-events")
    def list_monitor_events(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.list_monitor_events(context))

    @app.post("/api/monitor-events/{event_id}/ack")
    def ack_event(event_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.handle_monitor_event(context, event_id, "ack"))

    @app.post("/api/monitor-events/{event_id}/ignore")
    def ignore_event(event_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.handle_monitor_event(context, event_id, "ignore"))

    @app.post("/api/monitor-events/{event_id}/convert-to-task")
    def convert_event(event_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.handle_monitor_event(context, event_id, "convert-to-task"))

    @app.get("/api/plugins")
    def list_plugins(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        platform.security.require_role(context, {"owner", "admin"})
        return ok(context, platform.plugins.list_plugins())

    @app.post("/api/plugins/{plugin_id}/enable")
    def enable_plugin(plugin_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        platform.security.require_role(context, {"owner", "admin"})
        plugin = platform.plugins.enable_by_plugin_id(plugin_id, True)
        platform.security.audit(context, "plugin_enabled", "plugin", plugin_id)
        return ok(context, plugin)

    @app.post("/api/plugins/{plugin_id}/disable")
    def disable_plugin(plugin_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        platform.security.require_role(context, {"owner", "admin"})
        plugin = platform.plugins.enable_by_plugin_id(plugin_id, False)
        platform.security.audit(context, "plugin_disabled", "plugin", plugin_id)
        return ok(context, plugin)

    @app.post("/api/plugins/{plugin_id}/contract-tests")
    def plugin_contract_tests(plugin_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        platform.security.require_role(context, {"owner", "admin"})
        result = platform.plugins.run_contract_tests(plugin_id)
        platform.security.audit(context, "plugin_contract_tested", "plugin", plugin_id, result)
        return ok(context, result)

    @app.get("/api/plugin-runs")
    def plugin_runs(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        platform.security.require_role(context, {"owner", "admin", "auditor"})
        return ok(context, platform.store.list("plugin_runs"))

    @app.get("/api/audit-logs")
    def audit_logs(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.audit_logs(context))

    @app.get("/api/review-records")
    def review_records(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.review_records(context))

    @app.get("/api/model-invocations")
    def model_invocations(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.model_invocations(context))

    @app.get("/api/qa/acceptance-plan")
    def qa_acceptance_plan(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.qa_acceptance_plan(context))

    @app.post("/api/qa/acceptance-runs")
    def create_qa_acceptance_run(payload: QAAcceptanceRunCreate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.create_qa_acceptance_run(context, model_data(payload)))

    @app.get("/api/qa/acceptance-runs")
    def qa_acceptance_runs(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.qa_acceptance_runs(context))

    @app.get("/api/implementation-plan")
    def implementation_plan(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.implementation_plan(context))

    @app.get("/api/implementation-status")
    def implementation_status(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.implementation_status(context))

    @app.post("/api/implementation-checkpoints")
    def create_implementation_checkpoint(payload: ImplementationCheckpointCreate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.create_implementation_checkpoint(context, model_data(payload)))

    @app.get("/api/implementation-checkpoints")
    def implementation_checkpoints(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.implementation_checkpoints(context))

    @app.get("/api/runbook")
    def runbook(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.runbook(context))

    @app.get("/api/runbook/status")
    def runbook_status(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.runbook_status(context))

    @app.post("/api/runbook/checks")
    def create_runbook_check(payload: RunbookCheckCreate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.create_runbook_check(context, model_data(payload)))

    @app.get("/api/runbook/checks")
    def runbook_checks(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.runbook_checks(context))

    @app.post("/api/runbook/incidents")
    def create_runbook_incident(payload: RunbookIncidentCreate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.create_runbook_incident(context, model_data(payload)))

    @app.get("/api/runbook/incidents")
    def runbook_incidents(status: str | None = None, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.runbook_incidents(context, status))

    @app.post("/api/runbook/incidents/{incident_id}/resolve")
    def resolve_runbook_incident(incident_id: str, payload: RunbookIncidentResolve, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.resolve_runbook_incident(context, incident_id, model_data(payload)))

    @app.get('/api/data-dictionary')
    def data_dictionary(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.data_dictionary(context))

    @app.get('/api/data-dictionary/validate')
    def data_dictionary_validate(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.data_dictionary_status(context))

    @app.get('/api/lineage/{object_type}/{object_id}')
    def data_lineage(object_type: str, object_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.data_lineage(context, object_type, object_id))

    @app.get("/bff/cases/{case_id}/overview")
    def case_overview(case_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.case_overview(context, case_id))

    @app.get("/bff/home")
    def home_dashboard(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.home_dashboard(context))

    @app.get("/bff/cases/{case_id}/workspace")
    def case_workspace(case_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.case_workspace(context, case_id))

    @app.get("/bff/mobile/notifications/{notification_id}")
    def mobile_notification(notification_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.mobile_notification(context, notification_id))

    @app.get("/bff/mobile/clues/{clue_id}")
    def mobile_clue(clue_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.mobile_clue(context, clue_id))

    @app.get("/bff/mobile/cases/{case_id}/upload-context")
    def mobile_upload_context(case_id: str, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.mobile_case_upload_context(context, case_id))

    @app.post("/api/reports/{report_id}/review")
    def review_report(report_id: str, payload: ReportReview, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.review_report(context, report_id, model_data(payload)))

    @app.get("/api/reports/{report_id}/export")
    def export_report(report_id: str, format: str = "md", context: RequestContext = Depends(ctx)) -> Response:
        result = platform.export_report(context, report_id, format)
        extension = result["filename"].rsplit(".", 1)[-1]
        return Response(content=result["body"], media_type=result["media_type"], headers={"Content-Disposition": f"attachment; filename=asset-clue-report.{extension}"})

    @app.post("/api/monitor-targets/{target_id}/run-check")
    def run_monitor_check(target_id: str, payload: MonitorCheck, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.run_monitor_check(context, target_id, model_data(payload)))

    @app.post("/api/cases/{case_id}/external-records/manual")
    def create_manual_external_record(case_id: str, payload: ManualExternalRecordCreate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.create_manual_external_record(context, case_id, model_data(payload)))

    @app.get("/api/connector-alerts")
    def list_connector_alerts(status: str | None = None, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.list_connector_alerts(context, status))

    @app.post("/api/connector-alerts/{alert_id}/resolve")
    def resolve_connector_alert(alert_id: str, payload: ConnectorAlertResolve, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.resolve_connector_alert(context, alert_id, model_data(payload)))

    @app.get("/api/jobs")
    def list_jobs(status: str | None = None, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.list_jobs(context, status))

    @app.post("/api/jobs/schedule-monitor-checks")
    def schedule_monitor_jobs(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.schedule_monitor_jobs(context))

    @app.post("/api/jobs/run-due")
    def run_due_jobs(payload: RunDueJobsRequest | None = None, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        limit = payload.limit if payload else 20
        return ok(context, platform.run_due_jobs(context, limit))

    @app.get("/api/notification-channels")
    def list_notification_channels(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.list_notification_channels(context))

    @app.put("/api/notification-channels/{channel}")
    def configure_notification_channel(channel: str, payload: NotificationChannelConfigUpdate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.configure_notification_channel(context, channel, model_data(payload)))

    @app.post("/api/notification-channels/{channel}/callback/validate")
    def validate_notification_callback(channel: str, payload: NotificationCallbackValidate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.validate_notification_callback(context, channel, payload.payload))

    @app.get("/api/data-source-configs")
    def list_data_source_configs_endpoint(context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.list_data_source_configs(context))

    @app.put("/api/data-source-configs/{connector_id}")
    def configure_data_source_endpoint(connector_id: str, payload: DataSourceConfigUpdate, context: RequestContext = Depends(ctx)) -> dict[str, Any]:
        return ok(context, platform.configure_data_source(context, connector_id, model_data(payload)))
    return app


DESKTOP_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>执行案件工作台</title>
<style>:root{--ink:#16211b;--muted:#617068;--line:#d9e1dc;--soft:#f6f8f6;--accent:#146c5c;--warn:#9a5b11;--info:#235f9b}*{box-sizing:border-box}body{margin:0;font-family:"Microsoft YaHei",system-ui,sans-serif;color:var(--ink);background:#fbfcfb}header{height:56px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:24px;padding:0 24px;background:white;position:sticky;top:0;z-index:2}header strong{font-size:18px}nav{display:flex;gap:12px;color:var(--muted);font-size:14px;flex-wrap:wrap}main{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:calc(100vh - 56px)}aside{border-right:1px solid var(--line);padding:18px;background:#f8faf8}section{padding:20px 24px 32px}h1{font-size:24px;margin:0 0 6px;letter-spacing:0}h2{font-size:16px;margin:0 0 12px}p{color:var(--muted)}button{border:1px solid var(--accent);background:var(--accent);color:white;min-height:36px;padding:0 12px;border-radius:6px;cursor:pointer}button.secondary{background:white;color:var(--accent)}input,select{width:100%;min-height:36px;border:1px solid var(--line);border-radius:6px;padding:6px 8px;background:white}label{display:grid;gap:6px;font-size:13px;color:var(--muted);margin-bottom:10px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.panel{border:1px solid var(--line);border-radius:8px;background:white;padding:14px;min-height:120px}.list{display:grid;gap:8px}.item{border:1px solid var(--line);border-radius:7px;background:white;padding:10px;cursor:pointer}.item.active{border-color:var(--accent);box-shadow:0 0 0 2px rgba(20,108,92,.12)}.meta{font-size:12px;color:var(--muted)}.status{display:inline-flex;align-items:center;min-height:22px;border-radius:999px;padding:0 8px;background:var(--soft);font-size:12px;color:var(--muted)}.status.high,.status.critical{background:#fff0e5;color:var(--warn)}.pending{background:#fff7dd;color:var(--warn)}pre{white-space:pre-wrap;word-break:break-word;font-size:13px;color:#25352d}@media(max-width:860px){main{grid-template-columns:1fr}aside{border-right:0;border-bottom:1px solid var(--line)}.grid{grid-template-columns:1fr}}</style></head>
<body><header><strong>执行案件工作台</strong><nav><span>首页</span><span>案件</span><span>材料</span><span>线索</span><span>监控</span><span>任务</span><span>报告</span><span>设置</span></nav></header><main><aside><h2>案件</h2><div id="cases" class="list"></div><hr/><label>案件名称<input id="caseName" value="A 公司执行案件"/></label><label>标的金额<input id="amount" type="number" value="1200000"/></label><button onclick="createCase()">新建案件</button></aside><section><h1 id="title">今日重点</h1><p id="subtitle">选择案件后查看线索、风险、来源和下一步动作。</p><div class="toolbar"><label style="width:220px">主体名称<input id="subjectName" value="某某科技有限公司"/></label><button onclick="resolveSubject()">识别主体</button><button onclick="generateReport()">生成线索报告</button><button class="secondary" onclick="createMonitor()">加入监控</button></div><div class="toolbar"><input id="fileInput" type="file"/><select id="sensitivity"><option>L2</option><option>L3</option><option>L4</option></select><button class="secondary" onclick="uploadFile()">上传材料</button></div><div class="grid"><div class="panel"><h2>今日重点</h2><div id="highlights" class="list"></div></div><div class="panel"><h2>待复核</h2><div id="reviews" class="list"></div></div><div class="panel"><h2>任务</h2><div id="tasks" class="list"></div></div></div><div style="height:14px"></div><div class="grid"><div class="panel"><h2>材料状态</h2><div id="materials" class="list"></div></div><div class="panel"><h2>最新报告</h2><pre id="report"></pre></div><div class="panel"><h2>监控事件</h2><div id="events" class="list"></div></div></div></section></main>
<script>const headers={"Authorization":"Bearer user_owner","X-Tenant-Id":"tenant_demo","X-Client-Type":"web","Content-Type":"application/json"};let selectedCase=null,selectedSubject=null,latestReport=null;async function api(path,options={}){const merged={...options,headers:{...headers,...(options.headers||{})}};const res=await fetch(path,merged);const body=await res.json();if(!res.ok)throw new Error(body.error?.message||res.statusText);return body.data}function item(html,cls="item"){return `<div class="${cls}">${html}</div>`}async function loadCases(){const rows=await api("/api/cases");cases.innerHTML=rows.map(c=>item(`<strong>${c.case_name}</strong><div class="meta">${c.stage} · ${c.risk_level}</div>`, `item ${selectedCase===c.id?'active':''}`)).join("");[...cases.children].forEach((el,i)=>el.onclick=()=>{selectedCase=rows[i].id;loadOverview()});if(!selectedCase&&rows[0]){selectedCase=rows[0].id;loadOverview()}}async function createCase(){const c=await api("/api/cases",{method:"POST",body:JSON.stringify({case_name:caseName.value,amount:Number(amount.value),cause_of_action:"买卖合同纠纷"})});selectedCase=c.id;await loadCases()}async function loadOverview(){if(!selectedCase)return;const data=await api(`/bff/cases/${selectedCase}/overview`);title.textContent=data.case.case_name;subtitle.textContent=`${data.case.stage} · ${data.case.risk_level}`;highlights.innerHTML=data.today_highlights.map(x=>item(`<span class="status ${x.importance}">${x.importance}</span> ${x.title}<div class="meta">${x.action||""}</div>`)).join("")||item("暂无新增重点");reviews.innerHTML=data.pending_reviews.map(x=>item(`${x.title}<div class="meta">${x.type}</div>`,"item pending")).join("")||item("暂无待复核");tasks.innerHTML=data.tasks.map(x=>item(`${x.title}<div class="meta">${x.status}</div>`)).join("")||item("暂无任务");materials.innerHTML=data.material_status.map(x=>item(`${x.name}<div class="meta">${x.parse_status}</div>`)).join("")||item("暂无材料");loadEvents()}async function uploadFile(){if(!selectedCase||!fileInput.files[0])return;const form=new FormData();form.append("file",fileInput.files[0]);form.append("file_type","judgment");form.append("sensitivity_level",sensitivity.value);await fetch(`/api/cases/${selectedCase}/files`,{method:"POST",headers:{"Authorization":"Bearer user_owner","X-Tenant-Id":"tenant_demo","X-Client-Type":"web"},body:form});loadOverview()}async function resolveSubject(){if(!selectedCase)return;const data=await api("/api/subjects/resolve",{method:"POST",body:JSON.stringify({case_id:selectedCase,name:subjectName.value})});selectedSubject=data.candidates[0].subject_id}async function generateReport(){if(!selectedSubject)await resolveSubject();const job=await api(`/api/cases/${selectedCase}/asset-clue-reports`,{method:"POST",body:JSON.stringify({subject_id:selectedSubject,connector_ids:["manual_company_connector","execution_public_connector","public_auction_connector"]})});latestReport=await api(`/api/reports/${job.report_id}`);report.textContent=latestReport.content_md;loadOverview()}async function createMonitor(){if(!selectedSubject)await resolveSubject();await api("/api/monitor-targets",{method:"POST",body:JSON.stringify({case_id:selectedCase,subject_id:selectedSubject,event_types:["new_auction"],notify_channels:["in_app"]})});loadOverview()}async function loadEvents(){const rows=await api("/api/monitor-events");events.innerHTML=rows.map(e=>item(`${e.title}<div class="meta">${e.action_status} · ${e.recommended_action}</div>`)).join("")||item("暂无监控事件")}loadCases();</script></body></html>"""


MOBILE_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>提醒详情</title><style>body{margin:0;font-family:"Microsoft YaHei",system-ui,sans-serif;background:#fbfcfb;color:#16211b}main{padding:18px;max-width:520px;margin:0 auto}h1{font-size:22px;margin:12px 0;letter-spacing:0}.box{border:1px solid #d9e1dc;border-radius:8px;background:white;padding:14px;margin:12px 0}.meta{color:#617068;font-size:13px}button{width:100%;min-height:42px;margin:6px 0;border-radius:7px;border:1px solid #146c5c;background:#146c5c;color:white;font-size:15px}button.secondary{background:white;color:#146c5c}</style></head><body><main><div class="meta">今日提醒</div><h1 id="title">提醒详情</h1><div class="box"><strong>为什么重要</strong><p id="why"></p></div><div class="box"><strong>来源</strong><p id="source"></p></div><div class="box"><strong>下一步</strong><p id="action"></p></div><button onclick="handle('ack')">确认</button><button class="secondary" onclick="handle('ignore')">忽略</button><button class="secondary" onclick="handle('convert-to-task')">转任务</button></main><script>const notificationId="__NOTIFICATION_ID__";const headers={"Authorization":"Bearer user_owner","X-Tenant-Id":"tenant_demo","X-Client-Type":"mobile_h5","Content-Type":"application/json"};let eventId=null;async function load(){const res=await fetch(`/bff/mobile/notifications/${notificationId}`,{headers});const body=await res.json();const data=body.data;title.textContent=data.title;why.textContent=data.why_important;source.textContent=(data.source_refs||[]).map(x=>`${x.source_name} · ${x.source_time}`).join("；");action.textContent=data.recommended_action;eventId=data.event_id}async function handle(actionName){await fetch(`/api/monitor-events/${eventId}/${actionName}`,{method:"POST",headers});await load()}load();</script></body></html>"""


app = create_app()
