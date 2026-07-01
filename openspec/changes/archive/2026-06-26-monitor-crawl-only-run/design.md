## Context

当前 `run_monitor_task`（`intel/runner.py`）在爬取阶段（legacy / list_crawl / xhs keyword 流水线含 list_triage + investigation）结束后，**无条件**调用 `_run_analysis_phase` → `analyze_candidates`。超时预算（`intel/timeout_budget.py`）从 `task_timeout_sec` 中预留 `analysis_reserve_sec`，压缩 crawl 窗口。

已有 `reanalyze_monitor_task` + `POST /api/monitor/reanalyze` 可独立跑 AnalyzePipeline，但执行监测时无法选择跳过最终 analyze。list_triage 仍必须在爬取内（xhs 同页勘察依赖 triage 结果），本次 **不** 延后 list_triage。

涉及模块：`intel/runner.py`、`intel/timeout_budget.py`、`intel/db.py`、`intel/api.py`、`intel/scheduler.py`、`static/panel-intel.js`。

## Goals / Non-Goals

**Goals:**

- 新增 `crawl_only` 开关（API 请求级 + 任务级默认），为 true 时 Run 爬取完成后跳过 `_run_analysis_phase`。
- crawl_only Run 释放全部 task 超时给爬取；Run stats 明确 `analyze_deferred` 与待分析 raw 计数。
- UI 展示「仅爬取 / 待分析」并提供一键 incremental reanalyze。
- resume / keyword retry 继承原 Run 的 crawl_only。

**Non-Goals:**

- 不将 list_triage 从 keyword 流水线或 heimao barrier 后流程中拆出。
- 不新增异步 analyze 队列 / 定时自动 reanalyze（用户手动或后续 change）。
- 不改变 `reanalyze_monitor_task` 的 LLM 逻辑与 incremental 语义。
- crawl_only 与 `analyze_mode=full_replace` 同次 run **互斥**（full_replace 仅 reanalyze 路径）。

## Decisions

### 1. 参数传递：`crawl_only` 独立于 `analyze_mode`

- **选择**：`run_monitor_task(..., crawl_only=False)`；DB `monitor_task_runs` 增加布尔列 `crawl_only INTEGER NOT NULL DEFAULT 0`（或等价写入 stats，优先 **独立列** 便于查询与 resume）。
- **理由**：与 incremental/full_replace 正交；Run 历史可筛选「待分析」Run。
- **替代**：仅用 stats_json — 查询不便，已否决。

### 2. 超时：`crawl_only` 时 analysis_reserve=0

- **选择**：`compute_monitor_deadlines(..., crawl_only=False)` 当 `crawl_only=True` 返回 `analysis_reserve_sec=0`，`crawl_budget_sec=task_timeout_sec`（unlimited 时行为不变）。
- **理由**：用户选仅爬取即期望 Chrome 用尽可用时间，不应为未执行的分析预留。

### 3. Run 完成状态：`done` + deferred 标记，非新 status 枚举

- **选择**：`finish_task_run(status='done')`；`stats_json.analyze_deferred=true`，`pending_analyze_raw_count=N`（`_build_candidates_from_raw` 同款过滤后的候选数，**不** 实际调 LLM）。
- **理由**：与 partial / failed 区分清晰；看板仍按 intel 计数，无 intel 时用户见「待分析」提示。
- **替代**：新 status `crawl_done` — 需改多处 busy 判断，范围过大。

### 4. 任务 progress：`phase=crawl_done` 且 `analyze_pending=true`

- **选择**：crawl_only 成功结束时 `update_task_status(task_id, 'done', progress={phase:'crawl_done', analyze_pending:true, run_id})`；**不** 进入 `analyzing`。
- **理由**：与现网四阶段 progress 兼容扩展，UI 可渲染待分析横幅。

### 5. API：`POST /api/monitor/run` body

```json
{
  "task_id": 1,
  "analyze_mode": "incremental",
  "crawl_only": true
}
```

- 默认：`crawl_only = task.crawl_only ?? monitor.default_crawl_only ?? false`。
- 若 `crawl_only=true` 且请求带 `analyze_mode=full_replace` → 400 拒绝。

### 6. UI：执行前 checkbox「仅爬取（稍后 AI 分析）」

- 任务 Modal 持久化 `crawl_only` 到任务 JSON；列表「执行」使用 Modal 内值或快捷执行默认 false（任务详情页执行按钮旁 checkbox，默认读任务字段）。
- Run 历史行：若 `run.crawl_only && stats.analyze_deferred` 显示「待分析」tag + 「增量 AI」快捷按钮。

### 7. Scheduler：继承任务 `crawl_only`

- `_fire_scheduled_task` 读取 `task.get('crawl_only')`，传入 `run_monitor_task(..., crawl_only=...)`。
- 不在 cron 层单独配置。

### 8. Resume / retry

- `find_resumable_run_id` / continue API 从原 run 读 `crawl_only` 并传递。
- keyword retry 仍为 crawl 子集；完成后若原 run crawl_only，仍不自动 analyze。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 用户忘记 reanalyze，看板无新 intel | UI 待分析横幅 + 任务列表 `can_reanalyze` 强化；Run stats 暴露 pending 计数 |
| crawl_only Run 与 busy 检测 | `is_monitor_busy` 仍看 running/crawling/analyzing；crawl_only 不进入 analyzing，Run 更快释放 |
| 定时任务仅爬取长期无 intel | 任务级默认 false；文档说明 |
| DB 迁移 | 新列 DEFAULT 0，旧 Run 视为 false |

## Migration Plan

1. DB migration：`monitor_task_runs.crawl_only`；`monitor_tasks` JSON 或列 `crawl_only`。
2. 后端 runner / timeout / API / scheduler。
3. 前端 checkbox + Run 展示。
4. 文档与 `scripts/test_crawl_only_run.py` 单元测试。
5. 回滚：配置与 UI 默认 false；代码分支 fallback 行为等同现网。

## Open Questions

- （已闭合）是否在 crawl_only Run 结束时自动 enqueue reanalyze？→ **否**，保持手动。
- （已闭合）crawl_only 是否允许 scheduler 默认 true？→ **任务级字段**，全局默认 false。
