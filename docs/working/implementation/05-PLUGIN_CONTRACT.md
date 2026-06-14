# 05 PLUGIN_CONTRACT：插件契约

## 1. 目标

定义 P0/P1 平台插件机制，让数据源、文档解析器、模型供应商、评分器、报告模板和通知渠道可以插拔变化，但不破坏主业务流程、审计和安全策略。

## 2. 插件类型

| 类型 | 作用 | P0 示例 |
|---|---|---|
| DataConnector | 接入外部数据源 | 企业工商 API、司法拍卖、执行公开信息 |
| DocumentParser | 解析文件 | PaddleOCR/Docling/MinerU/Marker |
| Extractor | 抽取结构化信息 | 案件要素、金额、期限、主体 |
| Scorer | 评分 | 财产线索评分、事件重要性评分 |
| ModelProvider | 模型供应商 | 国内合规云、私有化模型、本地模型 |
| ReportTemplate | 报告模板 | 财产线索报告、案件要素摘要 |
| Notifier | 通知渠道 | 飞书、企业微信、邮件、站内通知 |
| ReviewPolicy | 复核策略 | 高风险必须负责人确认 |

## 3. 插件 Manifest

```yaml
plugin_id: qcc_connector
plugin_name: 企查查数据连接器
plugin_type: DataConnector
version: 1.0.0
owner: data-team
status: active
feature_flag: connector.qcc.enabled
supported_data_levels: [L0, L1]
required_permissions:
  - company.search
  - company.risk
rate_limit:
  requests_per_minute: 60
inputs:
  schema: subject_query_v1
outputs:
  schema: external_record_company_v1
compliance:
  authorized_api_required: true
  bypass_captcha_allowed: false
  stores_raw_response: true
  raw_response_retention_days: 30
contract_tests:
  - normalize_company_record
  - preserve_source_reference
  - reject_missing_authorization
rollback:
  disable_feature_flag: connector.qcc.enabled
```

## 4. 通用执行协议

插件执行输入：

```json
{
  "run_id": "run_001",
  "tenant_id": "tenant_001",
  "case_id": "case_001",
  "actor_id": "user_001",
  "data_policy": {
    "sensitivity_level": "L1",
    "allow_external_call": true
  },
  "payload": {}
}
```

插件执行输出：

```json
{
  "run_id": "run_001",
  "status": "success",
  "outputs": [],
  "source_refs": [],
  "warnings": [],
  "metrics": {
    "duration_ms": 1200,
    "records_count": 12
  }
}
```

失败输出：

```json
{
  "run_id": "run_001",
  "status": "failed",
  "error": {
    "code": "AUTHORIZATION_MISSING",
    "message": "缺少数据源授权"
  },
  "retryable": false
}
```

## 5. DataConnector 契约

必须做到：

- 不绕过验证码、登录、风控和付费墙。
- 标记授权状态。
- 保留来源名称、来源链接、查询时间、发布时间。
- 输出 canonical external_record。
- 支持 rate limit 和失败重试策略。
- 支持人工补录作为降级路径。

输出字段必须包含：

```json
{
  "source_name": "企查查",
  "source_url": "...",
  "record_type": "company",
  "record_time": "2026-06-01T00:00:00+08:00",
  "fetched_at": "2026-06-14T10:00:00+08:00",
  "normalized_payload": {},
  "authorization_status": "authorized"
}
```

## 6. DocumentParser 契约

必须输出：

- Markdown。
- JSON blocks。
- 页码和 bbox。
- block confidence。
- 表格和图片占位。
- 解析质量摘要。

禁止：

- 低置信度内容直接进入最终法律结论。
- 丢失原文件和页码映射。

## 7. ModelProvider 契约

必须声明：

- 支持的数据等级。
- 是否外部模型。
- 是否可能数据出境。
- 是否承诺不训练。
- 日志保留策略。
- 最大上下文和成本估算。
- 失败降级模型。

调用前必须经过数据策略网关。

## 8. ReportTemplate 契约

模板必须声明：

- 报告类型。
- 必填输入。
- 必填引用。
- 输出章节。
- 必须人工复核的段落。

财产线索报告 P0 必含：

```text
被执行人主体确认
执行公开信息摘要
工商与股权结构
对外投资与关联主体
司法拍卖资产线索
知识产权和经营权益线索
招投标/应收账款线索
疑似可追加主体或人格混同线索
线索价值排序
建议执行动作
待人工核验事项
```

## 9. Notifier 契约

通知内容必须包含：

- 标题。
- 事件类型。
- 为什么重要。
- 来源与发现时间。
- 建议动作。
- 深链。
- 操作按钮：确认、忽略、转任务。

## 10. Contract Test

每个插件必须通过：

- manifest schema 校验。
- 输入输出 schema 校验。
- 权限和数据等级校验。
- 失败路径校验。
- 审计日志校验。
- feature flag 禁用校验。

## 11. 回滚

任何插件升级必须支持：

- feature flag 关闭。
- 回滚旧版本。
- 清理未完成任务。
- 保留审计记录。
- 告警业务方哪些结果可能受影响。