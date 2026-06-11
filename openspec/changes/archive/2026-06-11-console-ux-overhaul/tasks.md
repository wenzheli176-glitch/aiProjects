## P0 — Design System（ui-shell + 浅色主题）

- [x] 0.1 新增 `static/ui-shell.js`：`UiModal`、`UiDrawer`、`UiToast`、`UiConfirm`（backdrop、ESC、关闭）
- [x] 0.2 `static/app.css`：浅色 CSS variables；重构 header/card/table/tag/button 适配浅底
- [x] 0.3 `templates/app.html`：引入 `ui-shell.js`；移除主要 inline 深色 style（分批）
- [x] 0.4 `app-core.js`：统一 `App.readQuery()` / `App.setQuery()` / `App.switchAppTab` 支持 home/intel_id/raw_id/run_id

## P1 — 首页看板

- [x] 1.1 `intel/db.py` + `intel/api.py`：`GET /api/dashboard/summary` 聚合
- [x] 1.2 `templates/app.html`：新增 `panel-home` Nav 第一项；KPI 卡片 + 最近 Run 表
- [x] 1.3 `static/panel-home.js`（或 panel-intel 内）：加载 summary、卡片钻取 query
- [x] 1.4 `/dashboard` redirect 改为 `/?tab=home`；默认 Tab 为 home

## P2 — 情报中心布局 + 详情页

- [x] 2.1 情报 Tab：筛选条移至列表上方（去掉 `.grid` 左栏）
- [x] 2.2 情报列表 + 详情页双视图：`intel_id` query；返回保留 filter
- [x] 2.3 详情页：全文、三时间、跳转 raw/intel 关联
- [x] 2.4 导出按钮文案「导出当前筛选结果」；确认 export API 忽略 page 全量（回归 intel export）

## P3 — 源数据 Tab + API

- [x] 3.1 `intel/db.py`：`list_raw_records_paged`；分析状态字段
- [x] 3.2 `intel/api.py`：`GET /api/raw/records`、`GET /api/raw/records/{id}`
- [x] 3.3 新增 `intel/export_raw.py`（或扩展 export）：`GET /api/raw/export` json/csv/xlsx，filter 全量
- [x] 3.4 `panel-raw.js` + Nav「源数据」：摘要列表、详情页 `raw_id`、导出、跳转 intel

## P4 — Modal 表单（合作方 + 监测任务）

- [x] 4.1 合作方 Tab：去掉 split form-box；列表全宽；添加/编辑 Modal
- [x] 4.2 监测任务 Tab：去掉 split form-box 与 `#taskFormPanel`；创建/编辑 Modal（含 SchedulePicker）
- [x] 4.3 移除 `#runDetailPanel` 占位（Run 迁 P5 Drawer）

## P5 — Run Drawer + stats 说明

- [x] 5.1 Run 摘要行点击 → `UiDrawer` 展示详情（迁移现有 fillRunDetailPanel 逻辑）
- [x] 5.2 stats 网格：数字 + label + help 常显；保留 glossary
- [x] 5.3 支持 `?tab=tasks&run_id=` 深链打开 Drawer

## P6 — 数据源 Tab + 全站交互排查

- [x] 6.1 `app-sources.js`：heimao/xhs Tab 切换 UI
- [x] 6.2 采集调试/系统/大模型：浅色适配 + 表格 responsive
- [x] 6.3 排查并替换主要 `alert()`/`confirm()`（panel-intel、crawl、sources）
- [x] 6.4 更新 `代码说明.md`；`openspec/verification-pending.md` 增加 § 手动验证

## 7. 手动验证

- [x] 7.1 访问 `/` 默认 home；看板 KPI 点击跳转 intel 且 filter 正确
- [x] 7.2 情报：筛选在上、详情页 `intel_id` 深链、返回保留筛选；导出当前筛选全量
- [x] 7.3 源数据：列表无 payload 全文；详情页全文；导出 json/xlsx；跳转 intel
- [x] 7.4 合作方/任务 Modal 创建编辑；任务页全宽无右栏表单
- [x] 7.5 Run Drawer：展开历史、点击 Run、stats 含义可见；`run_id` 深链
- [x] 7.6 数据源 heimao/xhs Tab 切换保存生效
- [x] 7.7 窄屏（≤900px）主要 Tab 可用；全站浅色无深色残留块
- [x] 7.8 `/dashboard` → home；login_wait 横幅各 Tab 仍可见
