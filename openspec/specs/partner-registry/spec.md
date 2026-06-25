# partner-registry Specification

## Purpose
TBD - created by archiving change partner-risk-intel. Update Purpose after archive.
## Requirements
### Requirement: 合作方名单 CRUD

系统 SHALL 在 SQLite 中持久化合作方（Partner），并支持创建、读取、更新、删除与启用/停用；Web 列表 MUST 支持钻取关联情报与源数据。

#### Scenario: 列表查看关联数据

- **WHEN** 用户在合作方列表点击「查看情报」
- **THEN** MUST 进入合作方详情页且 `partner_tab=intel`
- **且** MUST NOT 要求管理员权限

#### Scenario: 列表查看源数据

- **WHEN** 用户在合作方列表点击「查看源数据」
- **THEN** MUST 进入合作方详情页且 `partner_tab=raw`
- **且** URL MUST 含该合作方 `default_task_id` 作为 `task_id` query（自 context API）
- **且** 无关联任务时 MUST 展示空态而非 silent 失败

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

### Requirement: 名单驱动关键词策略

系统 SHALL 以合作方主名称与别名作为默认爬取关键词来源，而非要求用户为每次任务单独输入 ad-hoc 关键词。

#### Scenario: 默认关键词来自名单

- **当** MonitorTask 未指定 per-partner 自定义监测词
- **则** CrawlAdapter 必须使用 partner 主名称与全部别名作为搜索关键词（按源策略去重或分批）
- **且** partner 级可选 `monitor_keywords` 必须覆盖或追加默认词

#### Scenario: 排除词过滤

- **当** 合作方配置了排除词
- **则** PartnerMatcher 或归一化后规则层必须将命中排除词且无语义相关的候选标记为低优先级或写入 `export_tier=exclude`（不得静默丢弃 raw 记录）

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

### Requirement: 行业 cohort 推荐

系统 SHALL 提供 cohort 推荐 API，根据合作方名称（及可选别名）返回行业 cohort 候选列表；cohort 仍为开放标签，用户 MUST 手动点选确认后方可填入表单，创建合作方时 industry_cohort 允许为空。

#### Scenario: 请求 cohort 推荐

- **当** 调用 `POST /api/partners/suggest-cohort` 且 `name` 非空
- **则** 响应 MUST 含 `candidates` 数组（最多 `max_candidates` 条）
- **且** 每条 MUST 含 `cohort` 字符串与 `source`（`existing` 或 `llm`）
- **且** MUST 返回 `existing_cohorts`（当前 DB 去重非空 cohort 列表）

#### Scenario: 优先已有 cohort

- **当** DB 中存在非空 `industry_cohort` 值
- **则** LLM 推断 MUST 在 prompt 中注入该列表并要求优先 verbatim 选用
- **且** 后处理 MUST 将 LLM 输出映射到已有 cohort（若语义接近）
- **且** `source=existing` 的候选 MUST 排在 `source=llm` 且 `is_new=true` 之前

#### Scenario: 联网搜索辅助推断

- **当** `analysis.partner_cohort_suggest.web_search_enabled=true` 且网络可用
- **则** 系统 MAY 检索品牌公开行业信息并纳入 LLM 上下文
- **且** 搜索失败或超时时 MUST 降级为仅 LLM/已有 cohort，不得阻塞 API（返回部分候选或空 candidates + existing_cohorts）

#### Scenario: 用户点选确认

- **当** 用户在合作方表单点击某 cohort 候选
- **则** MUST 仅填入 cohort 输入框
- **且** MUST NOT 自动提交保存
- **且** 用户仍可将 cohort 清空后保存

#### Scenario: cohort 为空创建合作方

- **当** `POST /api/partners` 未提供 industry_cohort 或为空字符串
- **则** MUST 成功创建 partner
- **且** shared-crawl-pool MUST 仍对该 partner 使用 `partner:{id}` fallback 分组

#### Scenario: 推荐 API 禁用

- **当** `analysis.partner_cohort_suggest.enabled=false`
- **则** API MUST 返回 `ok=false` 或空 candidates 且文档说明功能关闭
- **且** UI MUST 隐藏或禁用「获取推荐」控件

### Requirement: 行业 cohort

