## MODIFIED Requirements

### Requirement: AnalyzePipeline 异步批处理

系统 SHALL 在爬取与归一化完成后，通过异步 AnalyzePipeline 调用云模型（OpenAI-compatible），与 CDP 爬取线程解耦。

#### Scenario: 爬取完成后触发分析

- **当** MonitorTask 爬取阶段结束且存在 normalized 候选
- **则** 任务状态必须变为 `analyzing`
- **且** AnalyzePipeline 必须在后台线程或 job 中批量调用模型，不得阻塞爬取循环内的逐条 HTTP

#### Scenario: 批处理与截断

- **当** 执行 AI 打标
- **则** 必须按 `config.analysis.batch_size` 分批
- **且** 每条 `body` 超过 `max_body_chars` 时必须截断后再发送

#### Scenario: 结构化 JSON 输出

- **当** 模型返回成功
- **则** 必须解析为 `relevance`、`confidence`、`risk_types`、`summary`、`subject_hits`、`sentiment`、`sentiment_score`
- **且** `confidence` MUST 为 0.0~1.0 浮点数（LLM 自报）
- **且** 必须写入 `intel_records` 并记录 `model` 与 `prompt_version`

#### Scenario: 分析输入含发布时间

- **当** 构建 LLM 批次
- **则** 每条输入 MUST 包含 `published_at`（`YYYY-MM-DD` 或空）与 `captured_at`
- **且** prompt MUST 指导模型结合发布时间评估风险时效与 confidence

#### Scenario: 分析失败可重试

- **当** 单批 API 调用失败
- **则** `analysis_jobs` 必须记录错误并支持有限次重试
- **且** 部分批失败时任务可标记 `done` 并附带 warnings（除非 strict 模式）

### Requirement: IntelRecord 统一交付 schema

系统 SHALL 将黑猫、小红书及未来源的分析结果统一写入 IntelRecord；每条 MUST 包含 `source` 字段供业务系统加权。`captured_at` MUST 表示原始数据入库时间（等于对应 `raw_records.created_at`）；`created_at` MUST 表示情报生成（AI 写入）时间，API MAY 以 `analyzed_at` 别名暴露。

#### Scenario: 必填字段

- **当** 写入 intel_records
- **则** 必须包含 `task_id`、`partner_id`、`source`、`url`、`title`、`relevance`、`confidence`、`captured_at`
- **且** 必须包含 `schema_version` 便于 API 消费者版本化
- **且** `captured_at` 必须来自关联 raw_record 的 `created_at`，不得使用 AI 写入时刻

#### Scenario: 高召回 relevance 语义

- **当** AI 判断主体与风险存疑
- **则** 必须标为 `medium` 或更高，不得标为 `noise`
- **且** 仅当明确与排查对象无关时才可标 `noise`

#### Scenario: export_tier 分桶

- **当** `relevance` 为 high 或 medium
- **则** 默认 `export_tier=include`
- **且** 不确定项必须可标 `export_tier=review` 而非直接 exclude

## ADDED Requirements

### Requirement: Recency 后处理降档 relevance

系统 SHALL 在 LLM 返回 relevance 后应用确定性 recency 后处理，写入最终 `relevance`；MUST 保留 LLM 原始档位于 `extra.relevance_llm`（或等价字段）。

#### Scenario: 30 天降 high

- **当** `analysis.recency.enabled=true`
- **且** `published_at` 可解析且距 `captured_at` 超过 `downgrade_days_high_to_medium`（默认 30）天
- **且** LLM 输出 `relevance=high`
- **则** 最终 `relevance` MUST 为 `medium`

#### Scenario: 90 天降 medium

- **当** `published_at` 可解析且 age 超过 `downgrade_days_medium_to_low`（默认 90）天
- **且** LLM 输出 `relevance=medium`（或已被上一步降为 medium 的 high）
- **则** 最终 `relevance` MUST 为 `low`

#### Scenario: 低 confidence 降档

- **当** LLM `confidence` 低于 `confidence_downgrade_threshold`（默认 0.4）
- **且** 当前 relevance 不为 `noise`
- **则** MUST 降一档（high→medium→low→low）

#### Scenario: 无 published_at 不降 age 档

- **当** `published_at` 为空
- **则** MUST NOT 因 age 规则降档
- **且** LLM 仍 MAY 输出 `relevance=high`
