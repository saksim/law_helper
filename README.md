# 律师团队 AI 项目文档入口

本仓库的文档入口统一放在 [docs/README.md](docs/README.md)。
## P0 可运行原型

当前仓库已补入基于 [docs/working/implementation/01-PRD.md](docs/working/implementation/01-PRD.md) 的 P0 模块化单体原型，覆盖案件工作台、材料解析、主体识别、财产线索报告、监控提醒、移动 H5 轻操作、权限与审计。

运行：

```bash
python -m uvicorn law_platform.web:app --app-dir src --host 127.0.0.1 --port 8000
```

测试：

```bash
python -m pytest
```

当前文档已经按生命周期重组为：

- `docs/latest/`：现在正在使用的最新发布材料。
- `docs/working/`：当前迭代中的草案、待确认事项和改版工作。
- `docs/releases/`：每次正式发布留下的不可变快照和发布说明。
- `docs/discovery/`：方案探讨、需求推演、会议准备和技术论证。
- `docs/archive/`：已经退役的历史发布材料。

根目录不再放业务文档，避免“最终稿、草稿、旧稿、讨论稿”混在一起。
