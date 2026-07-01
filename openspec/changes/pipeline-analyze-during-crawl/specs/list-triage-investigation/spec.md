## ADDED Requirements

### Requirement: investigation 批完成 analyze 钩子

系统 SHALL 在 investigation 工作项批处理完成后通知 Analyze Drain（当 `monitor.analyze_during_crawl=true`）。

#### Scenario: heimao Worker 批完成

- **WHEN** Worker 执行 `phase=investigation` 且 `process_investigation_batch` 返回
- **THEN** MUST 触发 `drain_analyze_ready`（trigger=batch）
- **AND** MUST 在 `sync_task_subtask_progress` 之前或之后更新 analyze_drain 计数

#### Scenario: 单进程 investigation 批完成

- **WHEN** `run_investigation_crawl` 完成一个 batch_size  chunk
- **THEN** MUST 同样触发 batch drain

#### Scenario: xhs keyword 同页勘察批完成

- **WHEN** `run_xhs_keyword_pipeline` 完成同页 investigation 子集
- **THEN** MUST 对 resulting detail raw 触发 batch drain

#### Scenario: investigation 批失败

- **WHEN** 批内全部 failed 且无 raw 变为 detail
- **THEN** batch drain MAY no-op
- **AND** timer drain MUST 在 interval 内兜底扫描其他已 detail 的 raw
