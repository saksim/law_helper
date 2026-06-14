# 项目文档中心

我认可 `latest / working / releases / archive` 这个分层。它本质上是在区分文档的生命周期：正在做、现在用、这次发了什么、过去发生过什么。

但本项目还需要新增一层：`discovery/`。很多材料并不是手册、发布说明或历史归档，而是用于形成判断的探讨材料。如果把它们塞进 `working`，会让当前迭代显得过重；如果塞进 `archive`，又会丢掉它们作为论证链路的价值。

## 分层定义

| 层级 | 含义 | 放什么 | 不放什么 |
|---|---|---|---|
| `latest/` | 现在用 | 最新稳定沟通稿、当前可直接使用的演示/说明材料 | 草稿、分歧、旧版论证 |
| `working/` | 正在做 | 当前迭代草案、待确认清单、改版计划 | 已发布快照、长期方案脑暴 |
| `releases/` | 这次发了什么 | 按日期冻结的发布包、发布说明、发布清单 | 会继续修改的当前文档 |
| `discovery/` | 为什么这么做 | 需求对齐、方案推演、技术论证、会议话术、成本评估 | 对外承诺、最新使用手册 |
| `archive/` | 过去发生过什么 | 已退役但需要保留的历史发布材料 | 仍有参考价值的探讨材料 |

## 当前入口

- 最新使用材料：[latest/README.md](latest/README.md)
- 当前迭代：[working/README.md](working/README.md)
- 发布记录：[releases/README.md](releases/README.md)
- 探讨材料：[discovery/README.md](discovery/README.md)
- 历史归档：[archive/README.md](archive/README.md)

## 流转规则

1. 新想法、新反馈、新技术判断先进入 `discovery/`。
2. 被选中进入本轮交付的内容，整理到 `working/`。
3. 通过确认并准备给业务方使用的内容，发布到 `latest/`。
4. 每次发布时，把当次 `latest/` 需要冻结的内容复制到 `releases/YYYY-MM-DD/`。
5. 当 `latest/` 中的材料被新版本替代，并且不再作为当前使用入口时，再移动到 `archive/`。

## 命名约定

- 发布目录使用日期：`YYYY-MM-DD`。
- 探讨材料文件名前缀保留日期，后缀保留版本号或用途。
- `latest/` 使用面向读者的稳定文件名，不暴露 `V1/V2/V3` 这类过程版本。
- `working/` 可以使用迭代名，但需要在 README 中说明当前状态。