## Why

监测任务 #100000 在 `task_timeout_sec=7200` 配置下约 5 分钟即失败，routine 爬取（含 heimao ∥ xhs Worker）未完成，导致 list_triage / investigation（小红书弹窗详情）从未执行。根因是 `analysis_timeout_sec` 与 `task_timeout_sec` 同为 7200 时，爬取阶段实际预算被压缩至约 300 秒，且错误信息误导用户以为整任务跑了 7200 秒才超时。

## What Changes

- 修正 `run_monitor_task` 爬取/分析超时预算分配：保证爬取阶段有合理最小时长，避免 `analysis_timeout_sec ≥ task_timeout_sec` 时爬取仅 5 分钟。
- 区分 **爬取阶段超时** 与 **整任务超时** 的 `error_message`、日志与 `progress.reason`（如 `crawl_timeout` / `timeout`）。
- 配置约束：`analysis_timeout_sec` 不得超过 `task_timeout_sec` 的可分配上限；提供 `monitor.min_crawl_timeout_sec`（或等价机制）作为爬取保底。
- 更新 `config.json` / `config.json.example` 默认值：`analysis_timeout_sec` 小于 `task_timeout_sec`（如 3600 vs 7200）。
- 文档与 UI 提示：`analysis_timeout_sec` 为分析预留，会从总时长中扣除，影响爬取可用时间。
- 单元测试覆盖预算计算与边界配置。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `intel-pipeline`：MonitorTask 任务超时需求扩展为「爬取/分析分阶段预算 + 可观测错误语义」，替代当前仅按 `task_timeout_sec` 描述 crawling 超时的模糊行为。

## Impact

- **代码**：`intel/runner.py`（`crawl_deadline` / `timeout_check` / `_timeout_message`）、可选 `config.py` 校验
- **配置**：`monitor.task_timeout_sec`、`monitor.analysis_timeout_sec`、新增 `monitor.min_crawl_timeout_sec`（待定名，design 定稿）
- **站点**：heimao / xhs 共用监测编排；超时修复后 investigation 弹窗阶段才有机会执行（行为不变，仅不再被提前掐断）
- **UI/API**：Run 失败原因、任务 `progress` JSON；系统设置超时字段说明
- **文档**：`代码说明.md` 或 `DEPLOY.md` 中 monitor 超时章节
