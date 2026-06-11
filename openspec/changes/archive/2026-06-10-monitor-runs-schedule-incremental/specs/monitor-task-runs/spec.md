## ADDED Requirements

### Requirement: 任务执行 Run 记录

系统 SHALL 为每次 monitor_task 执行（手动或定时）创建 `monitor_task_runs` 记录，含 trigger、analyze_mode、status、started_at、finished_at、阶段耗时与统计 JSON。

#### Scenario: 手动执行创建 Run

- **当** 用户调用 `POST /api/monitor/run` 且任务未在运行
- **则** 必须创建 run 记录且 `trigger=manual`
- **且** 默认 `analyze_mode=incremental`

#### Scenario: Run 完成写入汇总

- **当** 爬取与分析阶段均结束（或失败/超时）
- **则** run 必须更新 `crawl_duration_ms`、`analyze_duration_ms`、`stats_json`
- **且** `monitor_tasks.last_run_id` 必须指向该 run

#### Scenario: 重叠执行跳过

- **当** 定时触发时 `S.running=true` 且 `skip_if_running=true`
- **则** 必须创建 `status=skipped_overlap` 的 run
- **且** 不得抢占当前运行中的任务

### Requirement: 分源爬取与分析时长

系统 SHALL 在单次 run 内按 `source_id` 汇总 wall-clock 爬取时长与分析时长，写入 `timing_by_source_json`。

#### Scenario: 分源爬取计时

- **当** `run_monitor_task` 对每个 source 调用 `CrawlAdapter.crawl`
- **则** 必须累计该 source 的 `crawl_ms`
- **且** 必须记录 `raw_new` 与 `raw_updated` 计数

#### Scenario: 分源分析计时

- **当** `analyze_candidates` 完成一批 LLM 调用
- **则** 必须按批内各 source 候选条数比例分摊该批 wall time 至 `analyze_ms`
- **且** 必须与 token 分摊使用相同 source 分组

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

系统 SHALL 提供 run 列表 API，并在监测任务 UI 展示最近 run 的时长、token、增量统计与失败原因。

#### Scenario: 列表查询

- **当** 调用 `GET /api/monitor/tasks/{task_id}/runs`
- **则** 必须按 `started_at` 降序分页返回
- **且** 每条含 status、trigger、duration、stats 摘要

#### Scenario: 任务列表展示最近 Run

- **当** 用户打开监测任务列表
- **则** 必须显示最近成功/失败 run 时间与总时长
- **且** 可展开查看分源表格

### Requirement: 分析模式选择

系统 SHALL 支持 `analyze_mode=incremental`（默认）与 `analyze_mode=full_replace`；UI 必须区分「执行（增量）」与「全量重分析」。

#### Scenario: 增量执行

- **当** `POST /api/monitor/run` 未指定或 `analyze_mode=incremental`
- **则** 爬取增量 UPSERT raw
- **且** 分析仅处理待分析队列

#### Scenario: 全量重分析

- **当** `POST /api/monitor/reanalyze` 且 `analyze_mode=full_replace`
- **则** 必须先 `clear_intel_for_task`
- **且** 必须对全部 raw 调用 LLM 并覆盖写入 intel
