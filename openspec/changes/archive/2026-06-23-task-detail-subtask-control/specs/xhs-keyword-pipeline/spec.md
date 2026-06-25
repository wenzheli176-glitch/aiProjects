## ADDED Requirements

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
