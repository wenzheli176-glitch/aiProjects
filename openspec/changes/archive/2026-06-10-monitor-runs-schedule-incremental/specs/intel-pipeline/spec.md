## ADDED Requirements

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
