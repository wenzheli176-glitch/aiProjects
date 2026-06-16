# xhs-detail-modal

小红书 Web 详情为搜索页内弹窗，非独立 explore 页。实现：`xhs_detail.py`，由 `crawl_xhs` 在 `fetch_detail=true` 时调用；investigation 由 `fetch_xhs_details_by_urls` 复用同一弹窗路径。

### 需求：勘察阶段弹窗打开详情

系统 SHALL 在 investigation / `fetch_xhs_details_by_urls` 路径使用与 `crawl_xhs` 相同的弹窗详情流程；不得将 `page.goto(/explore/...)` 或新标签页直达笔记 URL 作为主要详情策略。

#### 场景：勘察通过搜索页点击

- **当** `XhsCrawlAdapter.crawl_investigation` 或 `fetch_xhs_details_by_urls` 处理队列 URL
- **则** 必须在 `search_result` 页面通过 `find_note_item_for_url` 定位 `.note-item`
- **且** 必须调用 `fetch_xhs_detail_via_modal(page, item, url)`
- **且** 不得对笔记 URL 执行 `page.goto` 作为主路径

#### 场景：URL 定位 note-item

- **当** 给定 explore 笔记 URL
- **则** `find_note_item_for_url` 必须从 URL 解析 note_id
- **且** 在当前搜索页 DOM 内匹配 `note_item_selector` 下含该 id 的链接
- **且** 返回可用于点击的 note-item 元素或明确失败

#### 场景：单条 DOM 未找到跳过

- **当** `dom_miss_skip=true` 且定位 note-item 失败
- **且** 未触发或重搜后仍失败
- **则** 必须跳过该 URL 的详情抓取
- **且** investigation 队列项必须标记 `failed`，`error_message` 含 `dom_not_found`
- **且** 必须继续处理队列中下一条 URL

#### 场景：批量 DOM 未找到触发重搜

- **当** 同一 keyword 批次内 DOM 未找到累计次数 ≥ `dom_miss_research_threshold`
- **则** 必须重新 `goto` 该 keyword 的 `search_result` URL
- **且** 必须执行配置的滚动加载（`research_max_scroll_rounds`）
- **且** 必须对当前 URL 再尝试一次 `find_note_item_for_url`
- **且** 日志必须记录重搜事件（含 keyword）

#### 场景：弹窗提取与关闭（勘察）

- **当** 弹窗打开成功
- **则** 必须按既有 `build_xhs_detail_modal_js` / `scroll_xhs_modal_content` / `close_xhs_note_modal` 执行
- **且** 提取后搜索页必须可用于下一条笔记

#### 场景：鉴权失败（勘察）

- **当** 弹窗详情被 `is_xhs_detail_auth_failure` 判定失败
- **则** 必须走 `login_gate` 等待登录后续跑
- **且** 不得 fallback 为 goto explore

### 需求：通过点击弹窗打开详情，禁止直接导航

#### 场景：避免 App 内打开拦截

- **当** 在小红书 Web 抓取笔记详情时
- **则** 系统必须在当前搜索/列表页通过 `open_xhs_note_modal` 点击笔记
- **且** 不得将新标签页 `goto(/explore/...)` 作为主要详情策略

#### 场景：弹窗已显示

- **当** 在 `detail_open_wait_ms` 内点击成功时
- **则** 提取前必须可见配置的弹窗根节点（`#noteContainer`、`.note-detail-mask` 等）

### 需求：在弹窗内提取内容

#### 场景：字段提取

- **当** 弹窗已打开时
- **则** `build_xhs_detail_modal_js` 必须仅在弹窗根节点内查询 title/content/author/time/likes/collects/comments/tags
- **且** 执行 evaluate 前必须通过 `scroll_xhs_modal_content` 滚动弹窗内容区

#### 场景：提取后关闭弹窗

- **当** 提取完成或失败时
- **则** `close_xhs_note_modal` 必须通过配置的关闭选择器或 Esc 关闭
- **且** 搜索页必须可用于下一条笔记

### 需求：识别 App 内打开提示

#### 场景：App 引导文案

- **当** 页面正文包含配置的 `detail_app_open_texts`（如「App 内打开」）
- **且** 提取的正文短于阈值时
- **则** 必须将本次抓取视为失败并记录原因

#### 场景：勘察 App 墙失败

- **当** investigation 弹窗路径命中 App 引导且正文过短
- **则** investigation 队列项必须标记 `failed`
- **且** 不得写入有效 detail-phase payload

### 需求：可配置的选择器与等待时间

#### 场景：配置项

- **当** 运维人员调整抓取参数时
- **则** 以下项必须在 `config.xhs` 下可配置：
  - `detail_open_wait_ms`
  - `detail_modal_root_selectors`
  - `detail_modal_scroll_selectors`
  - `detail_modal_close_selectors`
  - `detail_app_open_texts`
  - `detail.*_selectors`（标题、正文、作者等）
  - `investigation_detail.*`（勘察 DOM miss 阈值、重搜滚动、详情间隔）

### 需求：列表预览仍来自搜索卡片

#### 场景：弹窗失败时保留列表字段

- **当** 弹窗抓取失败时
- **则** 来自 `.note-item` 的列表级字段（标题、点赞等）可以仍保留在结果中
- **且** 仅当弹窗提取成功时才覆盖详情字段
