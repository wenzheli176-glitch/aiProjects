## MODIFIED Requirements

### Requirement: 统一风险看板

系统 SHALL 提供内部 Web 看板，展示 IntelRecord 列表，支持按合作方、来源、相关度、风险类型与时间筛选；默认展示 high 与 medium 相关度（高召回）。看板 MUST 作为统一 Web 壳的一个 Tab 呈现，而非独立 `/dashboard` 应用。列表 MUST 分列展示发布时间、采集时间、生成时间。

#### Scenario: 默认筛选

- **当** 用户打开看板且未改筛选
- **则** 必须仅展示 `relevance` 为 high 或 medium 的记录
- **且** 用户必须可切换「含 low」或「全部含 noise」

#### Scenario: 来源标签展示

- **当** 展示每条情报
- **则** 必须显示 `source` 标签（如黑猫投诉、小红书）
- **且** 不得在本系统内计算或展示业务权重分

#### Scenario: 按合作方统计

- **当** 用户选择监测任务或时间范围
- **则** 看板必须展示各合作方信号计数及按 source 分组计数
- **且** 计数不得隐含权重合并

#### Scenario: 三列时间展示

- **当** 渲染情报列表
- **则** 必须分别显示 `published_at`（发布时间）、`captured_at`（采集时间）、`analyzed_at`（生成时间）
- **且** 表头 MUST 使用字段标签 registry 中文名

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
