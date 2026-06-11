## Why

监测任务 Run 历史 API 已在 `monitor-runs-schedule-incremental` 中落地，但前端仍用 `alert()` 展示摘要，无法查看分源耗时、Token、统计明细与失败原因。用户需要可浏览、可分页、字段说明清晰的执行历史界面，以支撑运维排查与成本观察。

## What Changes

- 移除 `showRunHistory()` 的 `alert()`，改为任务列表行内展开 Run 摘要表（手风琴）
- 默认加载最近 **5** 条 Run；提供「加载更多」或页码分页查看全部历史
- 点击某条 Run 时，右侧 `form-box` 切换为 **Run 详情面板**（主从布局：列表摘要 + 右侧详尽信息）
- 详情面板展示：基础信息、阶段耗时、`stats` 汇总、分源 `timing_by_source` 表、分源 `token_usage` 表、`error_message`、字段说明（`<details>` 帮助块）
- 在 `field_labels.py` 注册 Run 相关字段中文标签，供 UI 与导出一致
- 无后端 API 变更（复用现有 `GET /api/monitor/tasks/{id}/runs` 与 `GET /api/monitor/runs/{id}`）

## Capabilities

### New Capabilities

（无 — 纯 UI 增强，不引入新 capability）

### Modified Capabilities

- `monitor-task-runs`: 细化 Run 历史 UI 交互（默认 5 条、分页/加载更多、行内展开、右侧详情面板）
- `config-field-labels`: 新增 `monitor_run` 分组字段标签（trigger、analyze_mode、stats 子键等）

## Impact

- **前端**：`static/panel-intel.js`（Run 列表/详情逻辑）、`templates/app.html`（右侧 form-box 增加 Run 详情容器与 Tab 切换）、`static/app.css`（手风琴、详情表格、状态色）
- **字段注册**：`field_labels.py`
- **文档**：`代码说明.md`、本 change 归档后更新 `openspec/verification-pending.md`
- **站点 / config**：无 heimao/xhs/login_gate 行为变更；无 `config.json` 新增键
