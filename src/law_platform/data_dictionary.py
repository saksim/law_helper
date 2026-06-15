from __future__ import annotations

from copy import deepcopy
from typing import Any

from .errors import AppError


ENUMS: dict[str, set[str]] = {
    'tenant_status': {'active', 'suspended'},
    'user_role': {'owner', 'lawyer', 'assistant', 'admin', 'reviewer', 'auditor'},
    'user_status': {'active', 'disabled'},
    'case_type': {'execution', 'litigation', 'arbitration', 'advisory'},
    'case_stage': {'intake', 'trial', 'execution', 'closed'},
    'case_risk_level': {'low', 'medium', 'high', 'critical'},
    'case_status': {'active', 'paused', 'closed'},
    'file_type': {'judgment', 'contract', 'evidence', 'chat_record', 'other'},
    'source_channel': {'web', 'mobile', 'wecom', 'feishu', 'email'},
    'parse_status': {'pending', 'running', 'review_required', 'done', 'failed'},
    'block_type': {'title', 'paragraph', 'table', 'image', 'footer', 'header'},
    'review_status': {'pending', 'confirmed', 'edited', 'rejected', 'task_created'},
    'sensitivity_level': {'L0', 'L1', 'L2', 'L3', 'L4'},
    'entity_object_type': {'case', 'file', 'report', 'external_record'},
    'entity_type': {'person', 'company', 'court', 'amount', 'date', 'case_no', 'deadline'},
    'subject_type': {'company', 'person'},
    'resolve_status': {'unresolved', 'candidate', 'confirmed', 'conflict'},
    'relation_type': {'shareholder', 'legal_representative', 'investment', 'branch', 'alias', 'related'},
    'external_record_type': {'execution', 'company', 'auction', 'ip', 'bid', 'news'},
    'authorization_status': {'authorized', 'manual', 'public', 'unknown'},
    'clue_type': {'equity', 'auction', 'ip', 'bid', 'receivable', 'related_subject', 'execution'},
    'monitor_event_type': {'new_execution', 'new_auction', 'equity_freeze', 'company_change', 'termination', 'recovery'},
    'importance': {'low', 'medium', 'high', 'critical'},
    'action_status': {'unread', 'acknowledged', 'ignored', 'task_created'},
    'report_type': {'asset_clue', 'case_summary', 'legal_research', 'evidence_matrix'},
    'generation_status': {'draft', 'review_required', 'confirmed', 'exported'},
    'generated_by': {'system', 'user'},
}


SCHEMAS: dict[str, dict[str, Any]] = {
    'tenants': {'required': {'id', 'name', 'status', 'settings'}, 'enums': {'status': 'tenant_status'}},
    'users': {'required': {'id', 'tenant_id', 'name', 'role', 'status'}, 'enums': {'role': 'user_role', 'status': 'user_status'}},
    'cases': {
        'required': {'id', 'tenant_id', 'case_name', 'case_type', 'stage', 'responsible_lawyer_id', 'risk_level', 'status'},
        'enums': {'case_type': 'case_type', 'stage': 'case_stage', 'risk_level': 'case_risk_level', 'status': 'case_status'},
    },
    'case_files': {
        'required': {'id', 'case_id', 'original_name', 'file_type', 'storage_path', 'parse_status', 'sensitivity_level', 'uploaded_by', 'source_channel'},
        'enums': {'file_type': 'file_type', 'parse_status': 'parse_status', 'sensitivity_level': 'sensitivity_level', 'source_channel': 'source_channel'},
    },
    'document_blocks': {
        'required': {'id', 'file_id', 'block_type', 'text', 'markdown', 'confidence', 'review_status'},
        'enums': {'block_type': 'block_type', 'review_status': 'review_status'},
    },
    'extracted_entities': {
        'required': {'id', 'object_type', 'object_id', 'entity_type', 'raw_text', 'normalized_value', 'source_ref', 'confidence'},
        'enums': {'object_type': 'entity_object_type', 'entity_type': 'entity_type'},
    },
    'subjects': {
        'required': {'id', 'tenant_id', 'subject_type', 'name', 'resolve_status', 'confidence'},
        'enums': {'subject_type': 'subject_type', 'resolve_status': 'resolve_status'},
    },
    'subject_relations': {'required': {'id', 'source_subject_id', 'target_subject_id', 'relation_type'}, 'enums': {'relation_type': 'relation_type'}},
    'external_records': {
        'required': {'id', 'connector_id', 'source_name', 'source_url', 'subject_id', 'record_type', 'record_time', 'fetched_at', 'normalized_payload', 'raw_payload_ref', 'authorization_status'},
        'enums': {'record_type': 'external_record_type', 'authorization_status': 'authorization_status'},
    },
    'asset_clues': {'required': {'id', 'case_id', 'subject_id', 'clue_type', 'title', 'source_refs', 'review_status'}, 'enums': {'clue_type': 'clue_type', 'review_status': 'review_status'}},
    'monitor_events': {
        'required': {'id', 'monitor_target_id', 'event_type', 'importance', 'detected_at', 'source_refs', 'action_status'},
        'enums': {'event_type': 'monitor_event_type', 'importance': 'importance', 'action_status': 'action_status'},
    },
    'reports': {
        'required': {'id', 'case_id', 'report_type', 'title', 'content_md', 'generation_status', 'generated_by', 'model_invocation_id'},
        'enums': {'report_type': 'report_type', 'generation_status': 'generation_status', 'generated_by': 'generated_by'},
    },
    'implementation_checkpoints': {'required': {'id', 'tenant_id', 'actor_id', 'created_at'}},
    'runbook_checks': {'required': {'id', 'tenant_id', 'actor_id', 'check_key', 'status', 'created_at'}},
    'runbook_incidents': {'required': {'id', 'tenant_id', 'actor_id', 'incident_type', 'severity', 'status', 'summary', 'created_at'}},
    'model_invocations': {'required': {'id', 'tenant_id', 'actor_id', 'case_id', 'provider', 'sensitivity_level', 'input_summary', 'output_summary', 'review_status', 'created_at'}, 'enums': {'sensitivity_level': 'sensitivity_level', 'review_status': 'review_status'}},
}


