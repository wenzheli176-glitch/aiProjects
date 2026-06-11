## ADDED Requirements

### Requirement: Cron 定时调度

系统 SHALL 在进程内维护调度器，按 `monitor_tasks.schedule_json.cron` 定时触发同一 monitor_task 的增量执行；cron MUST 为标准五段表达式。

#### Scenario: 启用定时

- **当** 任务 `schedule.enabled=true` 且全局 `monitor.scheduler_enabled=true`
- **则** 调度器必须注册 job，到点调用 `run_monitor_task(task_id, trigger='schedule')`
- **且** 必须使用 `schedule.timezone`（默认 `Asia/Shanghai`）

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

系统 SHALL 默认同 task 不重叠执行；定时触发遇运行中任务时必须 skip 并记录 run。

#### Scenario: skip_if_running 默认开启

- **当** schedule 未显式关闭 `skip_if_running`
- **则** 默认必须为 true
- **且** 与 `monitor-task-runs` skipped_overlap 场景一致

#### Scenario: 登录失败不阻塞调度器

- **当** 定时 run 因 login_gate 失败
- **则** run 必须标记 failed 并释放 `S.running`
- **且** 后续 cron 触发必须仍可尝试
