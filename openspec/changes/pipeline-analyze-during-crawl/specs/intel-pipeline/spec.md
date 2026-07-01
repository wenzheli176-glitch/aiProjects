## ADDED Requirements

### Requirement: Analyze Drain during crawl

系统 SHALL 在监测 Run 的 crawl 阶段（含 investigation）对 **detail-ready** 且 incremental 规则下待分析的 raw 执行 Analyze Drain；MUST 与 Chrome Worker 生命周期分离（HTTP LLM only）。

#### Scenario: investigation 批完成触发 drain

- **WHEN** `process_investigation_batch` 成功处理一批且 `monitor.analyze_during_crawl=true`
- **AND** Run 非 crawl_only
- **THEN** MUST 调用 `drain_analyze_ready`（trigger=batch）
- **AND** MUST 仅分析 `crawl_phase=detail` 候选

#### Scenario: 定时兜底 drain

- **WHEN** Run crawl 进行中且距上次 drain 超过 `monitor.analyze_drain_interval_sec`
- **AND** 存在 detail-ready 待分析 raw
- **THEN** MUST 调用 `drain_analyze_ready`（trigger=timer）
- **AND** MUST 覆盖 investigation 失败或批完成 drain 遗漏的 raw

#### Scenario: list 阶段不得自动 drain

- **WHEN** raw 的 `crawl_phase=list`
- **THEN** Analyze Drain MUST NOT 将其纳入候选
- **AND** 即使 list_triage 为 high/medium 也不得 during-crawl 分析

#### Scenario: 增量去重

- **WHEN** raw 已有 intel 且 `raw.updated_at <= intel.created_at`
- **THEN** drain MUST 跳过该 raw
- **WHEN** investigation 更新 raw 后 `raw.updated_at > intel.created_at`
- **THEN** drain MUST 重新分析（replace_intel）

#### Scenario: Run 收尾补漏

- **WHEN** crawl 阶段全部完成且 Run 非 crawl_only
- **THEN** `_run_analysis_phase` MUST 仅处理 drain 后仍 pending 的 detail-ready raw
- **AND** MUST NOT 重复全量扫描已分析 raw

#### Scenario: crawl_only 不自动 drain

- **WHEN** Run `crawl_only=true`
- **THEN** MUST NOT 执行 batch/timer 自动 drain
- **AND** 收尾 MUST NOT 调用 `_run_analysis_phase`

#### Scenario: analyze_during_crawl 关闭

- **WHEN** `monitor.analyze_during_crawl=false`
- **THEN** MUST 保持现网串行：crawl 全部完成后再 `_run_analysis_phase`

### Requirement: Run 内 analyze 执行锁

系统 SHALL 对同一 `run_id` 的 Analyze Drain 与 crawl 中 incremental reanalyze 互斥执行，防止双路重复 LLM。

#### Scenario: 并发 drain 请求

- **WHEN** batch drain 与 timer drain 同时触发
- **THEN** 后者 MUST 等待或跳过（仅一个 analyze 执行者）

#### Scenario: 手动 incremental 与自动 drain

- **WHEN** 用户于 crawling 态触发 incremental reanalyze
- **THEN** MUST 与 Run 内 analyze 锁协调
- **AND** MUST 使用相同 detail-only 候选构建逻辑

## MODIFIED Requirements

### Requirement: 分级 AnalyzePipeline

系统 SHALL 区分 List Triage（轻量）、Routine Analyze（可选）、Investigation Analyze（完整）三档 LLM 调用。

#### Scenario: Routine 跳过完整 LLM

- **当** raw 仅 list-phase 且 triage_relevance=noise
- **则** 不得调用完整 AnalyzePipeline
- **且** 可仅持久化 triage 结果或写轻量 intel 行（可配置）

#### Scenario: Investigation 必须完整分析

- **当** raw crawl_phase=detail 且来自 investigation 队列
- **则** 必须调用完整 AnalyzePipeline
- **且** 必须写入标准 intel_records
- **且** MAY 在 investigation 批完成后通过 Analyze Drain 立即执行（不必等 Run 收尾）

#### Scenario: During-crawl drain 仅 detail

- **WHEN** Analyze Drain during crawl 执行
- **THEN** MUST 等同 Investigation Analyze 完整管道
- **AND** MUST NOT 包含 crawl_phase=list 的 raw

### Requirement: investigation skip 后 analyze

AnalyzePipeline MUST 对 quota skip 的 xhs raw 仍可按 list_triage 结果分析（partial body）。

#### Scenario: skip 后仍写 intel

- **当** raw 仅 list phase 且 investigation 被 quota skip
- **且** list_triage 非 noise
- **则** analyze MUST 仍可处理该 raw（不要求 crawl_phase=detail）
- **且** during-crawl Analyze Drain MUST NOT 处理该 raw
- **且** Run 收尾补漏阶段 MUST 仍可处理该 raw
