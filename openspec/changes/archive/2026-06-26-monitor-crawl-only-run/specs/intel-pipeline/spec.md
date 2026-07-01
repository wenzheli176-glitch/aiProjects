## ADDED Requirements

### Requirement: crawl_only 跳过 AnalyzePipeline

系统 SHALL 在 `run_monitor_task(crawl_only=True)` 路径下，爬取与 list_triage、investigation 完成后 MUST NOT 调用 `analyze_candidates`；list_triage MUST 仍在爬取阶段内执行（含 xhs keyword 流水线）。

#### Scenario: list_triage 仍执行

- **WHEN** crawl_only Run 处理 xhs keyword 或 heimao list_first barrier 后 triage
- **THEN** MUST 照常调用 `run_list_triage`
- **AND** MUST NOT 因 crawl_only 跳过 triage 或 investigation

#### Scenario: 跳过最终 analyze

- **WHEN** crawl_only Run 全部 crawl 队列与 post-list 阶段完成
- **THEN** MUST NOT 调用 `_run_analysis_phase`
- **AND** MUST NOT 创建 analysis_job 用于本次 run 的最终匹配（reanalyze 路径除外）

#### Scenario: 待分析候选统计

- **WHEN** crawl_only Run 即将结束
- **THEN** MUST 使用与 `_build_candidates_from_raw` 相同过滤规则统计 `pending_analyze_raw_count` 写入 stats
- **AND** MUST NOT 写入新 intel_records

## MODIFIED Requirements

### Requirement: AnalyzePipeline 异步批处理

系统 SHALL 在爬取与归一化完成后，通过异步 AnalyzePipeline 调用云模型（OpenAI-compatible），与 CDP 爬取线程解耦；crawl_only Run MUST 豁免本要求。

#### Scenario: 爬取完成后触发分析

- **当** MonitorTask 爬取阶段结束且存在 normalized 候选且 `crawl_only=false`
- **则** 任务状态必须变为 `analyzing`
- **且** AnalyzePipeline 必须在后台线程或 job 中批量调用模型，不得阻塞爬取循环内的逐条 HTTP

#### Scenario: crawl_only 不触发分析

- **WHEN** MonitorTask 爬取阶段结束且 `crawl_only=true`
- **THEN** MUST NOT 将任务状态设为 `analyzing`
- **AND** MUST NOT 启动 AnalyzePipeline
