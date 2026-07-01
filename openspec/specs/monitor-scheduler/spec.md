# monitor-scheduler Specification

## Purpose
TBD - created by archiving change monitor-runs-schedule-incremental. Update Purpose after archive.
## Requirements
### Requirement: Cron 定时调度

系统 SHALL 在进程内维护调度器，按 `monitor_tasks.schedule_json.cron` 定时触发同一 monitor_task 的增量执行；cron MUST 为标准五段表达式；触发 MUST 继承任务级 `crawl_only` 配置。

#### Scenario: 启用定时

- **当** 任务 `schedule.enabled=true` 且全局 `monitor.scheduler_enabled=true`
- **则** 调度器必须注册 job，到点调用 `run_monitor_task(task_id, trigger='schedule', crawl_only=task.crawl_only)`
- **且** 必须使用 `schedule.timezone`（默认 `Asia/Shanghai`）

#### Scenario: 定时 crawl_only 任务

- **WHEN** 任务 `crawl_only=true` 且定时触发
- **THEN** MUST 以 crawl_only 模式执行 Run
- **AND** MUST NOT 在 Run 结束时自动 reanalyze

#### Scenario: 禁用定时

- **当** 用户关闭 schedule 或删除 cron job
- **则** 调度器必须移除对应 job
- **且** 不得再自动触发该 task

#### Scenario: 更新 Schedule 热加载

- **当** 管理员 PATCH 任务 schedule 字段
- **则** 必须立即 reload 调度 job
- **且** `next_run_at` 必须可通过 API 或 task 详情返回

### Requirement: 可视化 Cron 配置

系统 SHALL 在监测任务编辑 UI 提供频率、时间、星期选择控件生成 cron；用户 MUST NOT 需要手输 cron 表达式。

#### Scenario: 控件生成 Cron

- **当** 用户选择「每天 08:00」
- **则** 必须生成 `0 8 * * *` 并保存至 schedule_json
- **且** UI 必须只读预览「每天 08:00 · cron: …」

#### Scenario: 每周工作日

- **当** 用户选择每周且勾选周一至周五 09:30
- **则** 必须生成对应 DOW 的 cron（如 `30 9 * * 1-5`）
- **且** 加载任务时必须反解析到控件（preset 子集内）

#### Scenario: 每 N 小时

- **当** 用户选择每 6 小时
- **则** 必须生成 `0 */6 * * *` 或等价表达式
- **且** preset_id 必须持久化便于 UI 回显

### Requirement: 调度并发策略

系统 SHALL 默认同 task 不重叠执行；定时触发遇运行中任务时必须 skip 并记录 run。运行中判定 MUST 基于 active monitor run 状态，**不得**仅依赖 `crawler_web.S.running`。

#### Scenario: skip_if_running 查 Run 状态

- **当** schedule 触发且 `skip_if_running` 为 true（默认）
- **且** 该 task 存在 `monitor_runs.status` 为 running/crawling/analyzing 的记录
- **则** MUST 创建 `skipped_overlap` run 并跳过
- **且** MUST NOT 依赖 Flask 进程内 `S.running` 单例

#### Scenario: Worker 并行不触发误 skip

- **当** Run 使用多 Worker 且 `S.running` 在子进程为 false
- **则** scheduler MUST 仍能通过 run 表正确识别「任务进行中」

#### Scenario: 登录失败不阻塞调度器

- **当** 定时 run 因 login_gate 失败
- **则** run MUST failed 并释放 run 锁
- **且** 后续 cron MUST 仍可触发

