## MODIFIED Requirements

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
