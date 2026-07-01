## MODIFIED Requirements

### Requirement: ignore_before 分析过滤

系统 SHALL 在任务配置了 `ignore_before` 时，于 **列表入库**、**详情勘察** 与 **AI 分析** 三阶段跳过 `published_at` 早于截止日的内容；三阶段 MUST 共用同一 cutoff 解析（`resolve_ignore_before`）与同一日期比较规则（`should_skip_ignore_before`）。

#### Scenario: 早于截止日跳过分析

- **WHEN** 任务 `ignore_before` 为有效日期且候选 `published_at` 非空
- **且** `published_at` 早于 `ignore_before`（日期字符串比较）
- **THEN** MUST NOT 将该 raw 送入 LLM
- **且** run stats SHOULD 记录 `intel_skipped_ignore_before`

#### Scenario: 早于截止日跳过列表入库

- **WHEN** 列表爬取结果即将 `insert_raw_records`
- **且** 由 `_raw_published_at(source, record)` 解析出的日期早于 `ignore_before`
- **THEN** MUST NOT INSERT 该条 raw
- **且** run stats MUST 记录 `raw_skipped_ignore_before`
- **且** 终端日志 SHOULD 包含「忽略早于 … 跳过 N」

#### Scenario: 早于截止日跳过详情勘察

- **WHEN** `build_investigation_queue` 或 `row_needs_investigation` 评估某 raw
- **且** 归一化后 `published_at` 早于 `ignore_before`
- **THEN** MUST NOT 将该 raw 加入勘察队列
- **且** 日志 MAY 汇总跳过条数

#### Scenario: published_at 为空仍入库与仍分析

- **WHEN** 候选或 raw 的 `published_at` 为空或缺失
- **THEN** MUST NOT 因 `ignore_before` 跳过列表入库、勘察或分析
- **且** MUST 按既有增量/全量规则继续

#### Scenario: 未配置 ignore_before

- **WHEN** 任务无 `ignore_before` 或为空
- **THEN** 行为 MUST 与变更前一致

#### Scenario: 增量与全量均生效

- **WHEN** `analyze_mode` 为 `incremental` 或 `full_replace`
- **THEN** ignore_before 过滤 MUST 在送入 LLM 前应用

#### Scenario: business_spec 合并

- **WHEN** 同时存在 task.business_spec 与 partner business_spec
- **THEN** `resolve_ignore_before` MUST merge 后取非空 `ignore_before`
- **且** 空 dict MUST NOT 覆盖任务级已配置 cutoff
