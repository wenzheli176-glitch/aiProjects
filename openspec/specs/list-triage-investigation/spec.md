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
- **且** 非 heimao legacy 已 fetch_detail 情形
- **则** 必须加入 investigation_queue

#### Scenario: 勘察补详情

- **当** 执行 investigation_crawl（经 Worker queue）
- **则** CrawlAdapter 必须仅对队列 URL 抓详情
- **且** 必须更新同 dedup_key raw，设置 `crawl_phase=detail`
- **且** 黑猫走 login_gate + new_page；小红书走搜索页弹窗（禁止 goto explore）
- **且** xhs 弹窗 MUST 受 Run 级 `max_modal_per_run` 约束

#### Scenario: 勘察后深分析

- **当** investigation_crawl 成功更新 raw
- **则** 必须送入完整 AnalyzePipeline

#### Scenario: 勘察失败状态

- **当** xhs 弹窗失败
- **则** queue 项为 `failed`；统计 `investigation_failed`；Run 仍可 analyze

#### Scenario: 配额 skip 后 analyze

- **当** xhs 项因 quota skip
- **则** raw MUST 仍可按 list_triage 结果进入 analyze（partial body）
- **且** Run MUST NOT failed

#### Scenario: 配额 skip 状态

- **当** xhs 弹窗因 `modal_quota_exceeded` 被 skip
- **则** investigation_queue 对应项 MUST 为 `skipped`
- **且** MUST 计入 `investigation_skipped_quota`

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

### Requirement: xhs investigation 弹窗配额（Run 级）

系统 SHALL 支持 `xhs.investigation_detail.max_modal_per_run`；单次 Run 内所有 xhs Worker 实例 **共享**同一配额计数器。

#### Scenario: 配额内正常勘察

- **当** 弹窗成功且 Run 级 `investigation_modal_done < max_modal_per_run`
- **则** MUST 递增 Run 级计数并继续（Orchestrator 或 DB 原子更新）

#### Scenario: 配额超限 skip

- **当** Run 级计数已达上限且队列仍有 pending xhs 项
- **则** MUST skip 剩余项，reason `modal_quota_exceeded`
- **且** MUST 写入 `investigation_skipped_quota`
- **且** MUST NOT 将整个 Run 标记为 failed

#### Scenario: 多 xhs 实例不倍增配额

- **当** 配置 2 个 xhs Worker 实例且 `max_modal_per_run=200`
- **则** 全 Run 弹窗总数 MUST NOT 超过 200（非每实例 200）

### Requirement: list_triage 作用范围

list_triage MUST 仅处理 list_first 源的 list-phase raw。

#### Scenario: 仅 triage xhs list raw

- **当** Run 含 heimao legacy 与 xhs list
- **则** `run_list_triage` MUST 仅传入 `crawl_phase=list` 的 raw
- **且** heimao `crawl_phase=legacy` raw MUST NOT 进入 list_triage

### Requirement: heimao legacy 免重复 investigation

系统 SHALL 避免 heimao routine 已 fetch_detail 的 raw 再次进入 investigation。

#### Scenario: heimao fetch_detail 已抓详情

- **当** heimao legacy routine 且 task.fetch_detail=true
- **且** raw payload 已含有效详情 body
- **则** `build_investigation_queue` MUST NOT 将该 raw 入队

#### Scenario: heimao 无 triage 不入队

- **当** raw 无 `list_triage.triage_relevance`
- **则** MUST NOT 进入 investigation_queue

