## Why

合作方 Tab 目前只有编辑/启停/删除，风控同学查看某企业的情报或源数据需手动切 Tab 再在下拉框里找合作方（源数据还需再选任务）。列表与数据之间缺少一键钻取，操作路径长、易选错任务。

## What Changes

- **合作方列表**：每行增加两个独立按钮——**查看情报**、**查看源数据**（与编辑/删除并列）。
- **合作方详情页**：在「合作方」Tab 内新增列表/详情双视图；详情含 **情报 / 源数据** 两个子 Tab（对应按钮默认打开的目标 Tab）。
- **源数据带 task_id**：打开源数据子 Tab 时 MUST 自动带上该合作方**最近关联的监测任务** `task_id`（可切换任务）；无关联任务时展示空态说明。
- **情报子 Tab**：默认 `relevance_min=medium`，列表复用现有 `/api/intel/records` 筛选。
- **后端**：`GET /api/partners/{id}/context` 返回默认 `task_id`、关联任务列表、intel/raw 计数摘要。
- **URL 深链**：`?tab=partners&partner_id={id}&partner_tab=intel|raw`（源数据 Tab 可含 `task_id` query）。

## Capabilities

### New Capabilities

（无新 capability 目录。）

### Modified Capabilities

- `partner-registry`：合作方钻取上下文 API、与监测任务关联解析规则。
- `unified-web-console`：合作方列表操作按钮、合作方详情子 Tab、URL query 约定。
- `raw-records-api`：合作方详情内嵌源数据列表的 task_id 必选语义。
- `risk-dashboard-export-api`：合作方详情情报子 Tab 与现有 intel 筛选/export 对齐（文档级，无新端点）。

## Impact

- **前端**：`templates/app.html`、`static/panel-intel.js`（或拆出 `panel-partners.js`）、`static/app-core.js`（`navigatePartnerDetail`）、`static/app.css`
- **后端**：`intel/api.py`、`intel/db.py`（`get_partner_drilldown_context`）
- **文档**：`代码说明.md`
