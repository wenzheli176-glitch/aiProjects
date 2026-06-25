## Why

监测任务仅有列表行内 Run 历史 Drawer，子任务进度与 keyword/队列明细分散；暂停/终止无法按数据源粒度控制，终止后 Run 未收尾导致无法继续或 busy 阻塞；任务详情源数据/情报自动刷新整表重绘闪屏；子任务缺少三阶段用时，难以定位性能瓶颈。

## What Changes

- **任务详情页**：列表点击进入全屏详情（概览 / 执行历史 / 子任务 / 源数据 / 情报），URL 深链 `monitor_task_id` + `task_tab`。
- **分源子任务**：`GET /api/monitor/runs/{id}/subtasks` 合并 keyword 与队列项；展示细粒度状态（排队 / 爬取列表 / 勘察详情 / 分析 / 完成 / 失败）及三阶段用时列。
- **暂停 / 终止 / 继续**：`POST .../pause?source=` 仅暂停单源；`stop` 始终结束整任务（收尾 Run、取消未完成 keyword、不可继续）；`resume` 仅 paused 任务可用。
- **控制台体验**：任务列表与子任务/源数据/情报 Tab 增量 patch 刷新，消除轮询闪屏；任务进度摘要用中文而非 JSON。
- **测试**：`scripts/test_support.py` 自动清理测试任务；`test_task_control.py` 覆盖 halt 语义。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `unified-web-console`：任务详情页与子 Tab、分源子任务 UI、阶段用时列、无闪屏刷新。
- `monitor-task-runs`：per-source halt（`source_halt_json`）、subtasks API、stop/pause/resume 语义。
- `xhs-keyword-pipeline`：keyword 子任务 `phase_timing_ms` 持久化与运行中增量。

## Impact

- **后端**：`intel/run_state.py`、`intel/db.py`、`intel/api.py`、`intel/keyword_pipeline.py`、`intel/worker.py`、`intel/crawl_queue.py`
- **前端**：`static/panel-intel.js`、`static/app.css`、`templates/app.html`
- **测试**：`scripts/test_task_control.py`、`scripts/test_support.py`、`scripts/test_run_state.py`
