# 施工文档包

本目录基于 [../platform-construction-blueprint.md](../platform-construction-blueprint.md) 拆解，用于把平台蓝图推进到可实现、可验收、可交接的施工状态。

## 十四大施工文档

| 顺序 | 文档 | 主责对象 | 目的 |
|---:|---|---|---|
| 01 | [01-PRD.md](01-PRD.md) | 产品/业务负责人 | 定义客户场景、MVP、非目标和业务验收 |
| 02 | [02-UX_FLOW.md](02-UX_FLOW.md) | 产品/设计/前端 | 定义桌面 Web、移动 H5、通知入口的用户流程 |
| 03 | [03-DATA_DICTIONARY.md](03-DATA_DICTIONARY.md) | 后端/数据/AI | 定义核心实体、字段、状态、枚举和数据血缘 |
| 04 | [04-API_CONTRACT.md](04-API_CONTRACT.md) | 前端/后端/BFF | 定义接口边界、请求响应、错误码和权限约束 |
| 05 | [05-PLUGIN_CONTRACT.md](05-PLUGIN_CONTRACT.md) | 平台/数据源/AI | 定义连接器、解析器、模型、通知插件的契约 |
| 06 | [06-SECURITY_POLICY.md](06-SECURITY_POLICY.md) | 安全/平台/交付 | 定义数据分级、权限、模型策略、审计和合规边界 |
| 07 | [07-QA_ACCEPTANCE_PLAN.md](07-QA_ACCEPTANCE_PLAN.md) | QA/产品/业务专家 | 定义功能验收、体验验收、移动端验收和上线门禁 |
| 08 | [08-IMPLEMENTATION_PLAN.md](08-IMPLEMENTATION_PLAN.md) | 项目/研发负责人 | 定义阶段、Sprint、依赖、里程碑和人员分工 |
| 09 | [09-RUNBOOK.md](09-RUNBOOK.md) | 运维/交付/值班 | 定义部署、故障处理、回滚、告警和运营巡检 |
| 10 | [10-P1_PRODUCTION_ENHANCEMENT.md](10-P1_PRODUCTION_ENHANCEMENT.md) | 平台/后端/交付 | 定义 P1 生产增强、稳定性、质量看板和团队持续使用能力 |
| 11 | [11-P1_DATA_SOURCE_EXPANSION.md](11-P1_DATA_SOURCE_EXPANSION.md) | 数据源/平台/合规 | 定义 P1 数据源扩展、授权治理、字段血缘和数据质量评分 |
| 12 | [12-P1_CASE_ASSISTANCE.md](12-P1_CASE_ASSISTANCE.md) | 产品/AI/法律专家 | 定义 P1 类案检索、证据矩阵、文书初稿、庭审摘要等办案辅助能力 |
| 13 | [13-P2_PLATFORMIZATION.md](13-P2_PLATFORMIZATION.md) | 平台架构/DevOps/安全 | 定义 P2 多团队、多律所、私有化部署、SLO、升级迁移和成本治理 |
| 14 | [14-P2_KNOWLEDGE_AND_GROWTH.md](14-P2_KNOWLEDGE_AND_GROWTH.md) | 产品/知识工程/经营负责人 | 定义 P2 私有知识图谱、业务开拓情报、政策监控、反馈蒸馏和经营看板 |

## 使用顺序

1. 先冻结 [01-PRD.md](01-PRD.md)、[02-UX_FLOW.md](02-UX_FLOW.md)、[03-DATA_DICTIONARY.md](03-DATA_DICTIONARY.md)。
2. 再并行推进 [04-API_CONTRACT.md](04-API_CONTRACT.md)、[05-PLUGIN_CONTRACT.md](05-PLUGIN_CONTRACT.md)、[06-SECURITY_POLICY.md](06-SECURITY_POLICY.md)。
3. 开发前必须确认 [07-QA_ACCEPTANCE_PLAN.md](07-QA_ACCEPTANCE_PLAN.md)。
4. 进入 Sprint 前确认 [08-IMPLEMENTATION_PLAN.md](08-IMPLEMENTATION_PLAN.md)。
5. 上线前补齐并演练 [09-RUNBOOK.md](09-RUNBOOK.md)。
6. P0 试点闭环稳定后，进入 [10-P1_PRODUCTION_ENHANCEMENT.md](10-P1_PRODUCTION_ENHANCEMENT.md)。
7. P1 能力按依赖推进：[11-P1_DATA_SOURCE_EXPANSION.md](11-P1_DATA_SOURCE_EXPANSION.md) 与 [12-P1_CASE_ASSISTANCE.md](12-P1_CASE_ASSISTANCE.md) 可并行，但都必须复用 04/05/06 的接口、插件和安全契约。
8. P2 必须在 P1 稳定后推进，先做 [13-P2_PLATFORMIZATION.md](13-P2_PLATFORMIZATION.md)，再做 [14-P2_KNOWLEDGE_AND_GROWTH.md](14-P2_KNOWLEDGE_AND_GROWTH.md)。

## 范围锁定

本施工包现在覆盖 P0/P1/P2 三个阶段，但必须分阶段施工，不能把未来平台化能力混入 P0 闭环。

P0 试点可用版：

```text
桌面 Web 工作台 + 移动 H5/通知入口 + 文档解析 + 财产线索报告 + 主体监控 + 权限审计 + 律师复核
```

P1 生产增强版：

```text
稳定服务一个律师团队 + 多案件持续使用 + 数据源扩展 + 类案/证据/文书辅助 + 质量评估 + 更完整交付运维
```

P2 平台产品版：

```text
多团队/多律所复制 + 插件治理台 + 私有知识图谱 + 业务增长情报 + 反馈蒸馏 + 经营/成本/SLO 治理
```

## 阶段边界

- P0 是已完成代码基线，后续修改不能破坏现有 P0 流程。
- P1 目标是生产增强，不优先做多律所平台化治理。
- P2 目标是规模化复制，不回头重写 P0/P1 主链路，除非有迁移文档和回滚方案。
- 新增 P1/P2 功能必须先落到对应编号文档，再进入代码实现。
