# 03 DATA_DICTIONARY：核心数据字典

## 1. 设计原则

- 所有业务结论必须可追溯到来源记录、原文片段或人工复核。
- P0 先用 PostgreSQL 表达主体关系，不急于独立图数据库。
- 所有外部数据保留来源、时间、授权状态和原始响应摘要。
- 所有 AI 输出保留模型调用、输入摘要、输出摘要和复核状态。

## 2. 命名约定

- 主键统一使用 `id`。
- 外键使用 `{entity}_id`。
- 状态字段使用 `_status` 后缀。
- 时间字段使用 ISO 8601，统一记录 `created_at`、`updated_at`。
- 敏感字段必须标记 `sensitivity_level`。

## 3. 核心实体

### 3.1 tenants

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 租户 ID |
| name | string | 是 | 团队/律所名称 |
| status | enum | 是 | active/suspended |
| settings | jsonb | 否 | 租户配置 |

### 3.2 users

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 用户 ID |
| tenant_id | uuid | 是 | 租户 |
| name | string | 是 | 姓名 |
| role | enum | 是 | owner/lawyer/assistant/admin/reviewer |
| phone | string | 否 | 手机号，需脱敏展示 |
| email | string | 否 | 邮箱 |
| status | enum | 是 | active/disabled |

### 3.3 cases

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 案件 ID |
| tenant_id | uuid | 是 | 租户 |
| case_name | string | 是 | 案件名称 |
| case_type | enum | 是 | execution/litigation/arbitration/advisory |
| cause_of_action | string | 否 | 案由 |
| stage | enum | 是 | intake/trial/execution/closed |
| amount | decimal | 否 | 标的金额 |
| responsible_lawyer_id | uuid | 否 | 承办律师 |
| risk_level | enum | 否 | low/medium/high/critical |
| status | enum | 是 | active/paused/closed |

### 3.4 case_files

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 文件 ID |
| case_id | uuid | 是 | 案件 |
| original_name | string | 是 | 原文件名 |
| file_type | enum | 是 | judgment/contract/evidence/chat_record/other |
| storage_path | string | 是 | 对象存储路径 |
| parse_status | enum | 是 | pending/running/review_required/done/failed |
| sensitivity_level | enum | 是 | L0/L1/L2/L3/L4 |
| uploaded_by | uuid | 是 | 上传人 |
| source_channel | enum | 是 | web/mobile/wecom/feishu/email |

### 3.5 document_blocks

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 文档块 ID |
| file_id | uuid | 是 | 文件 |
| page_no | int | 是 | 页码 |
| block_type | enum | 是 | title/paragraph/table/image/footer/header |
| text | text | 否 | 文本内容 |
| markdown | text | 否 | Markdown 内容 |
| bbox | jsonb | 否 | PDF 坐标 |
| confidence | float | 是 | 置信度 |
| review_status | enum | 是 | pending/confirmed/edited/rejected |

### 3.6 extracted_entities

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 实体 ID |
| object_type | enum | 是 | case/file/report/external_record |
| object_id | uuid | 是 | 所属对象 |
| entity_type | enum | 是 | person/company/court/amount/date/case_no/deadline |
| raw_text | string | 是 | 原文 |
| normalized_value | string | 否 | 归一化值 |
| source_ref | jsonb | 是 | 页码/片段/外部来源 |
| confidence | float | 是 | 置信度 |

### 3.7 subjects

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 主体 ID |
| tenant_id | uuid | 是 | 租户 |
| subject_type | enum | 是 | company/person |
| name | string | 是 | 主体名称 |
| unified_social_credit_code | string | 否 | 统一社会信用代码 |
| id_card_hash | string | 否 | 身份证哈希，不存明文优先 |
| resolve_status | enum | 是 | unresolved/candidate/confirmed/conflict |
| confidence | float | 否 | 消歧置信度 |

### 3.8 subject_relations

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 关系 ID |
| source_subject_id | uuid | 是 | 来源主体 |
| target_subject_id | uuid | 是 | 目标主体 |
| relation_type | enum | 是 | shareholder/legal_representative/investment/branch/alias/related |
| strength | float | 否 | 关系强度 |
| source_record_id | uuid | 否 | 来源记录 |

