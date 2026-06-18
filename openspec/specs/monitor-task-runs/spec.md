# monitor-task-runs Specification

## Purpose
TBD - created by archiving change monitor-runs-schedule-incremental. Update Purpose after archive.
## Requirements
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

系统 SHALL 提供 run 列表 API，并在监测任务 UI 以主从布局展示 Run 历史：任务列表行内可展开摘要表，选中 Run 后在 **Drawer** 展示完整耗时、Token、统计与失败原因；默认加载最近 5 条，并支持加载更多或分页查看全部历史。

#### Scenario: 列表查询

- **当** 调用 `GET /api/monitor/tasks/{task_id}/runs`
- **则** 必须按 `started_at` 降序分页返回
- **且** 响应必须含 `total`、`page`、`limit` 与每条 run 的 status、trigger、analyze_mode、duration、stats 摘要

#### Scenario: 行内展开 Run 摘要

- **当** 用户在监测任务列表点击某任务的「历史」或等效控件
- **则** 必须在该任务行下方展开/收起 Run 摘要表
- **且** 首次展开必须请求 `page=1&limit=5`
- **且** 摘要表必须含 run id、开始/结束时间、trigger、analyze_mode、status、总耗时、raw/intel 统计摘要
- **且** 不得使用 `alert()` 展示 Run 历史

#### Scenario: 加载更多或分页

- **当** 该任务 Run 总数 `total` 大于已加载条数
- **则** UI 必须提供「加载更多」或分页控件以获取后续页
- **且** 加载更多必须递增 `page` 并追加展示（不替换已加载的较新记录）

#### Scenario: Run 详情 Drawer

- **当** 用户在 Run 摘要表中点击某一条 Run
- **则** 必须从右侧 Drawer 展示 Run 详情（不得占用任务编辑侧栏 form-box）
- **且** 必须调用 `GET /api/monitor/runs/{run_id}` 展示：`stats` 全量字段、分源 `timing_by_source` 表、分源 `token_usage` 表（含 total 合计）、`error_message`
- **且** stats 六项 MUST 展示中文 label 与一行含义说明（常显，非仅折叠 glossary）
- **且** 必须含可折叠字段说明（glossary）作为补充
- **且** URL MAY 含 `run_id` 以深链打开 Drawer

#### Scenario: 任务列表展示最近 Run

- **当** 用户打开监测任务列表
- **则** 「最近执行」列必须显示最近 run 时间与总时长（沿用现有 `last_run`）
- **且** 完整分源明细仅在 Run Drawer 展示（不在主表列内嵌）

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

系统 SHALL 在 `crawl_mode=list_first` 的 run 中，progress JSON 必须反映四阶段：`list_crawl`、`list_triage`、`investigation_crawl`、`analyze`。

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

