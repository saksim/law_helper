# 施工文档包

本目录基于 [../platform-construction-blueprint.md](../platform-construction-blueprint.md) 拆解，用于把平台蓝图推进到可实现、可验收、可交接的施工状态。

## 九大施工文档

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

## 使用顺序

1. 先冻结 [01-PRD.md](01-PRD.md)、[02-UX_FLOW.md](02-UX_FLOW.md)、[03-DATA_DICTIONARY.md](03-DATA_DICTIONARY.md)。
2. 再并行推进 [04-API_CONTRACT.md](04-API_CONTRACT.md)、[05-PLUGIN_CONTRACT.md](05-PLUGIN_CONTRACT.md)、[06-SECURITY_POLICY.md](06-SECURITY_POLICY.md)。
3. 开发前必须确认 [07-QA_ACCEPTANCE_PLAN.md](07-QA_ACCEPTANCE_PLAN.md)。
4. 进入 Sprint 前确认 [08-IMPLEMENTATION_PLAN.md](08-IMPLEMENTATION_PLAN.md)。
5. 上线前补齐并演练 [09-RUNBOOK.md](09-RUNBOOK.md)。

## 范围锁定

本施工包只覆盖 P0 试点可用版：

```text
桌面 Web 工作台 + 移动 H5/通知入口 + 文档解析 + 财产线索报告 + 主体监控 + 权限审计 + 律师复核
```

P1/P2 内容只作为扩展边界，不进入当前必须交付范围。