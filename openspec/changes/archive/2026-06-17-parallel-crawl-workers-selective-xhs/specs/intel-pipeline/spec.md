## ADDED Requirements

### Requirement: 分析批并行度

系统 SHALL 支持 `analysis.parallel_batches`（默认 5）；AnalyzePipeline 批 LLM 调用 MUST 使用该并发度；与 Crawl Worker 生命周期分离。

#### Scenario: 默认并行 5

- **当** 未配置 parallel_batches
- **则** MUST 默认 5

#### Scenario: 线程安全累加

- **当** 多批并行完成
- **则** run_metrics token/stats MUST 正确累加（加锁）

#### Scenario: 单批失败不阻塞他批

- **当** 某批 LLM 最终失败
- **则** MUST 跳过该批并继续其他批（与现网串行行为一致）
- **且** MUST 记录 failed_batches

### Requirement: investigation skip 后 analyze

AnalyzePipeline MUST 对 quota skip 的 xhs raw 仍可按 list_triage 结果分析（partial body）。

#### Scenario: skip 后仍写 intel

- **当** raw 仅 list phase 且 investigation 被 quota skip
- **且** list_triage 非 noise
- **则** analyze MUST 仍可处理该 raw（不要求 crawl_phase=detail）
