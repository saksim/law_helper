# Slide 07 - IT 负责人视角：系统架构

## 页面目标

让 IT 负责人看到这不是接 API，而是轻量平台底座。

## 主标题

IT 负责人视角：不是接一个大模型 API

## 页面文案

第一阶段需要的轻量平台底座：

```text
Document Pipeline
+ External Data Connector
+ Entity Resolution
+ Asset Clue Engine
+ Monitoring & Notification
+ Legal Extraction/RAG
+ Audit & Permission
```

## 视觉布局

- 分层架构图。
- 从上到下：
  - 前端工作台
  - 业务服务层
  - AI/NLP 层
  - 数据层
  - 外部数据源

## 建议图形

五层架构图：

1. 工作台：文档、线索、监控、报告
2. 服务：案件、文档、线索、监控、通知、审计
3. AI：OCR、抽取、RAG、线索评分
4. 数据：PostgreSQL、对象存储、向量库、全文检索
5. 外部：执行网、工商、商业 API、司法拍卖

## 演讲提示

强调：模型可以替换，数据结构和工作流不能乱。
