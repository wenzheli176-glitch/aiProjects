## Why

监测任务目前仅支持手动触发，无法评估各次执行效率；重复执行时 raw 层 dedup 会静默丢弃 payload 更新，分析层仍对全部 raw 调用 LLM（仅写入时 dedup），浪费 token；缺少定时调度与分 run / 分源耗时、token 汇总。用户需要同一 `monitor_task` 可 cron 定时增量跑、payload 变更自动重分析、换 Prompt 时可全量覆盖重分析，并在 UI 查看执行元数据。

## What Changes

- 新增 **`monitor_task_runs`** 表：每次手动/定时执行产生一条 run，记录总/分源爬取与分析时长、raw/intel 增量统计、按 source 汇总 token。
- **raw UPSERT**：同 task 内 dedup key 命中且 `content_hash` 变化时更新 `payload_json` 与 `updated_at`，不再静默 skip。
- **增量分析队列**：默认 run 仅对「无 intel」或「raw 已更新」的条目调 LLM；payload 更新后删除同 dedup_key 旧 intel 再覆盖写入。
- **全量重分析**：保留 `clear_intel_for_task` + 全量 LLM（覆盖写）；UI 区分「增量分析」与「全量重分析」。
- **Cron 定时**：同一 `monitor_task` 可配置 cron 表达式定时触发；进程内调度器，`skip_if_running` 避免重叠。
- **前端定时选择器**：频率/时间/星期可视化控件生成 cron，禁止手输表达式（高级只读预览）。
- **Run 历史 API + 任务列表 UI**：展示最近 run、分源时长与 token、下次执行时间。
- `raw_records` 增加 `content_hash`、`dedup_key`、`updated_at`；`analysis_jobs.run_id` 关联 run。

## Capabilities

### New Capabilities

- `monitor-task-runs`: 任务执行 Run 记录、分源时长/token 汇总、增量爬取/分析统计、Run 历史 API 与看板 UI。
- `monitor-scheduler`: Cron 定时触发同一 monitor_task、可视化 schedule 配置、调度器生命周期与并发策略。

### Modified Capabilities

- `partner-registry`: 监测任务可由 cron 自动触发；任务配置含 schedule 字段；移除「不得自动执行」约束。
- `intel-pipeline`: raw UPSERT 与 content_hash；增量分析队列；payload 更新触发重分析；全量覆盖重分析语义。

## Impact

- **站点**: heimao、xhs 共用 `intel/runner.py` 爬取循环计时；`login_gate.py` 定时跑失败时需可观测（run 状态 failed，不挂死锁）。
- **config.json 新增**:
  - `monitor.scheduler_enabled` — 全局是否启用进程内调度（默认 true）
  - `monitor.scheduler_timezone` — 默认可 `Asia/Shanghai`
  - 任务级 schedule 存 SQLite `monitor_tasks.schedule_json`（非 config.json 顶层）
- **SQLite**: 新表 `monitor_task_runs`；`raw_records` 增列；`analysis_jobs.run_id`；`monitor_tasks.schedule_json`、`last_run_id`
- **API**: `GET /api/monitor/tasks/{id}/runs`；`POST /api/monitor/run` 增 `analyze_mode`；schedule PATCH；`requirements.txt` 增 `APScheduler`（或等价）
- **前端**: `panel-intel.js` 任务表单定时区块、cron 选择器、run 历史、重跑 AI 下拉
- **文档**: `代码说明.md`、`docs/API对接说明.md`
