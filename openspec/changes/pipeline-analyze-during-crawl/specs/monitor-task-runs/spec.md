## ADDED Requirements

### Requirement: Analyze Drain 进度与统计

系统 SHALL 在 Run 的 `progress_json` 与 `stats_json` 中记录 during-crawl Analyze Drain 进度。

#### Scenario: progress 双指标

- **WHEN** Run crawl 阶段执行 Analyze Drain
- **THEN** `progress_json` MUST 含 `analyze_drain.done` 与 `analyze_drain.pending_detail`
- **AND** MUST 含 `analyze_drain.last_trigger`（batch|timer|manual）

#### Scenario: stats 耗时

- **WHEN** Run 结束
- **THEN** `stats_json` MUST 含 `analyze_during_crawl_ms` 与 `analyze_drained_count`

## MODIFIED Requirements

### Requirement: 分析模式选择

系统 SHALL 支持 `analyze_mode=incremental`（默认）与 `analyze_mode=full_replace`；UI 必须区分「执行（增量）」与「全量重分析」；并 MUST 支持 crawl_only 与「增量 AI / 全量 AI」按钮组合（crawl_only 完成后引导 incremental reanalyze）。

#### Scenario: 增量执行

- **当** `POST /api/monitor/run` 未指定或 `analyze_mode=incremental`
- **则** 爬取增量 UPSERT raw
- **且** 分析仅处理待分析队列
- **且** during-crawl Analyze Drain MAY 与爬取并行处理 detail-ready raw

#### Scenario: 全量重分析

- **当** `POST /api/monitor/reanalyze` 且 `analyze_mode=full_replace`
- **则** 必须先 `clear_intel_for_task`
- **且** 必须对全部 raw 调用 LLM 并覆盖写入 intel
- **且** MUST NOT 在 task `status=crawling` 时允许

#### Scenario: crawl_only 后增量 AI

- **WHEN** 最近一次 run 为 crawl_only 且 `analyze_deferred=true`
- **THEN** 任务 MUST `can_reanalyze=true`（有 raw 且非 busy）
- **AND** UI SHOULD 突出「待分析」与「增量 AI」入口

#### Scenario: crawling 中手动增量 AI

- **WHEN** task `status=crawling` 且存在 detail-ready 未分析 raw
- **AND** 用户 `POST /api/monitor/reanalyze` 且 `analyze_mode=incremental`
- **THEN** API MUST 允许执行（同 task）
- **AND** MUST 仅分析 detail-ready 候选
- **AND** MUST NOT 启动新的 crawl Run

#### Scenario: crawling 中禁止全量 AI

- **WHEN** task `status=crawling`
- **AND** `analyze_mode=full_replace`
- **THEN** API MUST 拒绝并返回明确错误

### Requirement: Stage2 多阶段 Run 进度

系统 SHALL 在 `crawl_mode=list_first` 的 run 中，progress JSON 必须反映四阶段：`list_crawl`、`list_triage`、`investigation_crawl`、`analyze`；crawl_only 成功结束时 MAY 使用 `crawl_done` 且 `analyze_pending=true`。

#### Scenario: 阶段切换

- **WHEN** Run 进入 investigation_crawl
- **THEN** progress `phase` MUST 反映 investigation
- **AND** during-crawl analyze drain 进行时 `analyze_drain` 子对象 MUST 更新（task status 可仍为 crawling）

#### Scenario: analyze 与 crawl 重叠

- **WHEN** Analyze Drain 在 crawling 态写入 intel
- **THEN** progress MUST 同时反映 investigation 与 analyze_drain 计数
- **AND** Run 收尾 analyze 补漏 MUST 仅处理剩余 pending
