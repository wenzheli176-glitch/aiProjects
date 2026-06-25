## ADDED Requirements

### Requirement: 数据清理 API 须管理员

系统 SHALL 对 `POST /api/admin/purge/raw` 与 `POST /api/admin/purge/intel` 施加 `@require_admin`。

#### Scenario: 操作员被拒绝

- **WHEN** `config.admin.enabled=true` 且无管理员 Session
- **THEN** purge 请求 MUST 返回 403

#### Scenario: 管理员可清理

- **WHEN** 有效管理员 Session 且请求含合法 `task_id`
- **THEN** MUST 允许 dry_run 与删除
