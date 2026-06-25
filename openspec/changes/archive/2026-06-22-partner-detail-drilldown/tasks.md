## 1. 后端 API

- [x] 1.1 `intel/db.py`：实现 `get_partner_drilldown_context(partner_id)`（default_task_id、tasks、counts）
- [x] 1.2 `intel/api.py`：`GET /api/partners/<id>/context`
- [x] 1.3 单元测试 `scripts/test_partner_drilldown_context.py`（有任务/无任务/计数）

## 2. 前端导航与 URL

- [x] 2.1 `app-core.js`：`App.navigatePartnerDetail(partnerId, opts)`；query 键 `partner_id`、`partner_tab`、`task_id`
- [x] 2.2 `panel-intel.js`（或 `panel-partners.js`）：`onPartnersTabActivate` 读取 query，列表/详情切换
- [x] 2.3 合作方列表行增加「查看情报」「查看源数据」按钮，分别打开对应子 Tab

## 3. 合作方详情 UI

- [x] 3.1 `app.html`：`partnerListView` / `partnerDetailView`、子 Tab 栏、情报/源数据 pane 容器
- [x] 3.2 情报子 Tab：嵌入列表（partner 固定、`relevance_min=medium`）、跳转 `intel_id` 详情
- [x] 3.3 源数据子 Tab：任务下拉（来自 context.tasks）、列表请求带 `partner_id`+`task_id`、跳转 `raw_id`
- [x] 3.4 空态：无关联任务 / 无 raw / 无 intel 的文案与引导
- [x] 3.5 `app.css`：子 Tab 与详情顶栏样式

## 4. 文档

- [x] 4.1 更新 `代码说明.md`：合作方详情深链、context API、按钮行为

## 5. 手动验证

- [x] 5.1 列表「查看情报」→ 详情情报 Tab，仅该合作方 medium+ 数据
- [x] 5.2 列表「查看源数据」→ 详情源数据 Tab，URL 含 task_id，切换任务生效
- [x] 5.3 刷新页面深链 `?tab=partners&partner_id=&partner_tab=raw&task_id=` 状态保持
- [x] 5.4 返回列表清除 partner 相关 query
- [x] 5.5 验证完成后 `python scripts/sync_verification_tasks.py push`
