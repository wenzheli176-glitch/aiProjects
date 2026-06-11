## Why

统一 Web 控制台当前为深色 split 布局（列表 + 右侧表单），监测看板筛选在侧栏、无首页汇总、无源数据浏览 API，Run 详情占右栏且部分交互仍用 `alert()`。用户需要科技感浅色、自适应、列表摘要 + 独立详情页、Modal 表单、Run Drawer，以及看板可钻取情报列表，以支撑日常运维与排查。

## What Changes

- **默认入口**：`/` 默认 Tab 为 **首页看板**；看板 KPI/区块可点击，带 query 跳转情报列表或任务/Run
- **浅色主题**：一次性全站浅色 design tokens，移除硬编码深色 inline 样式
- **共享 UI 组件**：`UiModal` / `UiDrawer` / `UiToast` / `UiConfirm`；逐步替换 `alert()` / `confirm()`
- **列表 + 详情原则**：列表仅摘要；情报与源数据用 **独立详情页**（`intel_id` / `raw_id` query）；Run 用 **Drawer**
- **监测看板**：快捷筛选移至情报列表 **上方**；支持详情页深链与返回保留筛选
- **源数据 Tab**：新增 raw 列表、详情页、**当前筛选条件下全量导出**（json/csv/xlsx）
- **表单 Modal 化**：合作方、监测任务创建/编辑改为 Modal；任务页全宽列表，移除 split `form-box`
- **Run 历史**：Run 详情从右栏迁至 Drawer；stats 字段 inline 含义说明
- **数据源 Tab**：heimao / xhs 切换编辑（替代纵向 card 堆叠）
- **响应式**：表格、Nav、Modal/Drawer 在小屏可用
- **后端 API**：`GET /api/dashboard/summary`；`GET /api/raw/records`、`GET /api/raw/records/{id}`、`GET /api/raw/export`
- **BREAKING**：`/dashboard` 重定向目标由 `/?tab=intel` 改为 `/?tab=home`（或 `/` 默认 home）

## Capabilities

### New Capabilities

- `home-dashboard`：首页 KPI、可点击钻取、summary API
- `raw-records-api`：raw 分页列表、单条详情、按筛选全量导出

### Modified Capabilities

- `unified-web-console`：Nav 顺序、默认 Tab、浅色主题、Modal/Drawer、responsive、交互规范
- `risk-dashboard-export-api`：看板布局、情报独立详情页、导出语义（当前筛选全量）
- `monitor-task-runs`：Run Drawer、任务页全宽、stats 字段 inline 说明

## Impact

- **前端**：`templates/app.html`、`static/app.css`、新增 `static/ui-shell.js`；`panel-intel.js`、`app-sources.js`、`app-core.js` 大改；可能拆分 `panel-home.js`、`panel-raw.js`
- **后端**：`intel/api.py`（dashboard、raw CRUD/export）；`intel/db.py`（raw 分页查询）；`intel/export_intel.py` 或新 `export_raw.py`
- **文档**：`代码说明.md`、可选 `docs/console-ux.md`
- **站点 / config**：无 heimao/xhs 爬取逻辑变更；无 `config.json` 新增 auth.* / heimao.* / xhs.* 键
- **OpenSpec 验证**：完成后更新 `openspec/verification-pending.md`
