## Context

在 `xhs-keyword-pipeline-subtasks` 之后，控制台仍用 Run Drawer 展示 keyword 表，且任务控制仅有全局 busy 判断。用户需要按数据源查看子任务、暂停单源、终止整任务，并在详情页直接浏览 raw/intel。

## Goals / Non-Goals

**Goals**

- 任务详情独立视图，五 Tab 与 query 深链
- Run 级 `source_halt_json` + API `pause/stop/resume` 与 Worker/Runner 协作
- 子任务统一模型（keyword + queue），含 `phase_timing_ms`
- 轮询时 DOM patch，保留滚动位置

**Non-Goals**

- 不改造 Run Drawer 为唯一入口（详情页为主，Drawer 可保留兼容）
- 不新增 per-source「终止后继续单源」—— stop 即整任务结束
- 不实现子任务分页（仍 limit 100）

## Decisions

### 1. 终止 vs 暂停

- **pause**（可带 `source`）：设置 `source_halt_json[source]=pause` 或全局 `pause_requested`；收尾当前 Run 为 `paused`，任务 `status=paused`，**可 resume**。
- **stop**（忽略 source 粒度）：全局 halt，取消未完成 keyword/队列，`finish_task_run(stopped)`，任务 `status=stopped`，**不可 resume**。

### 2. 子任务数据模型

`build_run_subtasks_by_source` 输出每源：`queue` 计数、`keywords` 计数、`subtask_items[]`（统一字段：`detail_status`、`phase_timing_ms`、`elapsed_ms`）。keyword 用时来自 `stats_json.phase_timing_ms` + 运行中 `_phase_started_at`；队列项来自 `payload._phase_timing_ms`。

### 3. 前端刷新策略

- 任务列表：`patchTaskRow` + `taskRowSignature`
- 详情子任务/概览：`refreshTaskDetailHeaderOnly` + `patchSubtasksBodyFromProgress`
- 源数据/情报 Tab：`syncTaskDetailTableBody` 行级签名，新行 prepend 时补偿 scrollTop

### 4. Schema

`monitor_task_runs.source_halt_json`：`{"xhs":"pause","heimao":"stop"}` 等。

## Risks / Trade-offs

- 手动验证项仍依赖 Chrome 跑真实 crawl → 登记于 `verification-pending.md`
- 历史 Run 无 `phase_timing_ms` 时 UI 显示 `-`

## Migration

无数据迁移；旧任务重跑后才有阶段用时。
