## ADDED Requirements

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

## MODIFIED Requirements

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
