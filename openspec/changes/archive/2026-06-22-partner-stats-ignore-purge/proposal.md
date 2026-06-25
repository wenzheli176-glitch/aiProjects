## Why

合作方列表无法一眼看出情报与源数据规模，需点进详情才知道是否有数据；监测任务缺少「忽略早于某日内容」的配置，历史噪声仍会进入 AI 分析；管理员也无法按任务/合作方/时间批量清理 raw 或 intel，只能删整任务或全量重分析。

## What Changes

- **合作方列表统计**：`GET /api/partners` 每条返回 `stats`（情报中+/总数、源数据数）；源数据计数与详情一致（**default_task**）；列表列可点击钻取详情对应子 Tab。
- **任务忽略时间**：监测任务 `business_spec.ignore_before`（YYYY-MM-DD）；爬取 **照常入库**，分析阶段若 `published_at` 早于该日则 **跳过**；`published_at` 为空则 **不比较、仍分析**。
- **管理员批量清理**：`POST /api/admin/purge/raw` 与 `POST /api/admin/purge/intel`（`@require_admin`）；**`task_id` 必填**；可选 `partner_id`、`published_before`；支持 `dry_run` 预览条数；Web 在任务 Tab / 合作方详情提供清理入口。

## Capabilities

### New Capabilities

- `admin-data-purge`：管理员按任务（及可选合作方、发布时间）批量清理 raw / intel，含 dry-run 与权限约束。

### Modified Capabilities

- `partner-registry`：`GET /api/partners` 内联 stats；与 `get_partner_drilldown_context` 计数规则对齐。
- `business-system-integration`：任务级 `business_spec.ignore_before` 持久化与 run 读取。
- `intel-pipeline`：`_build_candidates_from_raw` 应用 ignore_before；run_metrics 可观测跳过数。
- `admin-console-auth`：purge API 须管理员 Session。
- `unified-web-console`：合作方列表统计列、任务 ignore_before 表单、管理员清理 Modal。

## Impact

- **后端**：`intel/db.py`（`list_partners_with_stats`、purge 函数）、`intel/runner.py`（ignore 过滤）、`intel/api.py`（partners 响应、purge 路由）、`intel/run_metrics.py`（可选 skip 计数）
- **前端**：`static/panel-intel.js`、`templates/app.html`（任务表单、列表列、清理 Modal）、`static/app.css`
- **文档**：`代码说明.md`、`docs/API对接说明.md`（purge 与 ignore_before）
- **站点**：无 heimao/xhs 爬虫逻辑变更；仅分析管线与 Web/API
- **config.json**：无新增 auth/heimao/xhs 字段（ignore_before 存任务 `business_spec_json`）
