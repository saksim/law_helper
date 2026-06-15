# 11-P1 数据源扩展施工文档

## 1. 阶段目标

在 P0 连接器框架基础上，扩展更多授权数据源，并建立数据源质量、字段血缘、授权状态、成本和失败治理。

## 2. 数据源范围

### 2.1 P1 优先数据源

| 优先级 | 数据源类型 | 价值 | 接入原则 |
|---|---|---|---|
| P1-A | 企业工商/股权/风险商业 API | 主体画像、股权、涉诉、关联企业 | 优先正式 API 或授权账号 |
| P1-A | 执行公开信息 | 被执行、终本、恢复执行、限制高消费 | 优先官方/授权接口 |
| P1-A | 司法拍卖 | 可执行财产线索 | 优先 API，其次低频合规页面快照 |
| P1-B | 知识产权 | 商标、专利、著作权等可执行权益 | 先做结构化摘要和价值标记 |
| P1-B | 招投标/政府采购 | 应收账款、经营活跃度、客户关系 | 先作为辅助线索，不直接形成确定结论 |
| P1-C | 新闻/公告/RSS | 风险事件和政策事件 | 只进入监控提醒，不进入高置信资产结论 |

### 2.2 禁止事项

- 不绕过验证码、登录、付费墙或风控。
- 不抓取禁止自动访问的数据。
- 不保存超出授权范围的原始响应。
- 不把未经核验的外部数据直接写成法律结论。

## 3. 功能范围

| 编号 | 功能点 | 说明 | 验收 |
|---|---|---|---|
| P1-11-01 | 数据源目录 | 展示数据源授权、费用、字段、频率、状态 | 管理员能判断哪个源可用 |
| P1-11-02 | 字段血缘 | 外部字段映射到平台 canonical schema | 任一线索可回到数据源字段和响应摘要 |
| P1-11-03 | 数据质量评分 | 按完整性、新鲜度、稳定性、可信度评分 | 线索报告展示来源质量 |
| P1-11-04 | 授权凭证治理 | 配置 API key、token、账号状态、到期日 | 到期前提醒，敏感值脱敏 |
| P1-11-05 | 连接器健康检查 | 定时探测可用性、延迟、错误率 | 异常进入系统告警 |
| P1-11-06 | 手工补录增强 | 人工补录可绑定数据源、截图、说明和复核人 | 手工数据与自动数据可区分 |
| P1-11-07 | 数据源成本记录 | 记录调用量、失败量、单次成本或包月成本 | 团队可查看数据源成本趋势 |

## 4. 数据影响

建议新增或扩展：

| 实体 | 用途 |
|---|---|
| `data_source_catalog` | 数据源目录、授权、成本、状态 |
| `field_mappings` | 外部字段到平台字段的映射 |
| `data_quality_scores` | 数据质量评分结果 |
| `connector_health_checks` | 连接器健康检查历史 |
| `manual_record_attachments` | 人工补录附件、截图、说明 |
| `source_cost_records` | 数据源调用和成本记录 |

## 5. API 影响

建议新增：

```text
GET  /api/data-sources/catalog
PUT  /api/data-sources/{source_id}
POST /api/data-sources/{source_id}/health-check
GET  /api/data-sources/{source_id}/field-mappings
PUT  /api/data-sources/{source_id}/field-mappings
GET  /api/data-sources/{source_id}/quality
GET  /api/data-sources/costs
```

## 6. 插件契约扩展

DataConnector manifest 必须新增：

```yaml
authorization:
  type: api_key | oauth | manual | public
  expires_at: optional
quality:
  freshness_window_days: number
  required_fields: []
cost:
  billing_model: per_call | quota | subscription | unknown
lineage:
  field_mapping_version: string
```

## 7. 验收标准

- 每个 P1-A 数据源必须声明授权方式和字段映射。
- 连接器失败不能静默，必须进入健康检查和系统告警。
- 报告中的每条外部线索必须包含数据源质量摘要。
- 手工补录必须清楚标识为人工来源，并记录补录人和复核状态。
- 成本看板可以按数据源查看调用次数、失败次数和成本趋势。

## 8. 回滚策略

- 新数据源可通过 feature flag 单独关闭。
- 字段映射升级必须保留上一版本。
- 数据质量评分失败时，不阻塞原始记录入库，但报告必须提示“质量评分不可用”。
- 成本记录不可用时，不影响案件主流程。
