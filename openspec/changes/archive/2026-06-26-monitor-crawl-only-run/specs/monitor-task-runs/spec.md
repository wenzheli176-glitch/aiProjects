## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: Stage2 多阶段 Run 进度

系统 SHALL 在 `crawl_mode=list_first` 的 run 中，progress JSON 必须反映阶段：`list_crawl`、`list_triage`、`investigation_crawl`、`analyze`；crawl_only 成功结束时 MAY 使用 `crawl_done` 且 `analyze_pending=true`。

#### Scenario: crawl_only 完成进度

- **WHEN** crawl_only Run 爬取全部成功
- **THEN** task progress MUST 含 `phase=crawl_done` 与 `analyze_pending=true`
- **AND** MUST NOT 含 `phase=analyze`

### Requirement: 分析模式选择

系统 SHALL 支持 `analyze_mode=incremental`（默认）与 `analyze_mode=full_replace`；UI 必须区分「执行（增量）」与「全量重分析」；并 MUST 支持 crawl_only 与「增量 AI / 全量 AI」按钮组合（crawl_only 完成后引导 incremental reanalyze）。

#### Scenario: crawl_only 后增量 AI

- **WHEN** 最近一次 run 为 crawl_only 且 `analyze_deferred=true`
- **THEN** 任务 MUST `can_reanalyze=true`（有 raw 且非 busy）
- **AND** UI SHOULD 突出「待分析」与「增量 AI」入口
