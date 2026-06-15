# 13-P2 平台化施工文档

## 1. 阶段目标

P2 平台化目标是把 P1 中稳定服务单个律师团队的系统，升级为可复制给多个团队或多个律所的产品化平台。

核心结果：

- 多团队/多律所隔离。
- 团队级配置和策略治理。
- 插件治理台和版本管理。
- 私有化部署包、升级迁移手册和 SLO 体系。
- 成本、容量、安全、审计具备平台级可运营能力。

## 2. 租户与团队边界

| 层级 | 说明 |
|---|---|
| 平台 | 统一插件、模型、数据源、部署、审计策略 |
| 律所/组织 | 独立合同、数据边界、管理员、账单和合规策略 |
| 团队 | 执行业务团队、权限策略、案件配置、通知渠道 |
| 案件 | 文件、主体、线索、报告、任务、审计 |

## 3. 功能范围

| 编号 | 功能点 | 说明 | 验收 |
|---|---|---|---|
| P2-13-01 | 多租户隔离 | 组织、团队、案件、文件、审计强隔离 | 任一租户不能访问另一租户数据 |
| P2-13-02 | 团队级配置 | 模型、数据源、通知、报告模板按团队配置 | 团队配置变更不影响其他团队 |
| P2-13-03 | 插件治理台 | 插件启停、版本、契约测试、灰度、回滚 | 插件升级有灰度和回滚记录 |
| P2-13-04 | 私有化部署包 | 支持单客户私有化交付配置 | 部署清单、环境变量、初始化脚本完整 |
| P2-13-05 | 升级迁移手册 | 数据迁移、配置迁移、版本兼容、回滚 | 每次版本升级有迁移和回滚步骤 |
| P2-13-06 | 平台 SLO | 可用性、任务延迟、通知延迟、解析延迟、错误率 | SLO 可观测并有告警 |
| P2-13-07 | 成本看板 | 模型、数据源、存储、通知、任务成本 | 可按租户/团队/案件统计 |
| P2-13-08 | 审计归档 | 长期审计、导出、留存策略、不可篡改校验 | 合规审计可按租户导出 |

## 4. 架构影响

需要从模块化单体演进为“平台化模块化单体优先，瓶颈服务可拆分”的架构：

```text
Access/BFF
  -> Tenant Context
  -> Policy Gateway
  -> Case Domain / Document Domain / Plugin Domain / Quality Domain
  -> Shared Store / Object Store / Search Index / Task Queue
  -> Observability / Audit / Billing
```

服务拆分触发条件：

- 异步任务吞吐成为瓶颈。
- 文档解析或模型调用需要独立扩容。
- 插件运行安全隔离要求超过进程内治理能力。
- 多客户私有化部署要求独立组件生命周期。

## 5. 数据影响

建议新增或强化：

| 实体 | 用途 |
|---|---|
| `organizations` | 律所/客户组织 |
| `teams` | 团队与业务单元 |
| `tenant_policies` | 租户级安全、模型、数据源策略 |
| `plugin_versions` | 插件版本、灰度、回滚记录 |
| `deployment_profiles` | 私有化/云部署配置 |
| `migration_runs` | 升级迁移执行记录 |
| `slo_metrics` | SLO 指标和告警状态 |
| `cost_records` | 平台成本明细 |
| `audit_archives` | 审计归档和校验 |

## 6. API 影响

建议新增：

```text
GET  /api/organizations
POST /api/organizations
GET  /api/teams
POST /api/teams
PUT  /api/teams/{team_id}/policies
GET  /api/platform/plugins
POST /api/platform/plugins/{plugin_id}/rollout
POST /api/platform/plugins/{plugin_id}/rollback
GET  /api/platform/deployments/profiles
GET  /api/platform/migrations
POST /api/platform/migrations/{version}/run
GET  /api/platform/slo
GET  /api/platform/costs
GET  /api/platform/audit-archives
```

## 7. 安全与治理

- 所有查询必须带 tenant context。
- 审计日志必须包含 organization、team、case、actor、client type。
- 平台管理员不能默认读取客户案件正文，必须有授权流程。
- 私有化部署必须支持客户自有密钥。
- 插件升级必须支持租户级灰度。

## 8. 验收标准

- 两个组织、两个团队、多个案件并存时，权限隔离测试通过。
- 团队 A 的模型/数据源/通知配置不会影响团队 B。
- 插件灰度失败可回滚，未完成任务被清理或安全标记。
- SLO 看板至少展示可用性、任务延迟、通知延迟、错误率。
- 升级迁移必须有 dry-run、执行记录、失败回滚记录。

## 9. 回滚策略

- 多租户改造必须保持单租户兼容模式。
- 插件治理台失败时可退回管理员 API。
- SLO/成本看板失败不影响案件主链路。
- 私有化部署配置失败时可回退默认部署 profile。
