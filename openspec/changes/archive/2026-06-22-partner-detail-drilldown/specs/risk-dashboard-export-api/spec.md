## ADDED Requirements

### Requirement: 合作方详情情报子 Tab

合作方详情「情报」子 Tab MUST 复用 `GET /api/intel/records` 与 `GET /api/intel/export`，筛选语义与情报中心 Tab 一致。

#### Scenario: 默认相关度

- **WHEN** 打开合作方详情情报子 Tab
- **THEN** 列表请求 MUST 含 `partner_id`
- **且** 默认 MUST 含 `relevance_min=medium`（与看板 KPI 一致）

#### Scenario: 导出

- **WHEN** 用户在合作方详情情报子 Tab 点击导出
- **THEN** MUST 使用当前 `partner_id` 与相关度筛选调用 export API
