## ADDED Requirements

### Requirement: 合作方详情内嵌源数据

在合作方详情「源数据」子 Tab 中，列表查询 MUST 同时携带 `partner_id` 与 `task_id`；不得使用「全部任务」作为默认。

#### Scenario: 必选 task_id

- **WHEN** 合作方详情源数据子 Tab 加载列表
- **THEN** 调用 `GET /api/raw/records` MUST 含 `partner_id` 与 `task_id`
- **且** 无 `task_id` 时 MUST NOT 发起列表请求，应展示空态

#### Scenario: 切换任务

- **WHEN** 用户在下拉框切换关联监测任务
- **THEN** MUST 更新 URL `task_id` query 并重新加载 raw 列表
