## Context

小红书 list_first 将 list 与 investigation 分离以节省弹窗配额，但 investigation 依赖重开搜索页定位 DOM，与列表阶段会话不一致。Run #47 在 73 条勘察队列上大量 `dom_not_found` 并最终 `crawl_budget_sec` 超时。

## Goals / Non-Goals

**Goals:**
- 单 keyword 内完成 list → triage → 同页勘察
- 子任务可观测、可重跑
- 合作方级 per-source 超时，默认 3600s，可加长

**Non-Goals:**
- 不改变黑猫 legacy 爬取策略（仅加 per-partner 超时）
- 不改为 goto explore 详情
- 不做多 Tab 常驻搜索页

## Decisions

### 1. `keyword_pipeline` Worker phase

每个 xhs keyword 一条 `crawl_work_queue` 项，phase=`keyword_pipeline`。heimao legacy 仍并行。全部 routine 完成后，xhs **不再**进入 `_run_post_list_crawl_phases` 批量 investigation。

### 2. 同页勘察

`crawl_xhs_list_with_dom` 保留 `link→note-item` 映射；triage 完成后对需勘察条目直接 `fetch_xhs_detail_via_modal`，仅在同一 page 上 fallback `find_note_item_for_url`。

### 3. `monitor_keyword_runs`

字段：`run_id`, `task_id`, `source_id`, `keyword`, `cohort`, `status`, `phase`, `timeout_sec`, `stats_json`, `error_message`。`sync_task_subtask_progress` 写入 `monitor_tasks.progress_json.subtasks`。

### 4. 超时解析

`resolve_source_timeout_sec(source, partners, keyword=..., partner=...)`：匹配 keyword 所属合作方，取各源 `source_timeouts[source]` 与全局默认的 **最大值**。

### 5. 重跑

`POST /api/monitor/retry-keywords` 创建新 Run，仅 enqueue 指定 keyword 的 `keyword_pipeline` 项，完成后仍走 AI analyze。

## Risks / Trade-offs

- **LLM 调用更分散**：每 keyword 一次 triage，API 往返略增；换取勘察成功率与可恢复性。
- **keyword 顺序执行**：单 xhs Worker 串行 keyword；与 heimao 并行，整体 wall-clock 可接受。
