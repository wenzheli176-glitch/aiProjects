# monitor-task-runs Specification

## Purpose
TBD - created by archiving change monitor-runs-schedule-incremental. Update Purpose after archive.
## Requirements
### Requirement: 任务执行 Run 记录

系统 SHALL 为每次 monitor_task 执行（手动或定时）创建 `monitor_task_runs` 记录，含 trigger、analyze_mode、crawl_only、status、started_at、finished_at、阶段耗时与统计 JSON。

#### Scenario: 手动执行创建 Run

- **当** 用户调用 `POST /api/monitor/run` 且任务未在运行
- **则** 必须创建 run 记录且 `trigger=manual`
- **且** 默认 `analyze_mode=incremental`
- **且** 默认 `crawl_only=false`

#### Scenario: Run 完成写入汇总

- **当** 爬取与分析阶段均结束（或失败/超时）；crawl_only 时分析阶段视为跳过
- **则** run 必须更新 `crawl_duration_ms`、`analyze_duration_ms`、`stats_json`
- **且** `monitor_tasks.last_run_id` 必须指向该 run

#### Scenario: 重叠执行跳过

- **当** 定时触发时 `S.running=true` 且 `skip_if_running=true`
- **则** 必须创建 `status=skipped_overlap` 的 run
- **且** 不得抢占当前运行中的任务

### Requirement: crawl_only 执行模式

系统 SHALL 支持监测 Run 的 `crawl_only` 模式：为 true 时 MUST 完成全部爬取阶段（含 list_triage、investigation_crawl）后跳过 AnalyzePipeline，不调用 `analyze_candidates`。

#### Scenario: API 启动 crawl_only Run

- **WHEN** 用户 `POST /api/monitor/run` 且 `crawl_only=true`
- **THEN** MUST 创建 run 且记录 `crawl_only=true`
- **AND** MUST 执行完整爬取流水线（含 xhs keyword 内 list_triage）
- **AND** MUST NOT 进入 `analyzing` 阶段或调用 `_run_analysis_phase`

#### Scenario: crawl_only Run 正常完成

- **WHEN** crawl_only Run 爬取阶段成功结束且无 keyword 子任务 failed
- **THEN** run `status` MUST 为 `done`
- **AND** `stats_json` MUST 含 `analyze_deferred=true`
- **AND** `stats_json` MUST 含 `pending_analyze_raw_count`（按 incremental 规则统计待分析 raw 数）
- **AND** `analyze_duration_ms` MUST 为 0

#### Scenario: 默认行为保持现网

- **WHEN** `POST /api/monitor/run` 未指定 `crawl_only` 且任务未配置默认
- **THEN** MUST 等同 `crawl_only=false` 并在爬取后执行 AnalyzePipeline

#### Scenario: 与 full_replace 互斥

- **WHEN** 请求 `crawl_only=true` 且 `analyze_mode=full_replace`
- **THEN** API MUST 返回 400 并拒绝启动

#### Scenario: resume 继承 crawl_only

- **WHEN** 用户从 crawl_only Run 继续执行剩余 crawl 子任务
- **THEN** 续跑 MUST 继承原 run 的 `crawl_only`
- **AND** 完成后 MUST NOT 自动触发 analyze

### Requirement: 分源爬取与分析时长

系统 SHALL 在单次 run 内按 `source_id` 汇总 wall-clock 爬取时长与分析时长，写入 `timing_by_source_json`。

#### Scenario: 分源爬取计时

- **当** `run_monitor_task` 对每个 source 调用 CrawlAdapter（含 crawl_list_batch 与 crawl_investigation）
- **则** 必须分别累计 list_crawl_ms 与 investigation_crawl_ms 至该 source
- **且** 必须记录 `raw_new` 与 `raw_updated` 计数

#### Scenario: 分源分析计时

- **当** list_triage 或 analyze_candidates 完成 LLM 调用
- **则** 必须将 list_triage 耗时计入 `triage_ms`（run 级或 by_source）
- **且** 完整 analyze 耗时仍计入 analyze_ms

### Requirement: 分源 Token 汇总

系统 SHALL 在单次 run 结束时按 source 汇总 prompt/completion/total tokens，写入 `token_usage_json`；同时保留 `analysis_job_logs` 批次明细。

#### Scenario: 批内 Token 分摊

- **当** 一批 LLM 返回 usage 且批内候选含多个 source
- **则** 必须按条数比例将 tokens 累加至各 source
- **且** run 级 `total` 必须等于各 source 之和（允许四舍五入误差 ≤1）

#### Scenario: Run API 暴露 Token

- **当** 调用 `GET /api/monitor/runs/{run_id}`
- **则** 响应必须含 `token_usage.by_source` 与 `timing_by_source`
- **且** 文档说明分摊策略

### Requirement: Run 历史 API 与 UI

