## Context

黑猫投诉搜索页通过搜索框提交关键词后，结果列表在单页内**无限滚动**加载。既有实现假设 URL `page=` 或「下一页」按钮分页，与站点实际行为不符。小红书已采用「每轮滚动 → 解析 DOM → 饱和早停」模式，黑猫应对齐。

## Goals / Non-Goals

**Goals**

- `max_pages=M` 对 heimao 表示最多 M 轮滚动采集（与 xhs 产品语义一致）。
- 每轮：滚动 → 等待 → 解析 HTML 中投诉链接 → 去重入库。
- 见底时 `scroll_saturated` 早停；第 1 轮无结果时 `empty_page`。
- 每合作方爬取全部搜索关键词（除非 `max_keywords_per_partner>0`）。

**Non-Goals**

- 黑猫开放 API 签名分页。
- 控制台 heimao Tab 新增 scroll 表单（后续 UX 变更）。

## Decisions

### 1. 滚动策略

默认 `scroll_to_bottom=true`：每轮多次 `window.scrollTo(0, document.body.scrollHeight)`，间隔 `scroll_wait_seconds`。若列表在内部容器，可配置 `scroll_container_selector`。

### 2. 与 xhs 共用饱和早停

复用 `xhs_update_saturation(es, state, p, max_pages, new_count, item_count)`，`item_count` 为 DOM 中有效投诉链接总数。

### 3. 删除翻页模块

移除 `heimao_pagination.py`；`search_url_template` 保留为可选（搜索仍走搜索框），不再用于分页。

### 4. 关键词 cap

`max_keywords_per_partner=0` 表示不限制；仅当管理员显式设正整数时截断。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 滚动容器非 window | `scroll_container_selector` 配置 |
| 1000 轮配置耗时过长 | 饱和早停 + 合作方/任务超时 |
| 站点单次搜索实际上限 | 日志可观测；API 方案留后续 |

## Migration

- 已有 `config.json` 若含 `search_url_template` 的 `t={page}` 无需改（不再用于分页）。
- 建议根据网速调整 `scroll_times_per_page` / `scroll_wait_seconds`。
