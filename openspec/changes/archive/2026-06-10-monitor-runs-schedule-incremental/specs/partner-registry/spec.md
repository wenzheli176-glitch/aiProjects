## MODIFIED Requirements

### Requirement: 监测任务手动创建与触发

系统 SHALL 支持 MonitorTask：关联一个或多个合作方、一个或多个已启用数据源；任务可通过手动操作或 cron 定时进入执行队列。

#### Scenario: 创建监测任务

- **当** 用户选择合作方列表与来源列表（如 heimao、xhs）并提交
- **则** 系统必须创建 `monitor_tasks` 记录，初始状态为 `queued`
- **且** 必须持久化 task 与 partner、source 的关联关系

#### Scenario: 手动触发执行

- **当** 用户点击「执行」或调用 `POST /api/monitor/run`（含 `task_id`）
- **则** 系统必须创建 monitor_task_run 并启动 MonitorRunner
- **且** 默认使用增量 analyze_mode

#### Scenario: 定时触发执行

- **当** 任务 schedule.enabled=true 且 cron 到点
- **则** 系统必须对同一 task_id 创建 run（trigger=schedule）并启动 MonitorRunner
- **且** 行为与手动增量执行一致（爬取 UPSERT + 增量分析）

#### Scenario: 任务状态机

- **当** MonitorRunner 完成各源爬取
- **则** 状态必须依次经过 `crawling` → `analyzing` → `done` 或任一阶段失败时为 `failed`
- **且** `/api/monitor/tasks/{id}` 必须返回当前状态、阶段进度与 schedule 摘要

## ADDED Requirements

### Requirement: 任务 Schedule 配置持久化

系统 SHALL 在 `monitor_tasks.schedule_json` 持久化定时配置，含 enabled、cron、timezone、preset_id、skip_if_running。

#### Scenario: 创建任务默认定时关闭

- **当** 新建 monitor_task 未提交 schedule
- **则** schedule.enabled 必须为 false
- **且** 不得注册调度 job

#### Scenario: 保存 Schedule 需管理员

- **当** `config.admin.enabled=true` 且 PATCH 任务 schedule
- **则** 无管理员 Session 必须 403
- **且** 与现有任务写保护一致
