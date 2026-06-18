# xhs-detail-modal Specification

## Purpose

小红书 Web 详情为搜索页内弹窗，非独立 explore 页。实现：`xhs_detail.py`，由 `crawl_xhs` 在 `fetch_detail=true` 时调用；investigation 由 `fetch_xhs_details_by_urls` 复用同一弹窗路径。

## Requirements

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

#### Scenario: 弹窗提取与关闭（勘察）

- **当** 弹窗打开成功
- **则** 必须按既有 `build_xhs_detail_modal_js` / `scroll_xhs_modal_content` / `close_xhs_note_modal` 执行
- **且** 提取后搜索页必须可用于下一条笔记

#### Scenario: 鉴权失败（勘察）

- **当** 弹窗详情被 `is_xhs_detail_auth_failure` 判定失败
- **则** 必须走 `login_gate` 等待登录后续跑
- **且** 不得 fallback 为 goto explore

### Requirement: 通过点击弹窗打开详情，禁止直接导航

#### Scenario: 避免 App 内打开拦截

- **当** 在小红书 Web 抓取笔记详情时
- **则** 系统必须在当前搜索/列表页通过 `open_xhs_note_modal` 点击笔记
- **且** 不得将新标签页 `goto(/explore/...)` 作为主要详情策略

#### Scenario: 弹窗已显示

- **当** 在 `detail_open_wait_ms` 内点击成功时
- **则** 提取前必须可见配置的弹窗根节点（`#noteContainer`、`.note-detail-mask` 等）

### Requirement: 在弹窗内提取内容

#### Scenario: 字段提取

- **当** 弹窗已打开时
- **则** `build_xhs_detail_modal_js` 必须仅在弹窗根节点内查询 title/content/author/time/likes/collects/comments/tags
- **且** 执行 evaluate 前必须通过 `scroll_xhs_modal_content` 滚动弹窗内容区

#### Scenario: 提取后关闭弹窗

- **当** 提取完成或失败时
- **则** `close_xhs_note_modal` 必须通过配置的关闭选择器或 Esc 关闭
- **且** 搜索页必须可用于下一条笔记

### Requirement: 识别 App 内打开提示

#### Scenario: App 引导文案

- **当** 页面正文包含配置的 `detail_app_open_texts`（如「App 内打开」）
- **且** 提取的正文短于阈值时
- **则** 必须将本次抓取视为失败并记录原因

#### Scenario: 勘察 App 墙失败

- **当** investigation 弹窗路径命中 App 引导且正文过短
- **则** investigation 队列项必须标记 `failed`
- **且** 不得写入有效 detail-phase payload

### Requirement: 可配置的选择器与等待时间

#### Scenario: 配置项

- **当** 运维人员调整抓取参数时
- **则** 以下项必须在 `config.xhs` 下可配置：
  - `detail_open_wait_ms`
  - `detail_modal_root_selectors`
  - `detail_modal_scroll_selectors`
  - `detail_modal_close_selectors`
  - `detail_app_open_texts`
  - `detail.*_selectors`（标题、正文、作者等）
  - `investigation_detail.*`（勘察 DOM miss 阈值、重搜滚动、详情间隔）

### Requirement: 列表预览仍来自搜索卡片

#### Scenario: 弹窗失败时保留列表字段

- **当** 弹窗抓取失败时
- **则** 来自 `.note-item` 的列表级字段（标题、点赞等）可以仍保留在结果中
- **且** 仅当弹窗提取成功时才覆盖详情字段

### Requirement: investigation 弹窗配额配置

系统 SHALL 在 `config.xhs.investigation_detail` 支持 `max_modal_per_run`（整数，0 表示不限制）；CrawlProfile API 白名单 MUST 包含该键。

#### Scenario: 默认与 profile 暴露

- **当** 未配置 `max_modal_per_run`
- **则** MUST 使用 `config.py` DEFAULT（建议 200 或 0=不限）
- **且** `GET /api/sources/xhs/profile` MUST 在 `investigation_detail` 对象中返回该键

#### Scenario: Worker 路径读取配额

- **当** xhs Worker 或 Orchestrator 执行 investigation
- **则** MUST 从 `config.xhs.investigation_detail.max_modal_per_run` 读取
- **且** 与现有 `dom_miss_skip`、`dom_miss_research_threshold` 等键共存

### Requirement: 配额与弹窗路径衔接

弹窗配额 MUST 在 `fetch_xhs_details_by_urls` / investigation Worker 路径生效；routine `crawl_xhs` MUST NOT 消耗配额。

#### Scenario: routine 不计入配额

- **当** xhs list_crawl routine 执行
- **则** MUST NOT 递增 `investigation_modal_done`

#### Scenario: 每条成功弹窗计 1

- **当** investigation 单 URL 弹窗提取成功
- **则** Run 级 `investigation_modal_done` MUST +1
- **且** 达到上限后后续 URL MUST skip（见 list-triage-investigation）

### Requirement: xhs Worker investigation 弹窗路径

系统 SHALL 在 investigation / `fetch_xhs_details_by_urls` 路径使用弹窗详情流程；禁止 goto explore 为主路径。investigation MUST 在 xhs Worker 进程内执行（Stage 3）。

#### Scenario: 勘察通过搜索页点击（Worker）

- **当** xhs Worker 处理 investigation URL
- **则** MUST 在 search_result 页定位 note-item 并 `fetch_xhs_detail_via_modal`
- **且** MUST NOT goto explore 为主路径

#### Scenario: 单条 DOM 未找到跳过（配额）

- **当** dom_miss_skip 且定位失败
- **则** MUST skip 该 URL；queue 项 failed；**不计入** modal 配额成功计数

#### Scenario: 配额 skip 不弹窗

- **当** Run 级配额已用尽
- **则** MUST NOT 打开弹窗；直接 mark skipped
