## ADDED Requirements

### Requirement: 合作方名单 CRUD

系统 SHALL 在 SQLite 中持久化合作方（Partner），并支持创建、读取、更新、删除与启用/停用。

#### Scenario: 创建合作方含别名

- **当** 用户通过 UI 或 `POST /api/partners` 提交主名称、别名列表、可选排除词与监测词
- **则** 系统必须写入 `partners` 表并返回唯一 `partner_id`
- **且** 别名必须可用于后续 PartnerMatcher 匹配

#### Scenario: 停用合作方不参与监测

- **当** 合作方 `enabled=false`
- **则** 新建 MonitorTask 时不得默认包含该合作方
- **且** 既有 intel_records 仍可查询

### Requirement: 监测任务手动创建与触发

系统 SHALL 支持 MonitorTask：关联一个或多个合作方、一个或多个已启用数据源，且仅通过手动操作进入执行队列。

#### Scenario: 创建监测任务

- **当** 用户选择合作方列表与来源列表（如 heimao、xhs）并提交
- **则** 系统必须创建 `monitor_tasks` 记录，初始状态为 `queued`
- **且** 必须持久化 task 与 partner、source 的关联关系

#### Scenario: 手动触发执行

- **当** 用户点击「开始监测」或调用 `POST /api/monitor/run`（含 `task_id`）
- **则** 系统必须将任务状态更新为 `crawling` 并启动 MonitorRunner
- **且** 不得在未手动触发时自动执行定时监测

#### Scenario: 任务状态机

- **当** MonitorRunner 完成各源爬取
- **则** 状态必须依次经过 `crawling` → `analyzing` → `done` 或任一阶段失败时为 `failed`
- **且** `/api/monitor/tasks/{id}` 必须返回当前状态与阶段进度

### Requirement: 名单驱动关键词策略

系统 SHALL 以合作方主名称与别名作为默认爬取关键词来源，而非要求用户为每次任务单独输入 ad-hoc 关键词。

#### Scenario: 默认关键词来自名单

- **当** MonitorTask 未指定 per-partner 自定义监测词
- **则** CrawlAdapter 必须使用 partner 主名称与全部别名作为搜索关键词（按源策略去重或分批）
- **且** partner 级可选 `monitor_keywords` 必须覆盖或追加默认词

#### Scenario: 排除词过滤

- **当** 合作方配置了排除词
- **则** PartnerMatcher 或归一化后规则层必须将命中排除词且无语义相关的候选标记为低优先级或写入 `export_tier=exclude`（不得静默丢弃 raw 记录）