FILE_TYPE_ALIASES = {'case_material': 'other', 'execution_notice': 'judgment', 'material': 'other'}
SOURCE_CHANNEL_ALIASES = {'mobile_h5': 'mobile', 'app': 'mobile', 'mini_program': 'mobile'}
ENTITY_TYPE_ALIASES = {'unified_social_credit_code': 'company', 'cause_of_action': 'case_no', 'execution_basis': 'case_no', 'party': 'person'}
RELATION_ALIASES = {'case_party': 'related'}
RECORD_TYPE_ALIASES = {'receivable': 'bid'}
EVENT_TYPE_ALIASES = {'new_bid': 'company_change'}


def data_dictionary_payload() -> dict[str, Any]:
    return {
        'version': '03-DATA_DICTIONARY',
        'enums': {key: sorted(value) for key, value in ENUMS.items()},
        'schemas': deepcopy(SCHEMAS),
        'aliases': {
            'file_type': FILE_TYPE_ALIASES,
            'source_channel': SOURCE_CHANNEL_ALIASES,
            'entity_type': ENTITY_TYPE_ALIASES,
            'relation_type': RELATION_ALIASES,
            'record_type': RECORD_TYPE_ALIASES,
            'event_type': EVENT_TYPE_ALIASES,
        },
        'test_status': 'untested',
    }


def normalize_file_type(value: str | None) -> str:
    return FILE_TYPE_ALIASES.get(value or '', value or 'other')


def normalize_source_channel(value: str | None) -> str:
    return SOURCE_CHANNEL_ALIASES.get(value or '', value or 'web')


def normalize_dictionary_record(collection: str, item: dict[str, Any]) -> dict[str, Any]:
    row = deepcopy(item)
    if collection == 'case_files':
        row['file_type'] = normalize_file_type(row.get('file_type'))
        row['source_channel'] = normalize_source_channel(row.get('source_channel'))
    elif collection == 'extracted_entities':
        original = row.get('entity_type')
        normalized = ENTITY_TYPE_ALIASES.get(original or '', original)
        if normalized != original and original:
            row.setdefault('extraction_key', original)
            row['entity_type'] = normalized
    elif collection == 'subject_relations':
        row['relation_type'] = RELATION_ALIASES.get(row.get('relation_type') or '', row.get('relation_type'))
    elif collection == 'external_records':
        original = row.get('record_type')
        normalized = RECORD_TYPE_ALIASES.get(original or '', original)
        if normalized != original and original:
            row.setdefault('normalized_payload', {})
            row['normalized_payload'].setdefault('asset_subtype', original)
            row['record_type'] = normalized
        row.setdefault('authorization_status', 'unknown')
        row.setdefault('sensitivity_level', 'L1')
    elif collection == 'monitor_events':
        row['event_type'] = EVENT_TYPE_ALIASES.get(row.get('event_type') or '', row.get('event_type'))
    elif collection == 'reports':
        row.setdefault('model_invocation_id', None)
    elif collection == 'model_invocations':
        row.setdefault('review_status', 'pending')
    return row


