## Why

Stage 2 已落地 list_first 与弹窗勘察，但生产仍常因 **legacy 全量弹窗**、**单 Chrome 串行**、**Cookie 多实例难维护** 导致单次 Run 耗时过长。多合作方、多源场景下各源耗时差异大，需在 **不触发风控** 前提下并行爬取，并对小红书 **仅对重点内容弹窗详情**（禁止 goto explore）。Stage 3 将引入同机多进程 Worker、源级 crawl 策略、Cookie 管理页与可配置分析并发。

## What Changes

- **数据源级 crawl 策略**：xhs **强制** `list_first`（routine 无详情）；heimao **暂留** `legacy`（可 fetch_detail）。配置在 `source_profiles` / 数据源管理，非任务级覆盖。
- **混合源工作单元**：xhs 为 `keyword_batch × list_crawl`；heimao legacy 为 `partner × legacy_crawl`（**非** keyword_batch）。合作方在 match/triage/analyze 展开。
- **小红书详情**：routine 仅列表；investigation 队列内 **搜索页弹窗**；**禁止** routine 全量弹窗与 goto explore。
- **弹窗上限**：`xhs.investigation_detail.max_modal_per_run`；**Run 级全局计数**；超限 skip 剩余并写 stats。
- **同机多进程 Worker**：heimao legacy Worker 与 xhs list_first Worker **并行** crawl；investigation **按源回派**至对应 Worker；独立 CDP + profile + Cookie 文件。
- **Run 前 Cookie 诊断**：Worker 认领工作前自动 diagnose；单源失败 **partial**（其他源继续），全源失败才 fail Run。
- **Cookie 管理页**：实例上传/诊断/失效横幅；`config.auth` 与 `monitor.workers` 统一映射。
- **Run 级状态机**：`monitor_runs` + `crawl_work_queue` 替代全局 `S.running`；Worker 心跳、queue reclaim、停止广播、登录等待聚合。
- **分析并行**：`analysis.parallel_batches` 默认 **5**。

## Capabilities

### New Capabilities

- `crawl-worker-pool`: 多进程 Worker、双形态 work queue、heimao∥xhs 并行、investigation 按源回派、Run 状态/停止/日志
- `cookie-instance-admin`: Cookie 注入、Run 前 diagnose、管理页、与 `config.auth` 统一

### Modified Capabilities

- `source-adapter`: 源级 crawl_mode；task.crawl_mode 降级为兼容/文档字段
- `list-triage-investigation`: triage 范围、heimao 免 investigation、Run 级弹窗配额
- `intel-pipeline`: parallel_batches；investigation skip 后 analyze 行为
- `monitor-task-runs`: Worker stats、partial failure、新 stats 标签
- `xhs-detail-modal`: max_modal_per_run + profile 白名单
- `monitor-scheduler`: skip_if_running 改查 Run 状态
- `admin-console-auth`: Cookie 上传写权限与路径校验
- `unified-web-console`: Cookie 实例 Tab、登录等待多实例展示

## Impact

- **代码**：`intel/runner.py`、`intel/worker.py`、`intel/crawl_queue.py`、`intel/run_state.py`；`crawler_web.py`、`login_gate.py`、`auth_utils.py`；`intel/api.py`、`intel/scheduler.py`；`source_profiles.py`；UI panels
- **config**：`monitor.workers.*`、`monitor.run_state.*`、`analysis.parallel_batches`、`xhs.investigation_detail.max_modal_per_run`
- **DB**：`crawl_work_queue`、`worker_heartbeats`（或 run 内嵌 JSON）；`monitor_tasks.crawl_mode` 迁移说明
- **非目标**：跨机器 Worker；heimao 迁 list_first；goto explore 兜底
