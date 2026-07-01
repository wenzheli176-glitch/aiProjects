## Why

监测 Run 在爬取（含 list_triage、investigation）结束后仍串行执行完整 AnalyzePipeline，占用 wall-clock 与 LLM 配额；当 `task_timeout_sec` 有限时，分析预留还会压缩爬取预算。用户已有 `POST /api/monitor/reanalyze` 可事后补分析，但无法在执行时选择「先爬完、稍后分析」，导致 Chrome 已空闲仍要等 Run 结束，爬取效率与超时容错不足。

## What Changes

- **crawl_only 开关**：`POST /api/monitor/run` 与任务级默认支持 `crawl_only=true`；为 true 时 Run 在爬取阶段（含 list_triage、investigation）完成后 **跳过** `_run_analysis_phase`，不调用 `analyze_candidates`。
- **Run 状态语义**：crawl_only Run 正常结束时 `status=done`（或 partial），`stats_json` 标记 `analyze_deferred=true`、`pending_analyze_raw_count`；`analyze_duration_ms=0`；任务 progress 显示 `phase=crawl_done` 或等价「待分析」。
- **超时预算**：crawl_only 时 **不预留** `analysis_reserve_sec`，全部 `task_timeout_sec`（或 unlimited）用于爬取阶段。
- **list_triage 不变**：仍嵌入爬取流水线（尤其 xhs keyword 同页勘察）；**仅**最终合作方匹配 analyze 延后。
- **事后分析**：UI 与 API 在 crawl_only Run 完成后突出「重跑 AI / 分析待处理」；沿用现有 `reanalyze`（incremental），无需新 LLM 路径。
- **定时任务**：任务 `schedule` 或 `monitor_tasks` 可配置默认 `crawl_only`；定时触发继承任务默认（默认可仍为 false 保持现网行为）。
- **resume / retry**：从失败 Run 续跑时继承原 Run 的 crawl_only 语义；keyword 重跑仍为 crawl 子集，不自动触发 analyze。

## Capabilities

### New Capabilities

（无独立新 capability；行为归入现有 monitor / pipeline spec 增量。）

### Modified Capabilities

- `monitor-task-runs`：Run 创建参数 `crawl_only`、完成状态与 stats（analyze_deferred）、超时预算分支、progress 阶段。
- `intel-pipeline`：crawl_only 跳过 AnalyzePipeline；与 incremental / reanalyze 衔接；list_triage 仍在 crawl 内。
- `unified-web-console`：任务执行 Modal / 详情页「仅爬取」选项；Run 历史「待分析」标识与一键 reanalyze。
- `monitor-scheduler`：定时触发读取任务级 `crawl_only` 默认（可选）。

## Impact

- **config.json / config.py**：可选 `monitor.default_crawl_only`（默认 `false`）；任务 JSON 增加 `crawl_only` 字段（可选，默认 false）。
- **API**：`POST /api/monitor/run` body 增加 `crawl_only`；Run 详情 `stats_json` / `progress_json` 扩展；任务 CRUD 读写 `crawl_only`。
- **intel/runner.py**：`run_monitor_task(crawl_only=...)` 分支跳过 analyze；`compute_monitor_deadlines` 调用处传入 crawl_only。
- **intel/timeout_budget.py**：crawl_only 时 analysis_reserve=0。
- **intel/db.py**：`monitor_task_runs` 可选列 `crawl_only` 或写入 stats_json；`create_task_run` 参数扩展。
- **static/panel-intel.js**：执行按钮旁 checkbox；Run 卡片待分析态。
- **docs/API对接说明.md**、**代码说明.md**：文档更新。
- **站点**：heimao / xhs 爬取逻辑不变；共用 login_gate / Worker 池不变。
