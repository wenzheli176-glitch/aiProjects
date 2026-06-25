# xhs-keyword-pipeline Specification

## Purpose
TBD - created by archiving change xhs-keyword-pipeline-subtasks. Update Purpose after archive.
## Requirements
### Requirement: 单 keyword 流水线

系统 SHALL 对每个 xhs keyword 依次执行：列表爬取 → list_triage → 同页 investigation，再进入下一 keyword；不得等全部 keyword list 完成后再批量 investigation 重搜。每个 keyword 开始前 MUST 完成账号池 pick 与 Worker profile rebind。

#### Scenario: Worker keyword_pipeline phase

- **当** 监测任务含 xhs 且 crawl_mode 为 list_first
- **则** `crawl_work_queue` MUST 为每个 keyword 入队 phase=`keyword_pipeline`
- **且** 执行 `run_xhs_keyword_pipeline` 在同页 DOM 完成需勘察条目的弹窗详情

#### Scenario: 跳过批量 xhs investigation

- **当** xhs 已全部经 keyword 流水线处理
- **则** `_run_post_list_crawl_phases` MUST NOT 对 xhs 再 enqueue 批量 investigation

#### Scenario: keyword 绑定账号后执行

- **WHEN** Worker claim keyword_pipeline 项
- **THEN** MUST 先 `pick_account_for_keyword` 并 rebind
- **AND** MUST 将 `account_id` 写入 keyword run stats_json 再进入 list 阶段

### Requirement: Keyword 子任务持久化

系统 SHALL 在 `monitor_keyword_runs` 记录每个 keyword 的 status、phase、timeout_sec、stats_json、error_message。

#### Scenario: 子任务进度汇总

- **当** keyword 子任务状态变更
- **则** `monitor_tasks.progress_json.subtasks` MUST 更新 `{total,done,failed,pending,running}`

### Requirement: 失败 keyword 重跑

系统 SHALL 提供 `POST /api/monitor/retry-keywords`，接受 `task_id` 与 `keyword_run_ids[]`，仅重跑指定 keyword 子任务并完成后执行 AI analyze。

#### Scenario: 重跑 API

- **当** 管理员 POST `{task_id, keyword_run_ids:[...]}`
- **则** 系统 MUST 创建新 Run 并仅 enqueue 对应 keyword 的 pipeline 项

### Requirement: Keyword 超时

单 keyword wall-clock 超时 MUST 为 `resolve_source_timeout_sec('xhs', partners, keyword)`；默认 `xhs.keyword_timeout_sec`（3600）。

#### Scenario: 超时失败

- **当** 单 keyword 执行超过 timeout_sec
- **则** 该 `monitor_keyword_runs` MUST 标记 `failed`，error 含 timeout 说明
- **且** 其他 keyword 子任务 MAY 继续（Worker 队列下一项）

### Requirement: Keyword 子任务阶段用时

系统 SHALL 在 keyword 子任务 `stats_json.phase_timing_ms` 记录三阶段 wall-clock：`list_crawl_ms`、`analyze_ms`（list_triage）、`investigation_ms`；运行中 MUST 通过 `_phase_started_at` 增量合并至 API 响应。

#### Scenario: 流水线阶段切换

- **WHEN** keyword 从 list → triage → investigation 依次执行
- **THEN** 每阶段结束 MUST 累加对应 timing 键并 `update_keyword_run(stats_json=...)`

#### Scenario: 失败保留部分用时

- **WHEN** keyword 子任务中途失败
- **THEN** 已完成阶段的 `phase_timing_ms` MUST 仍持久化

#### Scenario: 队列项阶段用时

- **WHEN** Worker 完成 heimao/xhs 队列项
- **THEN** `mark_done` MUST 写入 `payload._phase_timing_ms`（legacy_crawl → list_crawl_ms，investigation → investigation_ms）

### Requirement: Keyword 子任务账号追踪

系统 SHALL 在 `monitor_keyword_runs.stats_json` 持久化 `account_id`（及可选 `account_label`），供子任务 Tab 与排障使用。

#### Scenario: 子任务 Tab 展示账号

- **WHEN** 用户查看 xhs keyword 子任务行
- **THEN** MAY 显示执行该 keyword 的账号 label（若 API 提供）

