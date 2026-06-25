## ADDED Requirements

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
