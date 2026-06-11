## MODIFIED Requirements

### Requirement: Run 历史 API 与 UI

系统 SHALL 提供 run 列表 API，并在监测任务 UI 以主从布局展示 Run 历史：任务列表行内可展开摘要表，选中 Run 后在右侧面板展示完整耗时、Token、统计与失败原因；默认加载最近 5 条，并支持加载更多或分页查看全部历史。

#### Scenario: 列表查询

- **当** 调用 `GET /api/monitor/tasks/{task_id}/runs`
- **则** 必须按 `started_at` 降序分页返回
- **且** 响应必须含 `total`、`page`、`limit` 与每条 run 的 status、trigger、analyze_mode、duration、stats 摘要

#### Scenario: 行内展开 Run 摘要

- **当** 用户在监测任务列表点击某任务的「历史」或等效控件
- **则** 必须在该任务行下方展开/收起 Run 摘要表
- **且** 首次展开必须请求 `page=1&limit=5`
- **且** 摘要表必须含 run id、开始/结束时间、trigger、analyze_mode、status、总耗时、raw/intel 统计摘要
- **且** 不得使用 `alert()` 展示 Run 历史

#### Scenario: 加载更多或分页

- **当** 该任务 Run 总数 `total` 大于已加载条数
- **则** UI 必须提供「加载更多」或分页控件以获取后续页
- **且** 加载更多必须递增 `page` 并追加展示（不替换已加载的较新记录）

#### Scenario: 右侧 Run 详情面板

- **当** 用户在 Run 摘要表中点击某一条 Run
- **则** 右侧 form-box 必须切换为 Run 详情视图
- **且** 必须调用 `GET /api/monitor/runs/{run_id}` 展示：`stats` 全量字段、分源 `timing_by_source` 表、分源 `token_usage` 表（含 total 合计）、`error_message`
- **且** 必须提供返回任务编辑表单的入口
- **且** 必须含可折叠字段说明（glossary）解释主要 Run 字段含义

#### Scenario: 任务列表展示最近 Run

- **当** 用户打开监测任务列表
- **则** 「最近执行」列必须显示最近 run 时间与总时长（沿用现有 `last_run`）
- **且** 完整分源明细仅在 Run 详情面板展示（不在主表列内嵌）
