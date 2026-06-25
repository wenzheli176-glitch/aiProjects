## ADDED Requirements

### Requirement: 合作方数据源超时表单

合作方新建/编辑 Modal MUST 提供「小红书超时(秒)」「黑猫超时(秒)」字段；留空表示使用全局默认；保存至 `source_timeouts`。

#### Scenario: 编辑合作方超时

- **当** 用户填写 xhs 超时 7200 并保存
- **则** `PUT /api/partners/{id}` MUST 持久化 `source_timeouts.xhs=7200`

### Requirement: Run keyword 子任务面板

Run 详情 Drawer MUST 展示 keyword 子任务表格（关键词、cohort、状态、阶段、超时、错误）；存在 failed 子任务时 MUST 提供「重跑失败 keyword」按钮调用 `POST /api/monitor/retry-keywords`。

#### Scenario: 查看子任务

- **当** 用户打开 Run 详情
- **则** MUST 请求 `GET /api/monitor/runs/{id}/keywords` 并渲染子任务列表

### Requirement: 任务列表子任务进度

监测任务列表状态列 MUST 在 `progress.subtasks` 存在时显示 `keyword done/total` 及 failed 计数。

#### Scenario: 运行中任务

- **当** 任务 crawling 且 progress.subtasks.total > 0
- **则** 状态列 MUST 显示子任务进度摘要
