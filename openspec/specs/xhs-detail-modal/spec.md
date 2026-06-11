# xhs-detail-modal

小红书 Web 详情为搜索页内弹窗，非独立 explore 页。实现：`xhs_detail.py`，由 `crawl_xhs` 在 `fetch_detail=true` 时调用。

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

### 需求：列表预览仍来自搜索卡片

#### 场景：弹窗失败时保留列表字段

- **当** 弹窗抓取失败时
- **则** 来自 `.note-item` 的列表级字段（标题、点赞等）可以仍保留在结果中
- **且** 仅当弹窗提取成功时才覆盖详情字段
