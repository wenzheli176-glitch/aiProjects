# raw-records-api Specification

## Purpose
TBD - created by archiving change console-ux-overhaul. Update Purpose after archive.
## Requirements
### Requirement: 源数据 REST 列表与详情

系统 SHALL 提供 raw_records 分页查询与单条详情 API，供 Web 壳「源数据」Tab 使用；列表 MUST 仅返回摘要字段，全文 payload 仅在详情 API 返回。

#### Scenario: 分页列表

- **当** 调用 `GET /api/raw/records`
- **则** 必须支持 `task_id`、`partner_id`、`source`、`since`、分页参数
- **且** 每条 MUST 含 id、task、partner、source、keyword、标题/摘要、created_at、updated_at、分析状态（有/无 intel）
- **且** 列表响应 MUST NOT 内联完整 payload_json

#### Scenario: 单条详情

- **当** 调用 `GET /api/raw/records/{id}`
- **则** 必须返回完整 payload 及 dedup_key、content_hash
- **且** 若有对应 intel_record MUST 返回可跳转的 intel id 引用

### Requirement: 源数据导出

系统 SHALL 支持按与列表相同的筛选条件全量导出 raw_records 为 JSON、CSV 或 Excel。

#### Scenario: 当前筛选全量导出

- **当** 调用 `GET /api/raw/export?format=json|csv|xlsx` 并带与列表相同的 filter 参数
- **则** 必须导出**所有匹配行**，不得仅限当前 `page`
- **且** UI 文案 MUST 标明「导出当前筛选结果」

#### Scenario: 导出含关键字段

- **当** 导出 JSON 或 Excel
- **则** 必须含 id、task_id、partner_id、source、keyword、created_at、updated_at、dedup_key
- **且** JSON 导出 MAY 含完整 payload；Excel MAY 扁平化摘要列 + payload 列

### Requirement: 源数据 Web Tab

系统 SHALL 在统一 Web 壳提供「源数据」Tab：摘要列表、独立详情页（`raw_id` query）、返回列表保留筛选。

#### Scenario: 详情页深链

- **当** URL 含 `?tab=raw&raw_id={id}`
- **则** 必须展示该条 raw 全文详情视图
- **且** 「返回」 MUST 移除 raw_id 并保留其他 filter query

#### Scenario: 跳转关联情报

- **当** raw 详情存在关联 intel
- **则** 必须提供跳转 `?tab=intel&intel_id=` 的链接

