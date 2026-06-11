## ADDED Requirements

### Requirement: 首页数据看板

系统 SHALL 在统一 Web 壳提供「首页看板」Tab 作为默认入口，展示情报与监测任务汇总 KPI，并支持点击区块钻取到情报列表或任务/Run 视图。

#### Scenario: 默认 Tab

- **当** 用户访问 `/` 且未指定 `tab` query
- **则** 必须激活首页看板 Tab
- **且** `/dashboard` 重定向 MUST 指向 `/?tab=home`（或等价默认 home）

#### Scenario: Summary API

- **当** 调用 `GET /api/dashboard/summary`
- **则** 必须返回情报总数、medium+ 计数、今日新增、按 source/relevance 分布、运行中任务数、最近 Run 摘要（≤5 条）
- **且** 不得阻塞主线程超过合理时间（单 SQL 聚合为主）

#### Scenario: 钻取到情报列表

- **当** 用户点击看板上与来源或相关度相关的 KPI 卡片
- **则** 必须切换到情报 Tab 并带上对应 filter query（如 `source=heimao`、`relevance_min=medium`）
- **且** 情报列表 MUST 按 query 自动加载

#### Scenario: 钻取到任务或 Run

- **当** 用户点击看板最近 Run 或失败任务提示
- **则** 必须切换到监测任务 Tab 或打开 Run Drawer（`run_id` query）
- **且** 不得使用 `alert()` 展示 Run 摘要
