## MODIFIED Requirements

### Requirement: MonitorTask 任务超时

系统 SHALL 在 `run_monitor_task` 执行期间读取 `config.monitor.task_timeout_sec`（默认 7200）作为整任务 wall-clock 硬顶；并 SHALL 读取 `config.monitor.analysis_timeout_sec`（默认 3600）与 `config.monitor.min_crawl_timeout_sec`（默认 1800）计算爬取与分析分阶段预算。超时后 MUST 停止当前阶段并释放全局运行锁。

#### Scenario: 爬取阶段预算

- **当** 监测任务进入 `crawling`（含 Worker routine、investigation_crawl）
- **则** `timeout_check('crawl')` MUST 使用 `crawl_deadline = task_started + crawl_budget`
- **且** `crawl_budget` MUST 为 `max(min_crawl_timeout_sec, task_timeout_sec - analysis_reserve)`
- **且** `analysis_reserve` MUST 为 `min(analysis_timeout_sec, task_timeout_sec - min_crawl_timeout_sec)` 并不少于 300 秒
- **且** 当 `analysis_timeout_sec` 配置过大时 MUST clamp 而非使爬取预算低于 `min_crawl_timeout_sec`

#### Scenario: 爬取阶段超时

- **当** `crawling` 阶段 `elapsed ≥ crawl_deadline`
- **则** 必须将 `S.running` 置为 false 以中断爬取循环
- **且** 任务状态必须更新为 `failed`
- **且** `error_message` MUST 包含「爬取阶段超时」与 `crawl_budget_sec`（或等价字段）
- **且** `monitor_tasks.progress.reason` MUST 为 `crawl_timeout`

#### Scenario: 分析阶段超时

- **当** 监测任务处于 `analyzing` 且 wall-clock 自任务开始 `elapsed ≥ task_timeout_sec`
- **则** 必须在下一批 AI 调用前停止分析
- **且** 任务状态必须更新为 `failed`，已写入的 `intel_records` 必须保留
- **且** `error_message` MUST 包含「分析阶段超时」或「任务超时」与 `task_timeout_sec`
- **且** `monitor_tasks.progress.reason` MUST 为 `timeout`

#### Scenario: 重跑 AI 不受监测超时约束

- **当** 调用 `reanalyze_monitor_task` 且不存在 CDP 爬取
- **则** 不得应用 monitor 分阶段超时中断逻辑

#### Scenario: 超时进度可观测

- **当** 因超时失败
- **则** `monitor_tasks.progress` JSON 必须包含 `reason`（`crawl_timeout` 或 `timeout`）
- **且** 终端日志必须输出 `[monitor] 爬取阶段超时` 或 `[monitor] 任务超时` 类信息，且 MUST 区分阶段

#### Scenario: 配置示例与文档

- **当** 读取 `config.json.example` 中 monitor 超时字段
- **则** `analysis_timeout_sec` MUST 小于 `task_timeout_sec`
- **且** 文档 MUST 说明 `analysis_timeout_sec` 从总时长预留分析时间，影响爬取可用预算

## ADDED Requirements

### Requirement: 监测超时预算单元测试

系统 SHALL 提供自动化测试验证 `compute_monitor_deadlines`（或等价函数）在边界配置下的 `crawl_budget_sec` 与 `analysis_reserve_sec`。

#### Scenario: analysis 与 task 同为 7200

- **当** `task_timeout_sec=7200` 且 `analysis_timeout_sec=7200` 且 `min_crawl_timeout_sec=1800`
- **则** `crawl_budget_sec` MUST 不小于 1800
- **且** MUST 不等于 300（旧实现的错误压缩）

#### Scenario: 典型生产配置

- **当** `task_timeout_sec=7200` 且 `analysis_timeout_sec=3600`
- **则** `crawl_budget_sec` MUST 为 3600
