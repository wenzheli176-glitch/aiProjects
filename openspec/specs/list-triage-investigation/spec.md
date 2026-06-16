# list-triage-investigation Specification

## Purpose
TBD - created by archiving change crawl-scale-stage2. Update Purpose after archive.
## Requirements
### Requirement: 列表 LLM 初筛

系统 SHALL 在 list_crawl 完成后，对新增或 content 变更的 list-phase raw 执行 List Triage：轻量 LLM 批处理，输入以 title + 列表 snippet 为主。

#### Scenario: 初筛输出字段

- **当** List Triage 成功
- **则** 必须写入 `triage_relevance`（high|medium|low|noise）
- **且** 必须写入 `triage_risk_hint`（none|elevated|severe）
- **且** 必须写入 `needs_investigation` 布尔值

#### Scenario: 初筛结果持久化

- **当** Triage 完成
- **则** 结果必须写入 raw_records 的 `list_triage_json` 或等价列
- **且** 不得覆盖 payload_json 中的原始列表字段

#### Scenario: 配置截断

- **当** 执行 List Triage
- **则** 必须遵守 `config.analysis.list_triage.batch_size` 与 `max_body_chars`
- **且** body 为空时仍必须可发起 triage

### Requirement: 勘察队列与增量重点详情

系统 SHALL 将满足阈值且为增量的条目加入 investigation 队列，并仅对队列 URL 执行 `fetch_detail=true` 补爬。

#### Scenario: 进入勘察队列条件

- **当** `needs_investigation=true`
- **且** `triage_relevance` 为 medium 或 high（或 P0 合作方规则强制）
- **且** raw 尚无 detail-phase payload 或 content_hash 已变更
- **则** 必须加入 investigation_queue

#### Scenario: 勘察补详情

- **当** 执行 investigation_crawl
- **则** CrawlAdapter 必须仅对队列 URL 抓详情
- **且** 必须更新同 dedup_key raw 的 payload，设置 `crawl_phase=detail`
- **且** 黑猫必须走现有 login_gate 与 new_page 详情
- **且** 小红书必须走搜索页弹窗详情（禁止 goto explore）；单条 DOM 未找到可 skip；同 keyword 批量 miss 达阈值必须重搜

#### Scenario: 勘察后深分析

- **当** investigation_crawl 成功更新 raw
- **则** 必须将该 raw 送入完整 AnalyzePipeline（非 list_triage 轻量 prompt）
- **且** analyze 必须使用勘察后的完整 body（若仍缺字段则允许 partial）

#### Scenario: 勘察失败状态

- **当** xhs 弹窗失败（含 dom_not_found、App 墙、鉴权超时）
- **则** investigation_queue 对应项必须更新为 `failed` 并记录 `error_message`
- **且** run stats 可统计 `investigation_failed` 增量
- **且** 任务整体仍可进入 analyze 阶段（处理已成功勘察的 raw）

### Requirement: 勘察 keyword 上下文

系统 SHALL 在 xhs investigation 执行时携带 list crawl 阶段的搜索 keyword，用于打开正确的 search_result 页与批量重搜。

#### Scenario: 从 raw 读取 keyword

- **当** investigation 处理 xhs 队列项
- **则** 必须优先使用 raw payload 的 `_search_keyword` 或 raw.keyword
- **且** 同一 keyword 的 URL 应在同一搜索页会话内批量处理

#### Scenario: 缺少 keyword

- **当** raw 无 keyword 且 URL 无法在当前页定位
- **则** 必须标记 `failed`（原因含 `dom_not_found` 或 `missing_keyword`）
- **且** 不得 goto explore URL 兜底

### Requirement: 高相关高风险优先

系统 SHALL 对 triage 同时为 high relevance 与 severe risk_hint 的增量条目优先入队并优先执行 investigation。

#### Scenario: 队列排序

- **当** investigation 队列非空
- **则** 必须按 P0 合作方关联 > triage_risk_hint severe > triage_relevance high > captured_at 排序

#### Scenario: P0 别名强制勘察

- **当** list raw 的 title/snippet 命中 P0 合作方别名
- **则** 即使 triage 为 medium，也必须设置 `needs_investigation=true`