def normalize_store_data(data: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    normalized = deepcopy(data)
    for collection, rows in list(normalized.items()):
        if isinstance(rows, list):
            normalized[collection] = [normalize_dictionary_record(collection, row) for row in rows]
    return normalized


def validate_dictionary_record(collection: str, item: dict[str, Any]) -> list[str]:
    schema = SCHEMAS.get(collection)
    if not schema:
        return []
    errors: list[str] = []
    record_id = item.get('id', '<new>')
    for field in sorted(schema.get('required', set())):
        if field not in item:
            errors.append(f'{collection}:{record_id}:missing:{field}')
    for field, enum_name in schema.get('enums', {}).items():
        value = item.get(field)
        if value is not None and value not in ENUMS[enum_name]:
            errors.append(f'{collection}:{record_id}:enum:{field}={value}')
    if errors:
        raise AppError('DATA_DICTIONARY_VIOLATION', 'Data record does not match 03-DATA_DICTIONARY.md', 400, {'errors': errors})
    return errors


def validate_store_against_dictionary(store: Any) -> dict[str, Any]:
    rows_checked = 0
    errors: list[str] = []
    for collection in sorted(SCHEMAS):
        for row in store.list(collection):
            rows_checked += 1
            try:
                validate_dictionary_record(collection, normalize_dictionary_record(collection, row))
            except AppError as exc:
                errors.extend(exc.details.get('errors', []))
    return {'status': 'passed' if not errors else 'failed', 'rows_checked': rows_checked, 'errors': errors, 'test_status': 'untested'}


def model_invocation_record(
    *,
    tenant_id: str,
    actor_id: str,
    case_id: str,
    object_type: str,
    object_id: str,
    provider: str,
    model_name: str,
    sensitivity_level: str,
    input_summary: str,
    output_summary: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        'tenant_id': tenant_id,
        'actor_id': actor_id,
        'case_id': case_id,
        'object_type': object_type,
        'object_id': object_id,
        'provider': provider,
        'model_name': model_name,
        'sensitivity_level': sensitivity_level,
        'input_summary': input_summary,
        'output_summary': output_summary,
        'review_status': 'pending',
        'created_at': created_at,
        'updated_at': created_at,
    }


def build_lineage(store: Any, object_type: str, object_id: str) -> dict[str, Any]:
    if object_type == 'asset_clue':
        obj = store.get('asset_clues', object_id)
        if not obj:
            raise AppError('VALIDATION_ERROR', 'Asset clue does not exist', 404)
        source_refs = obj.get('source_refs') or []
    elif object_type == 'report':
        obj = store.get('reports', object_id)
        if not obj:
            raise AppError('VALIDATION_ERROR', 'Report does not exist', 404)
        clues = [row for row in store.list('asset_clues') if row.get('report_id') == object_id]
        source_refs = [ref for clue in clues for ref in clue.get('source_refs', [])]
    elif object_type == 'monitor_event':
        obj = store.get('monitor_events', object_id)
        if not obj:
            raise AppError('VALIDATION_ERROR', 'Monitor event does not exist', 404)
        source_refs = obj.get('source_refs') or []
    else:
        raise AppError('VALIDATION_ERROR', 'Unsupported lineage object type', 400)

    external_records = []
    for ref in source_refs:
        record_id = ref.get('external_record_id')
        if record_id:
            record = store.get('external_records', record_id)
            if record:
                external_records.append(record)

    model_invocations = [
        row
        for row in store.list('model_invocations')
        if row.get('object_type') == object_type and row.get('object_id') == object_id
    ]
    if object_type == 'report' and obj.get('model_invocation_id'):
        invocation = store.get('model_invocations', obj['model_invocation_id'])
        if invocation and invocation not in model_invocations:
            model_invocations.append(invocation)

    review_records = [row for row in store.list('review_records') if row.get('object_type') == object_type and row.get('object_id') == object_id]

    return {
        'object_type': object_type,
        'object_id': object_id,
        'business_object': obj,
        'source_refs': source_refs,
        'external_records': external_records,
        'model_invocations': model_invocations,
        'review_records': review_records,
        'trace_status': 'complete' if source_refs or model_invocations else 'partial',
        'test_status': 'untested',
    }
