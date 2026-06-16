## MODIFIED Requirements

### Requirement: Intel REST API

系统 SHALL 提供 REST API 供内网系统对接。读接口（GET intel/partners/tasks/sources/status）MVP 阶段 MAY 内网无 Session；**写接口**（配置、名单 CRUD、源 PATCH、Cookie 保存）MUST 要求管理员 Session（`config.admin.enabled=true` 时）。

#### Scenario: 分页查询记录

- **当** 调用 `GET /api/intel/records`
- **则** 必须支持 query 参数：`task_id`、`partner_id`、`source`、`relevance_min`、`since`、`risk_type`、`sentiment_label`、`sentiment_score_min`、`sentiment_score_max`、分页
- **且** `sentiment_label` 与 score 区间同时提供时必须 AND 组合
- **且** 默认返回全量 relevance（由调用方过滤），文档说明高召回策略

#### Scenario: 合作方与任务 API

- **当** 调用 `GET /api/partners` 或 `GET /api/monitor/tasks`
- **则** 必须返回 SQLite 中名单与任务列表
- **且** `POST /api/monitor/run` 必须触发手动监测（见 partner-registry spec）

#### Scenario: 写操作需管理员

- **当** `config.admin.enabled=true` 且调用 `POST /api/config`、`POST /api/partners` 或 `PATCH /api/sources/*`
- **则** 必须验证管理员 Session，否则 403

#### Scenario: 读接口内网可用

- **当** 调用 `GET /api/intel/records` 或 `GET /api/intel/export`
- **则** 不得强制 Session（内网对接场景）
- **且** 文档必须声明写操作已受管理员保护

## ADDED Requirements

### Requirement: 情报列表情感筛选 UI

系统 SHALL 在情报 Tab 筛选栏提供情感 label 下拉与 score 区间输入，并与 API 参数对齐。

#### Scenario: label 筛选

- **当** 用户选择 `sentiment_label=negative`
- **则** 列表 MUST 仅展示匹配 label 的记录

#### Scenario: score 区间筛选

- **当** 用户填写 `sentiment_score_min=-1.0` 与 `sentiment_score_max=-0.3`
- **则** 列表 MUST 仅展示 score 落在闭区间内的记录

#### Scenario: 监测任务筛选不变

- **当** 用户使用现有 `fTask` 选择任务
- **则** 行为 MUST 与变更前一致（`task_id` 过滤）

#### Scenario: 导出透传情感筛选

- **当** 用户在带情感筛选的状态下导出 JSON/Excel
- **则** 导出 MUST 与当前筛选条件一致（全量匹配行，非仅当前页）
