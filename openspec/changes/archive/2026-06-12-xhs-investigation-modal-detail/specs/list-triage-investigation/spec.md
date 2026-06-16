## MODIFIED Requirements

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

## ADDED Requirements

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