系统 SHALL 提供 run 列表 API，并在监测任务 UI 展示 Run 历史；**任务详情 → 执行历史 Tab** MUST 为主入口之一。任务列表行内 MAY 保留展开摘要；选中 Run 后 Drawer MAY 仍可用，但不得与任务详情页互斥。

#### Scenario: 任务详情执行历史

- **WHEN** 用户在任务详情打开「执行历史」Tab
- **THEN** MUST 分页加载 `GET /api/monitor/tasks/{id}/runs`
- **且** 支持「加载更多」

### Requirement: 分析模式选择

系统 SHALL 支持 `analyze_mode=incremental`（默认）与 `analyze_mode=full_replace`；UI 必须区分「执行（增量）」与「全量重分析」；并 MUST 支持 crawl_only 与「增量 AI / 全量 AI」按钮组合（crawl_only 完成后引导 incremental reanalyze）。

#### Scenario: 增量执行

- **当** `POST /api/monitor/run` 未指定或 `analyze_mode=incremental`
- **则** 爬取增量 UPSERT raw
- **且** 分析仅处理待分析队列

#### Scenario: 全量重分析

- **当** `POST /api/monitor/reanalyze` 且 `analyze_mode=full_replace`
- **则** 必须先 `clear_intel_for_task`
- **且** 必须对全部 raw 调用 LLM 并覆盖写入 intel

#### Scenario: crawl_only 后增量 AI

- **WHEN** 最近一次 run 为 crawl_only 且 `analyze_deferred=true`
- **THEN** 任务 MUST `can_reanalyze=true`（有 raw 且非 busy）
- **AND** UI SHOULD 突出「待分析」与「增量 AI」入口

### Requirement: 监测任务 Modal 编辑

系统 SHALL 在监测任务 Tab 通过 Modal 创建与编辑任务；列表页 MUST 全宽，不得保留 split 右侧常驻表单。

#### Scenario: 创建任务 Modal

- **当** 用户点击「创建任务」
- **则** 必须在 Modal 中展示任务表单（含 schedule-picker）
- **且** 保存成功后 MUST 关闭 Modal 并刷新列表

#### Scenario: 编辑任务 Modal

- **当** 用户点击任务「编辑」
- **则** 必须在 Modal 中加载该任务数据
- **且** 运行中任务 MUST 禁用编辑

### Requirement: Stage2 多阶段 Run 进度

系统 SHALL 在 `crawl_mode=list_first` 的 run 中，progress JSON 必须反映四阶段：`list_crawl`、`list_triage`、`investigation_crawl`、`analyze`；crawl_only 成功结束时 MAY 使用 `crawl_done` 且 `analyze_pending=true`。

#### Scenario: 阶段切换

- **当** list_crawl 完成
- **则** progress.phase 必须变为 list_triage
- **且** stats_json 必须含 list_raw_new、list_raw_updated

#### Scenario: 勘察统计

- **当** investigation_crawl 结束
- **则** stats_json 必须含 investigation_queued、investigation_done、investigation_failed

#### Scenario: 初筛统计

- **当** list_triage 结束
- **则** stats_json 必须含 triage_high、triage_medium、triage_noise、needs_investigation_count

#### Scenario: crawl_only 完成进度

- **WHEN** crawl_only Run 爬取全部成功
- **THEN** task progress MUST 含 `phase=crawl_done` 与 `analyze_pending=true`
- **AND** MUST NOT 含 `phase=analyze`

### Requirement: Worker 与队列 Run 指标

系统 SHALL 在 monitor run stats 中记录 Worker、配额与诊断相关指标。

#### Scenario: 并行 crawl timing

- **当** heimao 与 xhs Worker 并行
- **则** stats MUST 含 `timing_by_source`
- **且** MAY 含 `worker_instances`（source、instance_id、status、diagnose_ok）

#### Scenario: investigation 配额 stats

- **当** xhs investigation 执行
- **则** MUST 含 `investigation_modal_done` 与 `investigation_skipped_quota`（若有）

#### Scenario: Cookie 诊断与 partial

- **当** 部分实例 diagnose 失败
- **则** MUST 含 `cookie_diagnose_failed` 计数
- **且** MAY 含 `sources_degraded` 或 run `status` 表达 partial success

#### Scenario: Run 详情展示

- **当** 用户查看 Run 详情
- **则** MUST 展示失败 instance、skip 配额、合并 Worker 日志入口

### Requirement: Run stats 字段标签

Run 历史与详情 UI 展示 stats 时 MUST 使用 `field_labels` 中文标签；新增 stats 键 MUST 同步注册。

#### Scenario: 新增字段标签

- **当** stats 含 `investigation_modal_done`、`investigation_skipped_quota`、`cookie_diagnose_failed`
- **则** field_labels MUST 提供中文名
- **且** Run 历史表头 MUST 使用 label

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

