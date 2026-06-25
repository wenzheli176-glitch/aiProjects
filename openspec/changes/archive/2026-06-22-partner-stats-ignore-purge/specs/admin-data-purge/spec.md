## ADDED Requirements

### Requirement: 管理员批量清理源数据

系统 SHALL 提供 `POST /api/admin/purge/raw`，允许管理员按监测任务批量删除 raw_records。

#### Scenario: task_id 必填

- **WHEN** 请求未含 `task_id`
- **THEN** MUST 返回 400
- **且** MUST NOT 执行任何删除

#### Scenario: dry_run 预览

- **WHEN** `dry_run=true` 且筛选条件合法
- **THEN** MUST 返回 `matched_count`
- **且** MUST NOT 删除任何行

#### Scenario: 按任务清理

- **WHEN** 仅提供 `task_id` 且 `dry_run=false`
- **THEN** MUST 删除该 task 下所有匹配 raw_records
- **且** 响应 MUST 含 `deleted_count`

#### Scenario: 可选合作方与发布时间

- **WHEN** 同时提供 `partner_id` 和/或 `published_before`
- **THEN** MUST 在 `task_id` 范围内 AND 组合筛选
- **且** `published_before` 比较字段 MUST 为 `published_at`（YYYY-MM-DD）
- **且** `published_at` 为空的 raw MUST NOT 被 `published_before` 条件匹配删除

#### Scenario: 运行中任务不可清理

- **WHEN** 对应 `task_id` 状态为 `crawling` 或 `analyzing`
- **THEN** MUST 返回 400 并拒绝 purge

### Requirement: 管理员批量清理情报

系统 SHALL 提供 `POST /api/admin/purge/intel`，允许管理员按监测任务批量删除 intel_records。

#### Scenario: task_id 必填

- **WHEN** 请求未含 `task_id`
- **THEN** MUST 返回 400

#### Scenario: dry_run 与删除

- **WHEN** `dry_run=true`
- **THEN** MUST 返回 `matched_count` 且不删除
- **WHEN** `dry_run=false`
- **THEN** MUST 删除匹配 intel 并返回 `deleted_count`
- **且** 对应 raw_records MUST 保留

#### Scenario: 筛选语义与 raw purge 一致

- **WHEN** 提供 `partner_id` 和/或 `published_before`
- **THEN** MUST 与 raw purge 相同的 AND 组合语义
- **且** 空 `published_at` 的 intel MUST NOT 被 `published_before` 匹配
