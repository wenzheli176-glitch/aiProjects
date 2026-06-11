## MODIFIED Requirements

### Requirement: 统一风险看板

系统 SHALL 提供内部 Web 看板，展示 IntelRecord 列表，支持按合作方、来源、相关度、风险类型与时间筛选；默认展示 high 与 medium 相关度（高召回）。看板 MUST 作为统一 Web 壳的一个 Tab 呈现，而非独立 `/dashboard` 应用。

#### Scenario: 默认筛选

- **当** 用户打开情报 Tab 且未改筛选
- **则** 必须仅展示 `relevance` 为 high 或 medium 的记录（medium+ 默认）
- **且** 用户必须可切换「含 low」或「全部含 noise」

#### Scenario: 筛选区布局

- **当** 用户打开情报 Tab 列表视图
- **则** 快捷筛选控件 MUST 位于情报表格上方（非左侧栏）
- **且** MUST 含刷新与导出入口

#### Scenario: 来源标签展示

- **当** 展示每条情报
- **则** 必须显示 `source` 标签（如黑猫投诉、小红书）
- **且** 不得在本系统内计算或展示业务权重分

#### Scenario: 情报独立详情页

- **当** URL 含 `?tab=intel&intel_id={id}` 或用户从列表点击详情
- **则** 必须展示该条情报全文详情视图（摘要、正文、情感、链接、三时间）
- **且** 「返回列表」 MUST 移除 intel_id 并保留 filter query
- **且** 若存在 raw_record_id MUST 提供跳转源数据详情链接

## MODIFIED Requirements

### Requirement: JSON 与 Excel 导出

系统 SHALL 支持按 task_id 或筛选条件导出 IntelRecord 为 JSON 与 Excel。

#### Scenario: JSON 导出 schema

- **当** 用户导出 JSON 或调用 `GET /api/intel/export?format=json`
- **则** 响应必须包含 `schema_version` 与 `records` 数组
- **且** 每条 record 必须含 `source`、`relevance`、`published_at`、`captured_at`、`analyzed_at`

#### Scenario: Excel 扁平表

- **当** 用户导出 Excel
- **则** 必须包含「发布时间」「采集时间」「生成时间」列
- **且** 列集必须与 JSON 字段一致或可扁平化映射

#### Scenario: 当前筛选全量导出

- **当** 用户在情报 Tab 点击导出且列表带有 filter
- **则** 导出 MUST 包含所有匹配 filter 的记录
- **且** MUST NOT 仅导出当前分页页内 rows
- **且** UI MUST 标明「导出当前筛选结果」
