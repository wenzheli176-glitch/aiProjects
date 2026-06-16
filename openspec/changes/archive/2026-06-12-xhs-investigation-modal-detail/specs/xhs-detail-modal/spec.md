## ADDED Requirements

### Requirement: 勘察阶段弹窗打开详情

系统 SHALL 在 investigation / `fetch_xhs_details_by_urls` 路径使用与 `crawl_xhs` 相同的弹窗详情流程；不得将 `page.goto(/explore/...)` 或新标签页直达笔记 URL 作为主要详情策略。

#### Scenario: 勘察通过搜索页点击

- **当** `XhsCrawlAdapter.crawl_investigation` 或 `fetch_xhs_details_by_urls` 处理队列 URL
- **则** 必须在 `search_result` 页面通过 `find_note_item_for_url` 定位 `.note-item`
- **且** 必须调用 `fetch_xhs_detail_via_modal(page, item, url)`
- **且** 不得对笔记 URL 执行 `page.goto` 作为主路径

#### Scenario: URL 定位 note-item

- **当** 给定 explore 笔记 URL
- **则** `find_note_item_for_url` 必须从 URL 解析 note_id
- **且** 在当前搜索页 DOM 内匹配 `note_item_selector` 下含该 id 的链接
- **且** 返回可用于点击的 note-item 元素或明确失败

#### Scenario: 单条 DOM 未找到跳过

- **当** `dom_miss_skip=true` 且定位 note-item 失败
- **且** 未触发或重搜后仍失败
- **则** 必须跳过该 URL 的详情抓取
- **且** investigation 队列项必须标记 `failed`，`error_message` 含 `dom_not_found`
- **且** 必须继续处理队列中下一条 URL

#### Scenario: 批量 DOM 未找到触发重搜

- **当** 同一 keyword 批次内 DOM 未找到累计次数 ≥ `dom_miss_research_threshold`
- **则** 必须重新 `goto` 该 keyword 的 `search_result` URL
- **且** 必须执行配置的滚动加载（`research_max_scroll_rounds`）
- **且** 必须对当前 URL 再尝试一次 `find_note_item_for_url`
- **且** 日志必须记录重搜事件（含 keyword）

#### Scenario: 弹窗提取与关闭

- **当** 弹窗打开成功
- **则** 必须按既有 `build_xhs_detail_modal_js` / `scroll_xhs_modal_content` / `close_xhs_note_modal` 执行
- **且** 提取后搜索页必须可用于下一条笔记

#### Scenario: 鉴权失败

- **当** 弹窗详情被 `is_xhs_detail_auth_failure` 判定失败
- **则** 必须走 `login_gate` 等待登录后续跑
- **且** 不得 fallback 为 goto explore

## MODIFIED Requirements

### Requirement: 识别 App 内打开提示

系统 SHALL 在手工 crawl 与 investigation 弹窗路径上识别 App 内打开引导文案；命中且正文过短时 MUST 视为抓取失败。

#### Scenario: App 引导文案

- **当** 页面正文包含配置的 `detail_app_open_texts`（如「App 内打开」）
- **且** 提取的正文短于阈值时
- **则** 必须将本次抓取视为失败并记录原因

#### Scenario: 勘察 App 墙失败

- **当** investigation 弹窗路径命中 App 引导且正文过短
- **则** investigation 队列项必须标记 `failed`
- **且** 不得写入有效 detail-phase payload
