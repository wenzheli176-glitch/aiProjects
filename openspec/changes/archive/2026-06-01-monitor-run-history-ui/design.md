## Context

后端已提供：

- `GET /api/monitor/tasks/{task_id}/runs?page=&limit=` → `{ ok, runs[], total, page, limit }`
- `GET /api/monitor/runs/{run_id}` → `{ ok, run }`（含 `timing_by_source`、`token_usage`、`stats`、`error_message`）

当前 `static/panel-intel.js` 中 `showRunHistory(task_id)` 调用 `limit=8` 后用 `alert()` 拼接文本。监测任务 Tab 为 `split` 布局：左侧任务表 + 右侧 `form-box`（创建/编辑任务表单）。

用户已确认：

1. **主从布局**：行内 Run 摘要（A）+ 选中 Run 时右侧详情面板（B）
2. **默认 5 条**，需「加载更多」或分页查看全部
3. **详情要详尽**，含字段说明

## Goals / Non-Goals

**Goals:**

- 任务行可展开/收起 Run 摘要表（ID、时间、触发、模式、状态、总耗时、raw/intel 摘要）
- 首次展开请求 `page=1&limit=5`；不足 `total` 时显示「加载更多」（追加 `page++`）或简易分页控件
- 点击 Run 行：右侧 `form-box` 切到 Run 详情视图；提供「返回编辑任务」回到表单
- 详情分块：概览卡片、stats 网格、分源 timing 表、分源 token 表、错误区、可折叠字段 glossary
- Run 字段中文标签写入 `field_labels.py`（group=`monitor_run`）

**Non-Goals:**

- 新 API、WebSocket 实时推送、analysis_job_logs 批次明细钻取
- Modal/Drawer 全屏弹层（沿用现有 split + form-box）
- 在任务列表列中嵌入完整分源表（仅摘要表 + 右侧详情）

## Decisions

### D1 行内手风琴 + 右侧详情（Master-Detail）

在 `taskTableBody` 每行后插入可折叠 `<tr class="run-history-row">`， colspan 覆盖全表。展开时渲染摘要 `<table class="run-summary-table">`。

选中 Run 时调用 `showRunDetail(run_id)`：

- 隐藏 `#taskFormPanel`（任务创建/编辑）
- 显示 `#runDetailPanel`
- `GET /api/monitor/runs/{id}` 填充详情

「返回编辑」或 `editTask` / `resetTaskForm` 时恢复任务表单视图。

**备选**：Modal 弹窗 — 拒绝，与现有 split 不一致且信息密度不足。

### D2 分页策略：「加载更多」优先

状态 per task：`runHistoryState[taskId] = { page, limit: 5, total, runs[], loading }`。

- 首次展开：`page=1, limit=5`
- 「加载更多」：`page++`，append 到 `runs[]`（API 按 id DESC，下一页为更旧记录）
- 当 `runs.length >= total` 隐藏按钮
- 可选：在 total 较大时显示「第 x/y 页」meta 与「上一页/下一页」（与加载更多二选一或并存 — 实现采用 **加载更多 + 页码只读提示**）

默认 `limit=5`（用户指定）；替换现有 `limit=8` alert 调用。

### D3 详情面板信息架构

区块顺序（自上而下）：

| 区块 | 内容 |
|------|------|
| 标题栏 | Run #id · 任务名 · status 标签 · 「返回编辑」 |
| 概览 | trigger、analyze_mode、started_at、finished_at、crawl/analyze/total 耗时 |
| 统计 stats | raw_new、raw_updated、raw_unchanged、intel_written、intel_replaced、intel_skipped（网格 + 中文 label） |
| 分源 timing | 表：source、crawl_ms、analyze_ms、raw_new、raw_updated、intel_written |
| 分源 token | 表：source、prompt_tokens、completion_tokens、total_tokens；合计行来自 `token_usage.total` |
| 错误 | `error_message`（failed/skipped 时高亮） |
| 字段说明 | `<details>` 折叠 glossary（链接 field_labels help 文案） |

状态色复用现有 `.tag` / status 样式：`done` 绿、`failed` 红、`skipped_overlap` 灰、`running` 蓝。

### D4 字段标签

在 `field_labels.py` 增加 `monitor_run` 分组，键覆盖 run 顶层与 `stats.*` 常用子键。前端 `runFieldLabel(key)` 读取内联 map 或 `/static/field-labels.json`（若已有加载逻辑则复用）。

不新增 `config.json` 键。

### D5 HTML 结构变更

`templates/app.html` 右侧 `form-box` 内：

```html
<div id="taskFormPanel">…现有表单…</div>
<div id="runDetailPanel" style="display:none">…详情占位…</div>
```

JS 模块函数：`toggleRunHistory(taskId)`、`loadMoreRuns(taskId)`、`selectRun(runId, taskId)`、`showRunDetail(runId)`、`hideRunDetail()`。

操作列「Run」按钮改为「历史」或保留文案但绑定 `toggleRunHistory`（展开/收起，非 alert）。

## Risks / Trade-offs

- **[Risk] 手风琴行破坏表格 zebra 样式** → 使用 `.run-history-row td` 深色背景与内嵌 table 区分层级
- **[Risk] 编辑任务与查看 Run 详情右栏互斥导致用户困惑** → 标题栏明确「Run 详情」+「返回编辑」；展开历史不自动切换右栏，仅点击 Run 行才切换
- **[Risk] 多次加载更多导致 DOM 过长** → 默认 5 条 + 按需加载；total 很大时仍可控
- **[Trade-off] 不展示 analysis_job_logs** → MVP 以 run 级汇总为准；批次明细留后续 change

## Migration Plan

1. 部署静态资源 + 模板；无需 DB 迁移
2. 用户 Ctrl+F5 强刷；无服务重启硬性要求（模板变更需重启 Flask）
3. 回滚：恢复 `panel-intel.js` 与 `app.html` 片段即可

## Open Questions

- （无 — 用户已确认布局、默认条数与详尽展示）
