## ADDED Requirements

### Requirement: ignore_before 分析过滤

系统 SHALL 在构建 AI 分析候选（`_build_candidates_from_raw`）时应用任务 `ignore_before`；爬取入库 MUST NOT 因该配置跳过 insert raw。

#### Scenario: 早于截止日跳过分析

- **WHEN** 任务 `ignore_before` 为有效日期且候选 `published_at` 非空
- **且** `published_at` 早于 `ignore_before`（日期字符串比较）
- **THEN** MUST NOT 将该 raw 送入 LLM
- **且** run stats SHOULD 记录跳过计数

#### Scenario: published_at 为空仍分析

- **WHEN** 候选 `published_at` 为空或缺失
- **THEN** MUST NOT 因 `ignore_before` 跳过
- **且** MUST 按既有增量/全量规则继续

#### Scenario: 未配置 ignore_before

- **WHEN** 任务无 `ignore_before` 或为空
- **THEN** 行为 MUST 与变更前一致

#### Scenario: 增量与全量均生效

- **WHEN** `analyze_mode` 为 `incremental` 或 `full_replace`
- **THEN** ignore_before 过滤 MUST 在送入 LLM 前应用
