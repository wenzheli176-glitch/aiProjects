## 1. 字段标签

- [x] 1.1 在 `field_labels.py` 增加 `monitor_run` 分组：run 顶层字段、stats 子键、timing/token 表头键及 help 文案
- [x] 1.2 若项目有 `field-labels.json` 导出流程，确认 Run 新键可被 UI 引用（或在前端内联 map 与 registry 保持一致）

## 2. 模板与样式

- [x] 2.1 `templates/app.html`：右侧 `form-box` 拆分 `#taskFormPanel` 与 `#runDetailPanel`（详情标题栏、概览、stats 网格、分源表占位、错误区、`<details>` glossary 占位）
- [x] 2.2 `static/app.css`：`.run-history-row`、`.run-summary-table`、`.run-detail-*` 状态色与表格样式，与现有 dark theme 一致

## 3. Run 历史交互（panel-intel.js）

- [x] 3.1 移除 `showRunHistory` 的 `alert()`；实现 `runHistoryState` 与 `toggleRunHistory(taskId)`（手风琴展开/收起）
- [x] 3.2 首次展开请求 `GET .../runs?page=1&limit=5`，渲染摘要表；实现 `loadMoreRuns(taskId)` 追加下一页
- [x] 3.3 摘要表行点击 → `selectRun(runId, taskId)` → `GET /api/monitor/runs/{id}` 填充 `#runDetailPanel`
- [x] 3.4 实现 `hideRunDetail()` / 「返回编辑」：恢复 `#taskFormPanel`，与 `editTask`/`resetTaskForm` 行为不冲突
- [x] 3.5 操作列按钮由 `showRunHistory` 改为 `toggleRunHistory`（文案「历史」或保留 Run 但行为为展开）

## 4. 详情面板内容

- [x] 4.1 概览：trigger、analyze_mode、status 标签、started/finished、阶段与总耗时
- [x] 4.2 stats 网格：六项计数 + 中文 label
- [x] 4.3 分源 timing 表与 token 表（含 total 合计行）；failed 时展示 `error_message`
- [x] 4.4 填充 `<details>` 字段 glossary（与 field_labels help 一致）

## 5. 文档与验证清单

- [x] 5.1 更新根目录 `代码说明.md` 监测任务 Run 历史 UI 说明
- [x] 5.2 在 `openspec/verification-pending.md` 增加本 change 手动验证项（见下方 §6）

## 6. 手动验证

- [x] 6.1 创建或选用已有监测任务，执行至少 2 次 manual run，点击「历史」展开：默认显示 ≤5 条，摘要列完整
- [x] 6.2 当 total>5 时点击「加载更多」，较旧 Run 追加显示且不丢失已加载行
- [x] 6.3 点击某 Run 行：右侧切换详情，分源 timing/token 与 stats 与 API JSON 一致；「返回编辑」恢复任务表单
- [x] 6.4 失败 Run：`error_message` 可见；`skipped_overlap` run 状态展示正确
- [x] 6.5 确认全程无 `alert()` 展示 Run 历史；Ctrl+F5 后行为正常
