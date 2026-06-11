## ADDED Requirements

### Requirement: PartnerMatcher 源无关匹配

系统 SHALL 在归一化之后、AI 分析之前，用 PartnerMatcher 将候选记录关联到 `partner_id`，匹配依据为主名称、别名与可选监测词。

#### Scenario: 别名命中

- **当** NormalizedRecord 的 title 或 body 包含某合作方别名
- **则** 必须设置 `partner_id` 与 `subject_hits` 包含该别名
- **且** 一条记录仅关联一个主 partner（多命中时取最长匹配或任务上下文优先）

#### Scenario: 无匹配仍保留

- **当** 规则层无法匹配任何 partner
- **则** 记录仍必须进入 AI 候选池（`partner_id` 可为空或 task 默认方）
- **且** 高召回策略下不得因未匹配而丢弃 raw 数据

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
- **则** 必须解析为 `relevance`、`risk_types`、`summary`、`subject_hits`
- **且** 必须写入 `intel_records` 并记录 `model` 与 `prompt_version`

#### Scenario: 分析失败可重试

- **当** 单批 API 调用失败
- **则** `analysis_jobs` 必须记录错误并支持有限次重试
- **且** 部分批失败时任务可标记 `done` 并附带 warnings（除非 strict 模式）

### Requirement: IntelRecord 统一交付 schema

系统 SHALL 将黑猫、小红书及未来源的分析结果统一写入 IntelRecord；每条 MUST 包含 `source` 字段供业务系统加权。

#### Scenario: 必填字段

- **当** 写入 intel_records
- **则** 必须包含 `task_id`、`partner_id`、`source`、`url`、`title`、`relevance`、`captured_at`
- **且** 必须包含 `schema_version` 便于 API 消费者版本化

#### Scenario: 高召回 relevance 语义

- **当** AI 判断主体与风险存疑
- **则** 必须标为 `medium` 或更高，不得标为 `noise`
- **且** 仅当明确与排查对象无关时才可标 `noise`

#### Scenario: export_tier 分桶

- **当** `relevance` 为 high 或 medium
- **则** 默认 `export_tier=include`
- **且** 不确定项必须可标 `export_tier=review` 而非直接 exclude

### Requirement: 去重与审计

系统 SHALL 为 IntelRecord 生成 `dedup_key`（如 source + external_id 或 url 归一化），并保留 AI 审计字段。

#### Scenario: URL 去重

- **当** 同一 task 内出现相同 `dedup_key`
- **则** 后写入记录必须标记 `is_duplicate=true` 或跳过写入（策略可配置）
- **且** 不得重复计数看板「新增信号」

#### Scenario: 可复现审计

- **当** 查询 intel_record
- **则** 必须返回 `prompt_version` 与 `model`
- **且** 可选返回 `raw_payload` 引用或 raw_records id

### Requirement: 云模型配置

系统 SHALL 从 `config.analysis` 读取 endpoint、model、api_key 环境变量名、prompt_version，支持切换 OpenAI-compatible 供应商。

#### Scenario: API Key 不落盘

- **当** 调用云模型
- **则** 必须从 `config.analysis.api_key_env` 指定环境变量读取密钥
- **且** 不得将密钥写入 SQLite 或日志明文

#### Scenario: Prompt 高召回指令

- **当** 构建 prompt
- **则** 必须包含合作方别名列表、source、title、body
- **且** 必须明确指令：主体存疑标 medium，仅明确无关标 noise
