## 架构

### ignore_before 三阶段

```
列表爬取 → insert_raw_records(filter) → investigation_queue(filter) → _build_candidates_from_raw(filter)
```

共用 `should_skip_ignore_before(published_at, cutoff)`：`published_at` 为空不跳过；日期比较取 `YYYY-MM-DD` 前缀。

`resolve_ignore_before(task, business_spec)` 先读 `task.business_spec`，再 merge 传入的 business_spec，避免空 `{}` 覆盖任务级配置。

列表阶段在 raw dict 上用 `_raw_published_at(source, record)` 解析日期（与入库展示一致），不依赖 NormalizeAdapter。

### 列表分页

前端 `static/list-pagination.js` 提供 `renderListPagination`；`panel-raw.js` / `panel-intel.js` 维护 page/pageSize 状态，经 `App.setQuery` 写入 URL。

后端 `GET /api/raw/records` 与 `GET /api/intel/records`：`page_size` 默认 20，`min(max(n,1), 200)`。

### 黑猫 end_marker

`crawl_early_stop.py` 为 heimao 与 xhs 分别维护 default `end_texts`；`heimao_body_has_end_marker` / 滚动后检测触发 `reason=end_marker`。

## 决策

| 决策 | 理由 |
|------|------|
| 列表过滤在 insert 前而非 DB trigger | 减少 SQLite 写入与后续 triage/investigation 压力 |
| published_at 为空仍入库/仍勘察 | 无法判定时效，保持高召回 |
| 任务详情子 Tab 暂不分页 | 运行中增量 patch 复杂度高；全局 Tab 优先 |

## 风险

| 风险 | 缓解 |
|------|------|
| 列表时间解析与 normalize 不一致 | 共用 `_raw_published_at` |
| 用户误以为 ignore_before 删库 | 日志 `[monitor] raw 忽略早于 … 跳过 N` |
