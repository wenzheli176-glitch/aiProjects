## ADDED Requirements

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

## MODIFIED Requirements

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
