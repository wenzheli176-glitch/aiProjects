## Why

监测任务在配置中已有 `monitor.task_timeout_sec`（默认 7200 秒），但 `run_monitor_task` 未 enforcement，导致多合作方 × 多源任务可无限期占用 Chrome 与全局 `S.running`（实测单次任务超过 3 小时）。同时 MonitorTask 的 `max_pages` 对黑猫表示 URL 分页页数，对小红书却表示「滚动轮次」，日志与 UI 混用「页/滚动」，同一任务字段语义不一致，运维难以预估采集量与超时边界。

## What Changes

- 在 MonitorRunner 中实现 **任务级超时**：自任务开始计时，超过 `monitor.task_timeout_sec` 后优雅停止当前爬取、标记任务失败或 `timeout` 状态，并释放 `S.running` 与 CDP。
- **统一 `max_pages` 语义**：MonitorTask 与 CrawlAdapter 层对 heimao、xhs 均将 `max_pages` 定义为「结果采集页数/轮次」；小红书仍通过滚动加载更多结果，但对外日志、进度与文档与黑猫一致使用「第 N/M 页」。
- 修正小红书 `crawl_xhs` 起始日志（「滚动 N 次」→「N 页」），并在每页采集前执行与后续页一致的滚动预热（可配置 `xhs.scroll_times_per_page`），使第 1 页与第 N 页行为对称。
- 看板与 `代码说明.md` 更新页数字段说明；**不**改变 MonitorTask API 字段名（仍为 `max_pages`）。
- 单次调试爬取（`/api/crawl_heimao`、`/api/crawl_xhs`）继续允许各源独立默认页数，但函数参数语义与监测任务对齐。

## Capabilities

### New Capabilities

- （无）本变更为既有监测与源适配能力的补全与语义统一，不引入新顶层 capability。

### Modified Capabilities

- `intel-pipeline`：MonitorRunner 必须在 `task_timeout_sec` 内完成或中断；超时后任务状态、进度与日志须可观测。
- `source-adapter`：`max_pages` 对 heimao/xhs 的契约统一为「采集页数」；xhs CrawlAdapter 日志与 `page` 字段须与黑猫分页语义一致。

## Impact

**站点与模块**

| 区域 | 影响 |
|------|------|
| heimao | 无行为变更；作为 `max_pages` 语义基准 |
| xhs | `crawl_xhs` 日志与每页采集逻辑调整；`page` 字段含义与黑猫对齐 |
| login_gate | 无变更 |
| 共用 | `intel/runner.py` 超时 enforcement；`crawler_web.py` 爬取循环配合 `S.running` 中断 |

**config.json 字段**

| 字段 | 变更 |
|------|------|
| `monitor.task_timeout_sec` | 已有，从未 enforcement → 本次实现 |
| `monitor.default_max_pages` | 无结构变更；文档明确为两源共用语义 |
| `xhs.scroll_times_per_page` / `scroll_pixels` / `scroll_wait_seconds` | 无新增；第 1 页起同样用于加载该页可见结果 |

**API / UI**

- `POST/PUT /api/monitor/tasks` 的 `max_pages` 含义文档化统一
- 看板任务表单标签「页数」对两源一致
- 任务失败时 `error_message` 可含 `任务超时（task_timeout_sec=…）`

**非目标**

- 不引入 per-source 独立 `max_pages` 字段（MonitorTask 仍单一值）
- 不改变 AI 分析阶段超时（仅爬取阶段或全任务 — 见 design.md 决策）
- 不新增定时调度
