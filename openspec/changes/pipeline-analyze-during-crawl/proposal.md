## Why

监测 Run 当前将爬取（含 list_triage、investigation）与 AnalyzePipeline **完全串行**：Chrome 在勘察详情时 LLM 空闲，analyze 阶段又要等全部 crawl 结束才开始，wall-clock 显著拉长。用户希望在 **同一 Run 内** 对已 `detail` 且未分析的 raw 尽早打标，并与爬取重叠执行；同时保留定时兜底与 crawl 中手动增量 AI，且不分析仍为 `list` 阶段的数据。

## What Changes

- **Analyze Drain（Run 内自动）**：investigation **每批完成** 后立即 drain 一批「`crawl_phase=detail` 且 incremental 规则下待分析」的 raw，调用现有 `analyze_candidates`（incremental）；Run 收尾 analyze 改为 **仅补漏**（处理 drain 遗漏/失败项），避免重复全量扫描。
- **定时兜底 Drain**：Run 进行中按可配置间隔（如 60s）再次扫描待分析 detail raw，覆盖 investigation 失败、进程中断恢复、drain 异常遗漏等场景。
- **候选严格过滤**：Analyze Drain MUST 仅包含 `crawl_phase=detail`（及 heimao legacy 已具备有效详情 body 的等价情形）；`list` 阶段 raw MUST NOT 进入 drain（含 list_triage 已标记 medium/high 但未勘察者）。
- **去重标记**：沿用 `intel_records` + `raw.updated_at` vs `intel.created_at` 增量语义；drain 与收尾 analyze 共用同一 Run 内 analyze 执行锁，避免双路重复提交同一 raw。
- **crawl 中手动增量 AI**：任务处于 `crawling` 时，允许对 **同一 task** 触发 incremental reanalyze（仅 detail-ready 候选）；与 Run 内 drain 共享 incremental 去重，不阻塞 Chrome Worker。
- **busy 语义调整**：`is_monitor_busy` / `can_reanalyze` 在「同 task + incremental + detail-only」场景下放行；仍禁止 crawl 中启动新的 full_replace 或第二个 monitor Run。
- **进度可观测**：`progress_json` / Run stats 增加 `analyze_drained`、`analyze_pending_detail`、`analyze_during_crawl_ms` 等字段；UI 任务详情展示 crawl 与 analyze 双进度。
- **crawl_only 不变**：`crawl_only=true` 时仍跳过一切自动 drain 与收尾 analyze；手动 incremental AI 仍可用（与现网 reanalyze 一致）。

## Capabilities

### New Capabilities

（无独立新 capability；行为归入现有 pipeline / monitor spec 增量。）

### Modified Capabilities

- `intel-pipeline`：Analyze Drain 触发（批完成 + 定时）、detail-only 候选、Run 收尾补漏、与 investigation 并行约束。
- `monitor-task-runs`：Run progress/stats 双阶段 analyze 指标；crawl 中 incremental reanalyze 语义；analyze 执行锁。
- `unified-web-console`：crawling 态启用「增量 AI」；展示 analyze drain 进度。
- `list-triage-investigation`：investigation 批完成 hook 与 drain 衔接（heimao/xhs 批量路径）。

## Impact

- **intel/runner.py**：`drain_analyze_ready()`、investigation 批后回调、定时 poll、收尾改补漏。
- **intel/investigation.py** / **intel/worker.py** / **intel/worker_pool.py**：批完成触发 drain；on_poll 定时 drain。
- **intel/run_state.py** / **intel/api.py**：busy 规则、`can_reanalyze`、crawl 中 incremental reanalyze API 行为。
- **intel/db.py**：可选 analyze 执行锁表或 Run 级 flag；progress/stats 字段。
- **config.py / config.json**：`monitor.analyze_drain_interval_sec`（定时兜底间隔，默认 60）、`monitor.analyze_during_crawl`（默认 true，可关）。
- **static/panel-intel.js**：crawling 时「增量 AI」可用；双进度展示。
- **docs/API对接说明.md**、**代码说明.md**：文档更新。
- **站点**：heimao / xhs 爬取逻辑不变；analyze 为 HTTP LLM，与 Chrome Worker 无资源冲突；list_triage LLM 与 analyze drain 可能并发，需可配置限流。
