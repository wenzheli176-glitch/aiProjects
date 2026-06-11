## ADDED Requirements

### Requirement: 统一风险看板

系统 SHALL 提供内部 Web 看板，展示 IntelRecord 列表，支持按合作方、来源、相关度、风险类型与时间筛选；默认展示 high 与 medium 相关度（高召回）。

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

### Requirement: JSON 与 Excel 导出

系统 SHALL 支持按 task_id 或筛选条件导出 IntelRecord 为 JSON 与 Excel。

#### Scenario: JSON 导出 schema

- **当** 用户导出 JSON 或调用 `GET /api/intel/export?format=json`
- **则** 响应必须包含 `schema_version` 与 `records` 数组
- **且** 每条 record 必须含 `source` 与 `relevance`

#### Scenario: Excel 扁平表

- **当** 用户导出 Excel
- **则** 必须包含「数据来源」列映射 `source`
- **且** 列集必须与 JSON 字段一致或可扁平化映射

### Requirement: Intel REST API

系统 SHALL 提供 REST API 供内网系统对接；MVP 阶段不做鉴权。

#### Scenario: 分页查询记录

- **当** 调用 `GET /api/intel/records`
- **则** 必须支持 query 参数：`task_id`、`partner_id`、`source`、`relevance_min`、`since`、`risk_type`、分页
- **且** 默认返回全量 relevance（由调用方过滤），文档说明高召回策略

#### Scenario: 合作方与任务 API

- **当** 调用 `GET /api/partners` 或 `GET /api/monitor/tasks`
- **则** 必须返回 SQLite 中名单与任务列表
- **且** `POST /api/monitor/run` 必须触发手动监测（见 partner-registry spec）

#### Scenario: 内网无鉴权

- **当** MVP 部署于内网
- **则** API 不得强制 API Key 或 Session
- **且** 文档必须声明仅适用于内网裸奔环境

### Requirement: 业务权重外置

系统 SHALL NOT 在 IntelRecord、看板或 API 中写入综合风险分或 source 权重；仅提供 `source` 与 AI `relevance` 供下游加权。

#### Scenario: API 响应无权重字段

- **当** 返回 intel_record
- **则** 不得包含 `weighted_score`、`final_risk` 等业务决策字段
- **且** 对接文档必须说明业务系统自行对 `source` 设置权重

#### Scenario: 可选 signal 强度

- **当** 需要辅助下游排序
- **则** 可返回 `relevance` 枚举或映射数值作为 `signal_strength`
- **且** 该数值不得与 source 权重相乘预计算
