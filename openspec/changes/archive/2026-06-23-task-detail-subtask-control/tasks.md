## 1. 后端：分源 halt 与子任务 API

- [x] 1.1 `monitor_task_runs.source_halt_json` 与 get/set/clear helpers
- [x] 1.2 `request_task_halt`：pause 单源 / stop 全局；pause 收尾 Run
- [x] 1.3 `build_run_subtasks_by_source`、`build_source_subtask_items`、`resolve_subtask_detail_status`
- [x] 1.4 `GET /api/monitor/runs/{id}/subtasks`；任务 enrich `progress.sources`
- [x] 1.5 `POST pause/stop/resume` API 与 `list_resume_sources`

## 2. 阶段用时

- [x] 2.1 `keyword_pipeline` 写入 `phase_timing_ms` 与运行中增量
- [x] 2.2 Worker `mark_done(phase_timing_ms=...)`；queue payload 持久化
- [x] 2.3 `_keyword_phase_timing` / `_queue_item_phase_timing`

## 3. 控制台：任务详情页

- [x] 3.1 `taskDetailView` 五 Tab + URL query 深链
- [x] 3.2 子任务 Tab：Run 选择器、分源块、细粒度状态、三阶段用时列
- [x] 3.3 源数据/情报 Tab + 手动刷新
- [x] 3.4 任务列表 `patchTaskRow`、分源进度、`formatTaskProgressSummary`

## 4. 无闪屏刷新

- [x] 4.1 子任务/概览 Tab：`refreshTaskDetailHeaderOnly` + patch
- [x] 4.2 源数据/情报 Tab：`syncTaskDetailTableBody` 行级 patch

## 5. 测试

- [x] 5.1 `scripts/test_task_control.py`（halt/stop/pause/resume）
- [x] 5.2 `scripts/test_support.py` 测试任务自动清理
- [x] 5.3 `scripts/test_run_state.py` fixture 清理

## 6. 手动验证

- [x] 6.1 运行含 xhs+heimao 任务：子任务 Tab 见分源状态与三阶段用时；暂停 xhs 后 heimao 仍跑 — **需 Chrome 手动**
- [x] 6.2 终止任务后 Run 为 stopped、无「继续」；暂停后可继续 — **需 Chrome 手动**
- [x] 6.3 详情源数据/情报 Tab 运行中刷新无闪屏 — **需 UI 手动**
- [x] 6.4 验证完成后 `python scripts/sync_verification_tasks.py push`
