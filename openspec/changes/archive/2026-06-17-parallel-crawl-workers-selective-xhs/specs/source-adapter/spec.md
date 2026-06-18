## ADDED Requirements

### Requirement: 数据源级 crawl_mode

系统 SHALL 在 `config.sources.{id}` 为每个源定义 `crawl_mode`；MonitorRunner MUST 按源选择 pipeline。

#### Scenario: xhs 强制 list_first

- **当** source_id 为 xhs
- **则** `crawl_mode` MUST 为 `list_first`
- **且** UI/API MUST NOT 允许 xhs 设为 legacy

#### Scenario: heimao 默认 legacy

- **当** source_id 为 heimao
- **则** 默认 `crawl_mode=legacy`；routine MAY 使用 task.fetch_detail

#### Scenario: 混合源任务

- **当** 任务同时含 heimao 与 xhs
- **则** MUST 按源分别路由（非 task.crawl_mode 二选一）
- **且** routine crawl MAY 并行（crawl-worker-pool）

### Requirement: monitor_tasks.crawl_mode 降级

`monitor_tasks.crawl_mode` 列保留兼容，但混合源任务 MUST NOT 作为唯一路由依据。

#### Scenario: 混合源忽略 task 级 crawl_mode

- **当** task.sources 含 heimao 与 xhs
- **则** Runner MUST 忽略 task.crawl_mode 的单值分支
- **且** MUST 按各源 crawl_mode 分别编排

#### Scenario: 仅 heimao 单源任务

- **当** task.sources 仅 heimao 且未启用 Worker 池
- **则** MAY 使用 task.crawl_mode 作 fallback（默认 legacy）

## MODIFIED Requirements

### Requirement: MonitorTask fetch_detail 语义

系统 SHALL 在源级 list_first（含强制 xhs）下忽略 task.fetch_detail 对该源 routine 的影响；详情由 investigation 触发。heimao legacy MAY 使用 task.fetch_detail。

#### Scenario: xhs routine 无详情

- **当** source 为 xhs
- **则** routine MUST 等价 fetch_detail=false

#### Scenario: heimao legacy 详情

- **当** heimao crawl_mode=legacy 且 task.fetch_detail=true
- **则** heimao routine MAY fetch_detail
- **且** MUST NOT 影响 xhs list_first 行为
