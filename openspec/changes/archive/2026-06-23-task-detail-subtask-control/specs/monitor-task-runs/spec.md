## ADDED Requirements

### Requirement: 分源暂停与终止

系统 SHALL 在 `monitor_task_runs.source_halt_json` 记录 per-source halt（`pause` | `stop`）；Worker/Runner MUST 通过 `is_halt_requested(run_id, source_id)` 响应。

#### Scenario: 暂停单源

- **WHEN** `POST /api/monitor/tasks/{id}/pause` 且 body/query 含 `source=xhs`
- **THEN** MUST 设置 `source_halt_json.xhs=pause`
- **且** 其他源 MAY 继续执行直至完成或单独 pause

#### Scenario: 终止整任务

- **WHEN** `POST /api/monitor/tasks/{id}/stop`（任意 source 参数）
- **THEN** MUST 全局终止：取消未完成 keyword/队列、终止 Worker、`finish_task_run(stopped)`
- **且** 任务 `status=stopped`，**不得** 提供 continue（仅 pause 可 resume）

#### Scenario: 暂停后 Run 收尾

- **WHEN** 用户 pause（全局或单源导致任务 paused）
- **THEN** 活跃 Run MUST `finish_task_run(paused)` 且清除 halt 阻塞以便 resume

#### Scenario: 继续任务

- **WHEN** `POST /api/monitor/tasks/{id}/resume` 且任务 `status=paused`
- **THEN** MUST 基于 `resume_run_id` 与 `list_resume_sources` 续跑未完成工作
- **WHEN** 任务 `status=stopped`
- **THEN** MUST 拒绝 resume

### Requirement: Run 分源子任务 API

系统 SHALL 提供 `GET /api/monitor/runs/{run_id}/subtasks`，返回按 `source_id` 分组的子任务汇总与 `subtask_items` 统一列表。

#### Scenario: 响应结构

- **WHEN** 调用 subtasks API
- **THEN** 每源 MUST 含 `queue`、`keywords` 计数、`status`、`halt`、`subtask_items`
- **且** 每项 MUST 含 `detail_status`、`detail_label`、`phase_timing_ms`（list_crawl_ms / investigation_ms / analyze_ms）

#### Scenario: 任务 progress 同步

- **WHEN** 子任务状态变更
- **THEN** `sync_task_subtask_progress` MUST 写入 `monitor_tasks.progress_json.sources`

## MODIFIED Requirements

### Requirement: Run 历史 API 与 UI

系统 SHALL 提供 run 列表 API，并在监测任务 UI 展示 Run 历史；**任务详情 → 执行历史 Tab** MUST 为主入口之一。任务列表行内 MAY 保留展开摘要；选中 Run 后 Drawer MAY 仍可用，但不得与任务详情页互斥。

#### Scenario: 任务详情执行历史

- **WHEN** 用户在任务详情打开「执行历史」Tab
- **THEN** MUST 分页加载 `GET /api/monitor/tasks/{id}/runs`
- **且** 支持「加载更多」
