## Context

当前 `run_monitor_task` 在 `intel/runner.py` 中顺序执行：list → triage → investigation → `_run_analysis_phase`。`is_monitor_busy()` 在 `crawling`/`analyzing` 或 `S.running` 时阻止 `reanalyze`。增量去重已通过 `get_raw_analysis_state` + `raw.updated_at` vs `intel.created_at` 实现。

用户要求：**investigation 每批完成即 analyze drain** + **定时兜底** + **仅 detail 候选** + **crawl 中可手动 incremental AI**。

## Goals / Non-Goals

**Goals:**

- Run 内 investigation 与 AnalyzePipeline **wall-clock 重叠**，缩短总耗时。
- 双触发 drain：**批完成事件**（主路径）+ **定时 poll**（失败/遗漏兜底）。
- 候选 **严格 detail-only**（`crawl_phase=detail`；heimao legacy 有效详情 body 等价）。
- 分析完成后沿用 intel 增量标记，Run 收尾 **只补漏**。
- `crawling` 态允许 **同 task incremental reanalyze**（detail-only），不启动新 crawl Run。

**Non-Goals:**

- crawl 中 **full_replace** 重分析（仍禁止）。
- list-phase raw 的自动 drain（含 xhs quota skip 的 list-only；留收尾补漏或手动 AI）。
- 跨 task 并行 Run；跨机器 analyze Worker。
- 改变 crawl_only Run 跳过 analyze 的语义。

## Decisions

### 1. `drain_analyze_ready()` 统一入口

新增 `intel/runner.py`（或 `intel/analyze_drain.py`）函数：

```
drain_analyze_ready(task_id, run_id, task, partners, *, trigger='batch'|'timer'|'manual', run_metrics, log_fn)
  → candidates = _build_candidates_from_raw(..., detail_only=True)
  → if empty: return 0
  → acquire run analyze lock
  → analyze_candidates(..., incremental)
  → update progress stats
  → release lock
```

**detail_only** 收紧 `_should_analyze_raw`：

- MUST `crawl_phase == 'detail'`
- OR heimao legacy + `_heimao_routine_has_detail`（与 investigation 跳过逻辑一致）
- MUST NOT `crawl_phase == 'list'`

**Alternatives:** 独立后台线程 — 否决；与 poll 合并更简单，且与 Worker on_poll 天然集成。

### 2. 双触发：批完成 + 定时

| 触发 | 挂载点 | 说明 |
|------|--------|------|
| **batch** | `process_investigation_batch` 返回后；xhs keyword 流水线同页勘察批后 | 主路径，延迟最低 |
| **timer** | `wait_queue_barrier` / `run_routine_crawl_with_workers` 的 `on_poll`；单进程 investigation 循环内 | 兜底 investigation 失败、drain 异常、进程恢复 |

配置：

- `monitor.analyze_during_crawl`（默认 `true`）
- `monitor.analyze_drain_interval_sec`（默认 `60`）

定时 drain 使用 `last_drain_at` 节流，避免与批完成 drain 重复空转。

### 3. Run 内 analyze 执行锁

同一 `run_id` 同时只允许一个 drain/reanalyze 执行 analyze（threading.Lock 或 DB `run_analyze_lock`）。

- 批完成 drain 与定时 drain 串行
- 手动 incremental AI 与自动 drain **互斥等待**（或合并队列），避免 duplicate LLM

**Alternatives:** per-raw claim 表 — 过重；单锁 + incremental 去重足够。

### 4. 收尾 analyze 改补漏

`run_monitor_task` 末尾：

```
if crawl_only: skip (unchanged)
remaining = count_detail_pending_analyze(task_id)
if remaining == 0: skip _run_analysis_phase, log "drain 已完成"
else: _run_analysis_phase(..., detail_only=True)  # 仅 remaining
```

含 xhs quota skip 的 list-only raw（spec 既有「skip 后仍写 intel」）**仅在收尾补漏**处理，不进入 during-crawl drain。

### 5. busy 语义与手动 incremental AI

`is_monitor_busy(for_reanalyze=False)` 或新参数 `allow_same_task_incremental`:

- **禁止**：第二个 `run_monitor_task`、手工 crawl、`full_replace` reanalyze
- **允许**：当前 task `status=crawling` 时 `POST /api/monitor/reanalyze` + `analyze_mode=incremental`

`enrich_task_row`: `can_reanalyze = raw_count > 0 && (not busy || (is_active && !crawl_only))`

手动 AI 调用同一 `drain_analyze_ready(..., trigger='manual')`。

### 6. progress / stats

`progress_json` 扩展（同 Run）：

```json
{
  "analyze_drain": {
    "done": 120,
    "pending_detail": 880,
    "last_trigger": "batch",
    "last_at": "..."
  }
}
```

`stats_json`: `analyze_during_crawl_ms`, `analyze_drained_count`, `analyze_drain_timer_runs`

### 7. analyze 并行度

during-crawl drain 在 orchestrator 线程执行；`analyze.py` 当前非主线程时 `parallel_batches=1`。**Decision:** drain 路径允许配置 `analysis.parallel_batches_during_crawl`（默认同 `parallel_batches`），并移除/放宽非主线程强制为 1 的限制（需验证 SQLite 锁）。

### 8. LLM 限流

list_triage + drain analyze 可能同时打 LLM。**Mitigation:** 可选 `monitor.analyze_drain_max_batches_per_tick`（默认不限制）；文档说明调低 `parallel_batches`。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| drain 与 triage 同时 LLM → 429 | 配置限流；默认定时 60s |
| 收尾与 drain 重复分析 | incremental + 单 Run analyze 锁 |
| SQLite 写竞争 | 现有 `_db_lock`；analyze 锁串行 |
| UI 状态 `crawling` 但实际也在 analyze | progress 双指标 + 文案「爬取+分析中」 |
| investigation 失败 batch 无 detail | 定时兜底 + 收尾补漏 |

## Migration Plan

1. 默认 `analyze_during_crawl=true`，现网行为渐进增强；可关回旧串行。
2. 无 DB schema 强制变更（progress/stats JSON 扩展即可）。
3. 部署后观察 Run `analyze_during_crawl_ms` 与 LLM 错误率。

## Open Questions

- xhs quota skip list-only 是否永远等收尾（当前设计：是，符合用户 detail-only 要求）。
- 是否在 UI 将 `crawling+analyze drain` 显示为复合状态标签（建议：progress 子字段，任务 status 仍为 `crawling` 直到 crawl 阶段结束）。
