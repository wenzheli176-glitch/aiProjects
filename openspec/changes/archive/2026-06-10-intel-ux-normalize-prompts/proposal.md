## Why

统一控制台已合并监测、数据源与大模型配置，但情报时间语义不清（看板仅一列「时间」）、数据源清洗逻辑不可配置、配置项以英文键名展示可读性差，且 Prompt 仅单条字符串无法版本化管理。用户已明确：采集时间取 `raw_records.created_at`，清洗先暴露关键开关，Prompt 存 SQLite，中文标签全站统一。

## What Changes

- 情报 `captured_at` 在 pipeline 中 MUST 透传 `raw_records.created_at`；看板/API/导出分列展示 **发布时间**、**采集时间**、**生成时间**（`intel_records.created_at`）。
- 数据源 Tab 增加 **清洗/归一化** 配置区（heimao/xhs 各若干开关与关键参数），写入 `config.{source}.normalize.*`，由 `NormalizeAdapter` 读取。
- 新增全站 **字段标签注册表**（中文（english_key）），应用于数据源、系统设置、大模型、监测看板表头等 Web 表单。
- 新增 SQLite **`prompt_templates`** 表与 REST API：多版本 Prompt CRUD、设活跃版本、大模型 Tab 回显当前生效 Prompt（含内置默认）。
- `config.analysis.active_prompt_id` 指向活跃模板；分析写入 `intel_records.prompt_version` 仍为模板标识，便于审计。

## Capabilities

### New Capabilities

- `config-field-labels`: 全站配置字段元数据（label、group、type、help），UI 统一渲染中文（英文键）。
- `prompt-version-store`: SQLite Prompt 模板库、活跃版本切换、API 与看板集成。

### Modified Capabilities

- `intel-pipeline`: 采集时间语义、`captured_at` 赋值规则、生成时间暴露。
- `source-adapter`: 源级 normalize 配置块与白名单 API/UI。
- `risk-dashboard-export-api`: 看板情报列表时间列与导出字段对齐。

## Impact

- **站点**: heimao、xhs NormalizeAdapter；共用 `intel/runner.py`、`intel/db.py`。
- **config.json 新增**:
  - `heimao.normalize.*` — 如 `include_reply_in_body`、`include_merchant_in_body`、`body_max_chars`、`strip_html`
  - `xhs.normalize.*` — 如 `body_max_chars`、`include_likes_in_extra`、`fallback_title_from_body`
- **SQLite**: `prompt_templates` 表；`intel_records` 无需改列（沿用 `captured_at`、`created_at`）。
- **API**: `GET/PATCH /api/sources/{id}/profile` 扩展 normalize 键；新增 `/api/analysis/prompts*`；Intel API 响应含 `captured_at`、`analyzed_at`（或 `created_at` 别名文档化）。
- **前端**: `static/field-labels.js`（或 JSON）、`app-sources.js`、`panel-intel.js`、`panel-crawl.js`、大模型 Tab。
- **文档**: `代码说明.md`、`docs/API对接说明.md`。
