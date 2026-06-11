## MODIFIED Requirements

### Requirement: IntelRecord 统一交付 schema

系统 SHALL 将黑猫、小红书及未来源的分析结果统一写入 IntelRecord；每条 MUST 包含 `source` 字段供业务系统加权。`captured_at` MUST 表示原始数据入库时间（等于对应 `raw_records.created_at`）；`created_at` MUST 表示情报生成（AI 写入）时间，API MAY 以 `analyzed_at` 别名暴露。

#### Scenario: 必填字段

- **当** 写入 intel_records
- **则** 必须包含 `task_id`、`partner_id`、`source`、`url`、`title`、`relevance`、`captured_at`
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

### Requirement: 采集时间透传

系统 SHALL 在 `intel/runner.py` 构建 AI 候选时，将 `raw_records.created_at` 写入候选 `captured_at`，并在 `insert_intel_record` 中原样持久化。

#### Scenario: 监测任务流水线

- **当** MonitorRunner 从 raw_records 归一化并进入 AnalyzePipeline
- **则** 每条 intel 的 `captured_at` 必须等于其 `raw_record_id` 对应 raw 行的 `created_at`
- **且** 无 raw 关联的手工数据 MUST 文档说明 fallback 策略

#### Scenario: API 时间字段

- **当** 调用 `GET /api/intel/records`
- **则** 每条记录必须返回 `published_at`、`captured_at`、`analyzed_at`（或等价的 `created_at` 文档化别名）
- **且** 三者语义不得混用
