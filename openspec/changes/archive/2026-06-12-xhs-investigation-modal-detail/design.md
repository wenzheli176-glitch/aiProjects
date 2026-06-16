## Context

- **正确路径**：`crawl_xhs` + `fetch_xhs_detail_via_modal(page, item, link)`（搜索页点击 → 弹窗 → 提取 → 关闭）。
- **错误路径**：`fetch_xhs_details_by_urls` 对每条 URL `page.goto(url)`，注释写明「investigation 模式 goto」。
- **Stage2**：`list_first` routine 不抓详情；`run_investigation_crawl` → `XhsCrawlAdapter.crawl_investigation` → `fetch_xhs_details_by_urls`。
- **用户决策**：单条 DOM 找不到 → **允许跳过**；同一批次 **大量** DOM 找不到 → **重搜**后再试。

## Goals / Non-Goals

**Goals:**

- 勘察 100% 走弹窗，与 `xhs-detail-modal` spec 一致。
- 仅有 URL 时能在搜索页 DOM 定位 note-item 并点击。
- 单条 miss → skip + 明确 failed 原因；批量 miss → keyword 重搜一轮。
- 降低风控：同页会话、弹窗间隔、不新开 tab、不 goto explore。

**Non-Goals:**

- goto explore 兜底
- 修改手工 crawl 已有弹窗逻辑（除抽取共用 helper）
- 黑猫 investigation

## Decisions

### 1. 入口统一：`fetch_xhs_details_by_urls` 重写

**选择**：保留函数名与 adapter 调用点，内部改为 modal 流程。

**流程**：

```
输入 urls[] + 可选 keyword（从 raw payload _search_keyword）
    │
    ▼
prepare_browser + xhs login_gate
    │
    ▼
goto search_result?keyword=...（若当前页非目标关键词）
    │
    ▼
for each url in batch:
    item = find_note_item_for_url(page, url)
    if not item:
        dom_miss += 1
        if dom_miss >= threshold: research_search(keyword); dom_miss=0; retry find once
        if still not item: mark failed(dom_not_found); continue
    detail, err = fetch_xhs_detail_via_modal(page, item, url)
    on success → merge payload; on auth fail → login_gate
    sleep between_detail
```

### 2. `find_note_item_for_url(page, url)`

- 从 URL 解析 note_id（`/explore/{id}` 或 query）。
- 在 `note_item_selector` 容器内查找 `link_selector` href 含 id。
- 可选：当前页滚动若干轮（`scroll_times_per_page`）逐屏查找。
- 返回 `(item_element | None, reason)`。

实现于 `xhs_detail.py`，供 `crawler_web` 与测试调用。

### 3. 单条 skip vs 批量重搜

| 事件 | 行为 |
|------|------|
| 单条 `find_note_item` 失败 | `update_investigation_status(id, 'failed', 'dom_not_found')`；**continue** 下一条 |
| 同 keyword 批次 `dom_miss` ≥ `dom_miss_research_threshold` | 记录日志 `investigation: xhs 重搜 keyword=...`；`goto search_url`；等待 + 滚动 `research_max_scroll_rounds`；**重置 dom_miss**；对当前及后续 pending URL 再试定位（当前 URL 立即重试一次） |
| 重搜后仍找不到 | 仍按单条 skip |

默认：`dom_miss_research_threshold=3`，`dom_miss_skip=true`。

**「大量」定义**：同一 keyword 上下文内连续或累计未找到次数达阈值（非全任务比例），避免偶发 miss 频繁重搜。

### 4. keyword 分组

`fetch_xhs_details_by_urls` 签名扩展为接受 `keyword` 或 `(url, keyword)` 列表；`crawl_investigation` 从 investigation_queue 关联 raw 读取 `_search_keyword` / raw.keyword。

同一 keyword 的 URL 在同一搜索页会话内顺序处理，减少 goto 搜索页次数。

### 5. 与 `fetch_xhs_detail_via_modal` 复用

勘察成功路径与手工爬取完全一致：open → scroll modal → evaluate → close → App 墙检测。

失败走 `is_xhs_detail_auth_failure` + `wait_for_site_login`，与 spec 一致。

### 6. 删除 goto 主路径

移除 `page.goto(explore_url)` 作为详情抓取手段；若代码中保留，仅允许 goto `search_result` 模板 URL。

### 7. 配置 `xhs.investigation_detail`

```json
"investigation_detail": {
  "dom_miss_skip": true,
  "dom_miss_research_threshold": 3,
  "research_max_scroll_rounds": 2,
  "between_detail_min": 4,
  "between_detail_max": 7
}
```

默认与现有 `detail_wait_*` 对齐。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 列表页无该笔记（已下架/关键词不匹配） | 单条 skip；批量重搜一次 |
| 重搜仍无法覆盖 | failed 计数入 run stats，不阻塞任务 |
| DOM 选择器变更 | 复用可配置 `note_item_selector` / `link_selector` |
| 勘察变慢（滚动找 DOM） | keyword 分组 + 间隔可配置；比 goto 风控失败更稳 |

## Migration Plan

1. 部署后勘察自动走弹窗；无需 DB migration。
2. 旧 run 中已 failed 的 investigation 可手动重跑任务。
3. 验证项：list_first 任务 xhs investigation 日志无 `goto explore`，有弹窗成功或 `dom_not_found`。

## Open Questions

- （已关闭）单条 miss → skip；批量 miss → 重搜
- run metrics 是否新增 `investigation_dom_miss` / `investigation_research` — **建议 tasks 中实现，非阻塞**
