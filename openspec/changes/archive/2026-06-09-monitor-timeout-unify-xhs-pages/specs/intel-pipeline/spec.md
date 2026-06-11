## ADDED Requirements

### Requirement: MonitorTask 任务超时

系统 SHALL 在 `run_monitor_task` 执行期间读取 `config.monitor.task_timeout_sec`（默认 7200），自任务开始起按 wall-clock 计时；超时后 MUST 停止爬取与分析并释放全局运行锁。

#### Scenario: 爬取阶段超时

- **当** 监测任务处于 `crawling` 且 elapsed ≥ `task_timeout_sec`
- **则** 必须将 `S.running` 置为 false 以中断 `crawl_heimao` / `crawl_xhs` 循环
- **且** 任务状态必须更新为 `failed`，`error_message` 必须包含 `任务超时` 与配置秒数

#### Scenario: 分析阶段超时

- **当** 监测任务处于 `analyzing` 且 elapsed ≥ `task_timeout_sec`
- **则** 必须在下一批 AI 调用前停止分析
- **且** 任务状态必须更新为 `failed`，已写入的 `intel_records` 必须保留

#### Scenario: 重跑 AI 不受监测超时约束

- **当** 调用 `reanalyze_monitor_task` 且不存在 CDP 爬取
- **则** 不得应用 `monitor.task_timeout_sec` 中断逻辑

#### Scenario: 超时进度可观测

- **当** 因超时失败
- **则** `monitor_tasks.progress` JSON 必须包含 `reason=timeout` 或等价字段
- **且** 终端日志必须输出 `[monitor] 任务超时` 类信息
