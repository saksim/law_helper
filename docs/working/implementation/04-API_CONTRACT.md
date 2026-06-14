# 04 API_CONTRACT：接口契约

## 1. 目标

定义 P0 阶段桌面 Web、移动 H5、通知入口、BFF 与后端服务之间的接口边界。

原则：

- 多端不直接拼复杂业务 API，由 Client BFF 聚合。
- 所有接口必须带租户、权限和审计上下文。
- 所有 AI/插件结果必须能返回来源、状态、错误和复核信息。

## 2. 通用约定

### 2.1 请求头

```http
Authorization: Bearer <token>
X-Tenant-Id: <tenant_id>
X-Request-Id: <uuid>
X-Client-Type: web|mobile_h5|mini_program|bot|admin
```

### 2.2 通用响应

```json
{
  "request_id": "uuid",
  "data": {},
  "meta": {
    "server_time": "2026-06-14T10:00:00+08:00"
  }
}
```

### 2.3 通用错误

```json
{
  "request_id": "uuid",
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "无权访问该案件",
    "details": {}
  }
}
```

错误码：

| code | 含义 |
|---|---|
| VALIDATION_ERROR | 请求参数错误 |
| PERMISSION_DENIED | 权限不足 |
| DATA_POLICY_BLOCKED | 数据策略拦截 |
| CONNECTOR_UNAVAILABLE | 数据源不可用 |
| MODEL_UNAVAILABLE | 模型不可用 |
| REVIEW_REQUIRED | 需要人工复核 |
| RATE_LIMITED | 触发频率限制 |

## 3. BFF 接口

### 3.1 案件首页聚合

```http
GET /bff/cases/{case_id}/overview
```

返回：

```json
{
  "case": {
    "id": "case_001",
    "case_name": "A 公司执行案件",
    "stage": "execution",
    "risk_level": "high"
  },
  "today_highlights": [
    {
      "type": "asset_clue",
      "title": "发现新增司法拍卖资产",
      "importance": "high",
      "source_time": "2026-06-14T09:30:00+08:00",
      "action": "建议核验资产归属"
    }
  ],
  "pending_reviews": [],
  "deadlines": [],
  "tasks": []
}
```

### 3.2 移动提醒详情

```http
GET /bff/mobile/notifications/{notification_id}
```

必须返回轻量字段：标题、为什么重要、来源、下一步动作、操作按钮。

## 4. 案件接口

```http
POST /api/cases
GET /api/cases
GET /api/cases/{case_id}
PATCH /api/cases/{case_id}
```

创建案件请求：

```json
{
  "case_name": "A 公司执行案件",
  "case_type": "execution",
  "cause_of_action": "买卖合同纠纷",
  "amount": 1200000,
  "responsible_lawyer_id": "user_001"
}
```

## 5. 文件与文档解析接口

### 5.1 上传文件

```http
POST /api/cases/{case_id}/files
Content-Type: multipart/form-data
```

字段：

- `file`: 文件。
- `file_type`: judgment/contract/evidence/other。
- `sensitivity_level`: L0-L4。

### 5.2 查询解析结果

```http
GET /api/files/{file_id}/parse-result
```

返回：

```json
{
  "file_id": "file_001",
  "parse_status": "review_required",
  "markdown_url": "/api/files/file_001/markdown",
  "blocks": [
    {
      "id": "block_001",
      "page_no": 1,
      "block_type": "paragraph",
      "text": "...",
      "confidence": 0.72,
      "review_status": "pending",
      "bbox": [60, 100, 500, 160]
    }
  ]
}
```

### 5.3 复核解析块

```http
POST /api/document-blocks/{block_id}/review
```

```json
{
  "review_status": "edited",
  "corrected_text": "修正后的内容",
  "reason": "OCR 识别错误"
}
```

## 6. 主体接口

```http
POST /api/subjects/resolve
GET /api/subjects/{subject_id}
POST /api/cases/{case_id}/subjects
```

主体消歧请求：

```json
{
  "name": "某某科技有限公司",
  "unified_social_credit_code": "可选",
  "case_id": "case_001"
}
```

返回候选：

```json
{
  "candidates": [
    {
      "subject_id": "sub_001",
      "name": "某某科技有限公司",
      "unified_social_credit_code": "...",
      "confidence": 0.92,
      "source_refs": []
    }
  ],
  "requires_confirmation": true
}
```

## 7. 财产线索接口

### 7.1 生成报告

```http
POST /api/cases/{case_id}/asset-clue-reports
```

```json
{
  "subject_id": "sub_001",
  "connector_ids": ["qcc", "auction_public"],
  "report_template": "execution_asset_clue_v1"
}
```

返回异步任务：

```json
{
  "job_id": "job_001",
  "status": "running"
}
```

### 7.2 查询报告

```http
GET /api/reports/{report_id}
```

### 7.3 复核线索

```http
POST /api/asset-clues/{clue_id}/review
```

```json
{
  "review_status": "confirmed",
  "comment": "优先核验",
  "next_action": "create_task"
}
```

## 8. 监控接口

```http
POST /api/monitor-targets
GET /api/monitor-targets
GET /api/monitor-events
POST /api/monitor-events/{event_id}/ack
POST /api/monitor-events/{event_id}/ignore
POST /api/monitor-events/{event_id}/convert-to-task
```

创建监控：

```json
{
  "case_id": "case_001",
  "subject_id": "sub_001",
  "event_types": ["new_execution", "new_auction", "equity_freeze"],
  "frequency": "daily",
  "notify_channels": ["feishu", "email"]
}
```

## 9. 插件接口

```http
GET /api/plugins
POST /api/plugins/{plugin_id}/enable
POST /api/plugins/{plugin_id}/disable
POST /api/plugins/{plugin_id}/contract-tests
GET /api/plugin-runs
```

插件启用必须检查：授权、数据等级、contract test、feature flag。

## 10. 审计接口

```http
GET /api/audit-logs
GET /api/model-invocations
GET /api/review-records
```

审计查询仅管理员和授权负责人可用。

## 11. 验收

- 所有 P0 接口具备 OpenAPI 文档。
- 所有写操作记录 audit log。
- 所有列表支持分页。
- 所有外部调用类接口返回可理解错误。
- 所有敏感接口通过权限测试和数据策略测试。