### 3.9 external_records

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 外部记录 ID |
| connector_id | string | 是 | 连接器 |
| source_name | string | 是 | 数据源名称 |
| source_url | string | 否 | 来源链接 |
| subject_id | uuid | 否 | 关联主体 |
| record_type | enum | 是 | execution/company/auction/ip/bid/news |
| record_time | datetime | 否 | 数据源发布时间 |
| fetched_at | datetime | 是 | 抓取/查询时间 |
| normalized_payload | jsonb | 是 | 规范化数据 |
| raw_payload_ref | string | 否 | 原始响应存储引用 |
| authorization_status | enum | 是 | authorized/manual/public/unknown |

### 3.10 asset_clues

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 线索 ID |
| case_id | uuid | 是 | 案件 |
| subject_id | uuid | 是 | 主体 |
| clue_type | enum | 是 | equity/auction/ip/bid/receivable/related_subject/execution |
| title | string | 是 | 线索标题 |
| description | text | 是 | 线索说明 |
| estimated_value | string | 否 | 估算价值 |
| actionability_score | int | 是 | 0-100 |
| confidence | float | 是 | 置信度 |
| source_refs | jsonb | 是 | 来源引用数组 |
| review_status | enum | 是 | pending/confirmed/edited/rejected/task_created |
| recommended_action | text | 否 | 建议动作 |

### 3.11 monitor_events

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 事件 ID |
| monitor_target_id | uuid | 是 | 监控目标 |
| event_type | enum | 是 | new_execution/new_auction/equity_freeze/company_change/termination/recovery |
| title | string | 是 | 事件标题 |
| importance | enum | 是 | low/medium/high/critical |
| detected_at | datetime | 是 | 发现时间 |
| source_refs | jsonb | 是 | 来源 |
| action_status | enum | 是 | unread/acknowledged/ignored/task_created |

### 3.12 reports

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 报告 ID |
| case_id | uuid | 是 | 案件 |
| report_type | enum | 是 | asset_clue/case_summary/legal_research/evidence_matrix |
| title | string | 是 | 报告标题 |
| content_md | text | 是 | Markdown 内容 |
| generation_status | enum | 是 | draft/review_required/confirmed/exported |
| generated_by | enum | 是 | system/user |
| model_invocation_id | uuid | 否 | 模型调用 |
| reviewed_by | uuid | 否 | 复核人 |

### 3.13 audit_logs

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| id | uuid | 是 | 审计 ID |
| tenant_id | uuid | 是 | 租户 |
| actor_id | uuid | 是 | 操作人 |
| action | string | 是 | 操作 |
| object_type | string | 是 | 对象类型 |
| object_id | string | 是 | 对象 ID |
| ip | string | 否 | IP |
| user_agent | string | 否 | UA |
| metadata | jsonb | 否 | 附加信息 |
| created_at | datetime | 是 | 时间 |

## 4. 枚举定义

### sensitivity_level

| 值 | 含义 | 处理策略 |
|---|---|---|
| L0 | 法条、公开案例、公开政策 | 可进入常规模型 |
| L1 | 工商、拍卖、公开执行信息 | 优先国内，可脱敏分析 |
| L2 | 脱敏案件摘要 | 按合规策略选择模型 |
| L3 | 合同、证据、聊天记录 | 国内合规云/私有化优先 |
| L4 | 身份证、流水、商业秘密 | 本地/私有化，禁止外部模型 |

### review_status

| 值 | 含义 |
|---|---|
| pending | 待复核 |
| confirmed | 已确认 |
| edited | 已修改 |
| rejected | 已驳回 |
| task_created | 已转任务 |

## 5. 数据血缘要求

所有 `asset_clues`、`reports`、`monitor_events` 必须能追溯：

```text
业务对象 -> 来源记录/文档块 -> 数据源/原文件 -> 查询时间/页码/坐标 -> 复核记录
```

## 6. 交接对象

- 给后端：作为数据库 schema 和领域模型基础。
- 给前端：作为字段展示、筛选、状态文案基础。
- 给 AI：作为抽取输出 schema。
- 给 QA：作为数据完整性与血缘测试依据。