## Why

小红书 list_first 模式下，全部 keyword 列表爬完后再批量 triage 与重搜勘察，导致搜索会话断裂、大量 `dom_not_found` 与整轮 `crawl_budget` 超时。监测任务仅有整体状态，失败 keyword 无法单独重跑；数据量大的合作方也无法单独加长某数据源超时。

## What Changes

- **单 keyword 流水线**：每个 keyword 完成列表爬取后立即 list_triage + 同页弹窗勘察，再进入下一 keyword；不再对 xhs 走批量 investigation 重搜。
- **Keyword 子任务**：`monitor_keyword_runs` 表记录每个 keyword 的状态/阶段/统计；任务 `progress.subtasks` 汇总；失败子任务可 `POST /api/monitor/retry-keywords` 单独重跑。
- **合作方源超时**：`partners.source_timeouts_json`（如 `{"xhs":7200,"heimao":3600}`）覆盖单 keyword / 单合作方 legacy 爬取最大 wall-clock；未配置则用 `xhs.keyword_timeout_sec`（默认 3600）或 `heimao.partner_timeout_sec`。
- **控制台**：合作方表单增加 xhs/黑猫超时；Run 详情展示 keyword 子任务表与「重跑失败 keyword」按钮；任务列表显示子任务进度。

## Capabilities

### New Capabilities

- `xhs-keyword-pipeline`：单 keyword list→triage→同页 investigation；Worker `keyword_pipeline` phase；子任务持久化与重跑 API。

### Modified Capabilities

- `partner-registry`：合作方 `source_timeouts` 字段与 API 读写。
- `intel-pipeline`：xhs 跳过批量 post-list investigation；子任务超时解析。
- `unified-web-console`：合作方超时表单、Run keyword 子任务 UI、任务 subtasks 进度。

## Impact

- **后端**：`intel/keyword_pipeline.py`、`intel/source_timeout.py`、`intel/db.py`（schema v9–10）、`intel/crawl_queue.py`、`intel/worker.py`、`intel/runner.py`、`intel/api.py`、`crawler_web.py`（`crawl_xhs_list_with_dom`）
- **前端**：`templates/app.html`、`static/panel-intel.js`
- **配置**：`xhs.keyword_timeout_sec`、`heimao.partner_timeout_sec`