系统 SHALL 为 Partner 支持 `industry_cohort` 字段，用于共享爬取的关键词合并与调度分组；该字段为**开放标签**（非受控枚举），MAY 为空；系统 SHOULD 在录入时提供 cohort 推荐辅助（见「行业 cohort 推荐」），但 MUST NOT 自动写入。

#### Scenario: 创建合作方含 cohort

- **当** 用户提交 industry_cohort（如「新能源整车」）
- **则** 系统必须持久化该字符串
- **且** shared-crawl-pool 必须按 cohort 精确匹配合并 keyword_batch

#### Scenario: 未设 cohort

- **当** industry_cohort 为空
- **则** 该 partner 单独成组（cohort fallback 为 `partner:{id}`）
- **且** 不得阻止创建或更新合作方

### Requirement: 优先级字段

系统 SHALL 在 partners 表存储 priority_tier、priority_source、priority_updated_at。

#### Scenario: UI 与 API 同步

- **当** 管理员在 UI 修改 tier
- **则** 必须写入 priority_source=manual
- **且** 与业务 API 写入可互相覆盖（后者更新 updated_at）

### Requirement: 合作方钻取上下文 API

系统 SHALL 提供 `GET /api/partners/{partner_id}/context`，供合作方详情页解析默认监测任务与数据计数。

#### Scenario: 返回默认 task_id

- **WHEN** 合作方至少关联一个 monitor_task
- **THEN** 响应 MUST 含 `default_task_id` 为 `updated_at` 最新的关联任务 id
- **且** MUST 含 `tasks` 数组（该合作方关联的全部任务 id、name、updated_at）

#### Scenario: 无关联任务

- **WHEN** 合作方未出现在任何 `monitor_task_partners`
- **THEN** `default_task_id` MUST 为 null
- **且** `tasks` MUST 为空数组

#### Scenario: 计数摘要

- **WHEN** 调用 context API
- **THEN** MUST 返回 `counts.intel_total` 与 `counts.intel_medium_plus`（按 `partner_id`，`is_duplicate=0`）
- **且** MUST 返回 `counts.raw_total`（按 `partner_id` + `default_task_id`；无 default 时为 0）

### Requirement: 合作方列表数据量统计

系统 SHALL 在 `GET /api/partners` 每条合作方记录中返回 `stats`，供列表展示情报与源数据规模。

#### Scenario: 情报计数

- **WHEN** 调用 `GET /api/partners`
- **THEN** 每条 MUST 含 `stats.intel_total`（`partner_id` 全任务、`is_duplicate=0`）
- **且** MUST 含 `stats.intel_medium_plus`（`relevance IN (medium, high)`）

#### Scenario: 源数据计数与详情一致

- **WHEN** 合作方至少关联一个 monitor_task
- **THEN** MUST 含 `stats.default_task_id`（`updated_at` 最新的关联任务）
- **且** `stats.raw_total` MUST 为该 `default_task_id` + `partner_id` 的 raw 计数
- **WHEN** 无关联任务
- **THEN** `default_task_id` MUST 为 null 且 `raw_total` 为 0

#### Scenario: 列表点击钻取

- **WHEN** 用户在合作方列表点击情报统计
- **THEN** MUST 进入合作方详情且 `partner_tab=intel`
- **WHEN** 用户点击源数据统计
- **THEN** MUST 进入合作方详情且 `partner_tab=raw` 并带 `default_task_id` 作为 `task_id`

### Requirement: 合作方数据源超时

系统 SHALL 在 `partners.source_timeouts_json` 持久化 per-source 最大爬取超时（秒），键为 source_id（如 `xhs`、`heimao`）；API 读写字段名为 `source_timeouts`。

#### Scenario: 创建合作方带超时

- **当** `POST /api/partners` 提交 `source_timeouts: {"xhs": 7200}`
- **则** 该合作方 xhs keyword 子任务 MUST 使用 7200 秒超时（不低于全局默认）

#### Scenario: 未配置时使用默认

- **当** 合作方未配置某 source 超时
- **则** MUST 使用 `xhs.keyword_timeout_sec` 或 `heimao.partner_timeout_sec` 全局默认

#### Scenario: 多合作方共享 keyword

- **当** 同一 keyword 匹配多个合作方且超时不同
- **则** MUST 取各合作方该源超时与全局默认的 **最大值**

