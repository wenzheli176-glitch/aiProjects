## MODIFIED Requirements

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
