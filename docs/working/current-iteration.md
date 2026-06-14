# 当前迭代：文档层革新

生成日期：2026-06-14

## 目标

把原本散落在根目录、`archive/` 和 `ppt_img2_guides/` 中的 Markdown 文档，重组为清晰的文档生命周期结构。

## 本轮决策

- 认可 `latest / working / releases / archive` 四层。
- 新增 `discovery/` 作为探讨层，承接方案推演、需求对齐、技术论证和会议准备材料。
- 根目录不再存放业务文档，只保留项目入口。
- `latest/` 使用稳定命名，不保留过程版本号。
- `releases/` 按日期冻结发布包。

## 迁移结果

| 原位置 | 新位置 | 归类理由 |
|---|---|---|
| `LEGAL_TEAM_AI_FINAL_COMMUNICATION.md` | `docs/latest/project-communication-guide.md` | 当前稳定沟通文档 |
| `ppt_img2_guides/` | `docs/latest/presentation-guides/` | 当前可使用的演示生成与讲解材料 |
| `archive/LEGAL_TEAM_AI_COST_PROFIT_STRATEGY_V1.md` | `docs/discovery/proposals/2026-06-01-cost-profit-strategy-v1.md` | 早期成本与收益方案推演 |
| `archive/LEGAL_TEAM_AI_CASE_NLP_ARCHITECTURE_V2.md` | `docs/discovery/proposals/2026-06-01-case-nlp-architecture-v2.md` | 技术架构论证 |
| `archive/LEGAL_TEAM_AI_REQUIREMENT_ALIGNMENT_V3.md` | `docs/discovery/proposals/2026-06-01-requirement-alignment-v3.md` | 需求对齐与实施评估 |
| `archive/LEGAL_TEAM_AI_MEETING_TALK_TRACK_V4.md` | `docs/discovery/meeting-prep/2026-06-01-meeting-talk-track-v4.md` | 会议沟通准备材料 |

## 待确认

- 后续是否需要把 `latest/project-communication-guide.md` 拆成业务版、IT 版和决策版。
- 是否要为每次发布增加签收人、适用对象和废止日期。
- 是否需要为 `discovery/` 建立状态标签，例如 `draft`、`superseded`、`adopted`。