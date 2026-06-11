# intel-pipeline Specification

## Purpose
TBD - created by archiving change partner-risk-intel. Update Purpose after archive.
## Requirements
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

### Requirement: MonitorTask 任务超时

系统 SHALL 在 `run_monitor_task` 执行期间读取 `config.monitor.task_timeout_sec`（默认 7200），自任务开始起按 wall-clock 计时；超时后 MUST 停止爬取与分析并释放全局运行锁。

#### Scenario: 爬取阶段超时

- **当** 监测任务处于 `crawling` 且 elapsed ≥ `task_timeout_sec`
- **则** 必须将 `S.running` 置为 false 以中断 `crawl_heimao` / `crawl_xhs` 循环
- **且** 任务状态必须更新为 `failed`，`error_message` 必须包含 `任务超时` 与配置秒数

#### Scenario: 分析阶段超时

- **当** 监测任务处于 `analyzing` 且 elapsed ≥ `task_timeout_sec`
- **则** 必须在下一批 AI 调用前停止分析
- **且** 任务状态必须更新为 `failed`，已写入的 `intel_records` 必须保留

#### Scenario: 重跑 AI 不受监测超时约束

- **当** 调用 `reanalyze_monitor_task` 且不存在 CDP 爬取
- **则** 不得应用 `monitor.task_timeout_sec` 中断逻辑

#### Scenario: 超时进度可观测

- **当** 因超时失败
- **则** `monitor_tasks.progress` JSON 必须包含 `reason=timeout` 或等价字段
- **且** 终端日志必须输出 `[monitor] 任务超时` 类信息

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

### Requirement: Raw 记录 UPSERT 与内容哈希

系统 SHALL 在 `insert_raw_records` 中对同 task 内相同 dedup key 执行 UPSERT：content 不变则跳过，变化则更新 `payload_json`、`content_hash`、`updated_at`。

#### Scenario: 新 URL 插入

- **当** 爬取结果 dedup key 在该 task 内不存在
- **则** 必须 INSERT raw_records
- **且** 必须写入 `content_hash` 与 `dedup_key`

#### Scenario: 相同内容跳过

- **当** dedup key 已存在且 `content_hash` 相同
- **则** 不得 INSERT 或 UPDATE
- **且** run stats 必须计为 raw_unchanged

#### Scenario: Payload 更新

- **当** dedup key 已存在且 `content_hash` 不同
- **则** 必须 UPDATE payload 与 `updated_at`
- **且** 不得删除原 raw id（保持 raw_record_id 稳定）

### Requirement: 增量分析队列

系统 SHALL 在 `analyze_mode=incremental` 时，仅对满足以下条件的 raw 构建 AI 候选：尚无对应非 duplicate intel，或 raw.updated_at 晚于 intel 生成时间。

#### Scenario: 新 Raw 待分析

- **当** raw 无关联 intel_records（raw_record_id 或 dedup_key）
- **则** 必须进入分析队列
- **且** 必须调用 LLM

#### Scenario: 已分析且未更新跳过 LLM

- **当** raw 有 intel 且 raw.updated_at 不晚于 intel.analyzed_at
- **则** 不得将该 raw 送入 LLM
- **且** run stats 计为 intel_skipped

#### Scenario: Payload 更新自动重分析

- **当** raw.updated_at 晚于既有 intel.analyzed_at
- **则** 必须将该 raw 送入 LLM
- **且** 写入前必须 DELETE 同 task 同 dedup_key 的旧 intel（覆盖写）

### Requirement: 全量覆盖重分析

系统 SHALL 在 `analyze_mode=full_replace` 时清除 task 全部 intel 后对全部 raw 执行 LLM 分析。

#### Scenario: 清除后全量

- **当** 用户选择全量重分析
- **则** 必须先 `clear_intel_for_task(task_id)`
- **且** 必须对全部 raw 重新 INSERT intel（非 UPSERT 保留旧 id）

#### Scenario: 重跑 AI 不受监测超时

- **当** 仅重分析且无 CDP 爬取
- **则** 仍不得应用 monitor.task_timeout_sec 中断（与现有 spec 一致）
- **且** 必须创建独立 run 记录

### Requirement: Analysis Job 关联 Run

系统 SHALL 在 `analysis_jobs` 记录 `run_id`，关联到本次 monitor_task_run。

#### Scenario: 创建 Job 带 Run

- **当** `_run_analysis_phase` 创建 analysis_job
- **则** 必须写入当前 run_id
- **且** analysis_job_logs 必须可通过 run_id 聚合

