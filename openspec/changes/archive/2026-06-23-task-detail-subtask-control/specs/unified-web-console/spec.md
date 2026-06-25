## ADDED Requirements

### Requirement: 监测任务详情页

系统 SHALL 在监测任务 Tab 提供列表视图与任务详情视图；详情 MUST 含 **概览**、**执行历史**、**子任务**、**源数据**、**情报** 五个子 Tab。

#### Scenario: URL 深链

- **WHEN** URL 含 `?tab=tasks&monitor_task_id={id}&task_tab=overview|runs|subtasks|raw|intel`
- **THEN** MUST 展示任务详情视图并激活对应子 Tab

#### Scenario: 返回列表

- **WHEN** 用户在详情点击「返回」
- **THEN** MUST 清除 `monitor_task_id`、`task_tab`、`run_id` query
- **且** 展示任务列表视图

#### Scenario: 列表行进入详情

- **WHEN** 用户点击任务列表行或「详情」
- **THEN** MUST 打开任务详情（不得仅展开 Run Drawer 作为唯一入口）

### Requirement: 任务详情子任务 Tab

子任务 Tab MUST 按数据源分块展示队列与 keyword 合并列表；每行 MUST 含细粒度状态（排队 / 爬取列表 / 勘察详情 / 分析 / 完成 / 失败）及三列阶段用时：**列表爬取**、**详情勘察**、**分析**（毫秒，运行中增量更新）。

#### Scenario: 选择 Run 并刷新

- **WHEN** 用户选择 Run 并点击「刷新」
- **THEN** MUST 请求 `GET /api/monitor/runs/{run_id}/subtasks`
- **且** 渲染每源 `subtask_items` 表格

#### Scenario: 运行中增量刷新

- **WHEN** 任务 crawling/analyzing 且用户位于子任务 Tab
- **THEN** 轮询 MUST 通过 patch 更新状态与阶段用时
- **且** 不得整页替换为「加载中…」

#### Scenario: 重跑失败 keyword

- **WHEN** xhs 源存在 failed 子任务
- **THEN** MUST 提供「重跑失败」按钮调用 `POST /api/monitor/retry-keywords`

### Requirement: 任务详情源数据与情报 Tab

详情页源数据/情报 Tab MUST 展示该任务下 raw/intel 列表（各最多 100 条）；运行中轮询 MUST 增量 patch 表格行，保留滚动位置，不得闪屏。

#### Scenario: 手动刷新

- **WHEN** 用户点击 Tab 内「刷新」
- **THEN** MAY 显示加载态后渲染全表

#### Scenario: 自动刷新

- **WHEN** 任务运行中且用户位于源数据或情报 Tab
- **THEN** MUST 仅更新变更行与计数
- **且** 新增行插入列表顶部时 MUST 补偿 scrollTop

### Requirement: 任务列表无闪屏刷新与分源进度

监测任务列表在轮询刷新时 MUST 使用行级 patch（`patchTaskRow`）；状态列 MUST 在 `progress.sources` 存在时展示分源子任务摘要；`#taskStatus` MUST 显示中文进度摘要而非 JSON。

#### Scenario: 运行中轮询

- **WHEN** 存在 crawling/analyzing 任务且列表可见
- **THEN** 每 3s 刷新 MUST 不重建整表 DOM
- **且** 已展开 Run 历史行 MUST 保持展开状态

## MODIFIED Requirements

### Requirement: Run keyword 子任务面板

Run 详情 MAY 保留 keyword 子任务表；**任务详情 → 子任务 Tab** MUST 为分源子任务的主入口，展示 keyword 与队列统一列表及阶段用时列。存在 failed keyword 时 MUST 提供「重跑失败 keyword」按钮。

#### Scenario: 查看子任务

- **WHEN** 用户在任务详情子任务 Tab 选择 Run
- **THEN** MUST 请求 subtasks API 并渲染分源块与子任务表
- **且** 表格 MUST 含列表爬取 / 详情勘察 / 分析 用时列

### Requirement: 任务列表子任务进度

监测任务列表状态列 MUST 在 `progress.subtasks` 或 `progress.sources` 存在时显示子任务/分源进度摘要（含 failed 计数）。

#### Scenario: 运行中任务

- **WHEN** 任务 crawling 且 progress 含分源或 keyword 汇总
- **THEN** 状态列 MUST 显示可读进度摘要（非原始 JSON）
