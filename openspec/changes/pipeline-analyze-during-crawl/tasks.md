## 1. 配置与候选过滤

- [x] 1.1 `config.py` / `config.json.example`：新增 `monitor.analyze_during_crawl`（默认 true）、`monitor.analyze_drain_interval_sec`（默认 60）
- [x] 1.2 `intel/runner.py`：`_should_analyze_raw(..., detail_only=True)` 仅 `crawl_phase=detail`（及 heimao legacy 有效详情）；`_build_candidates_from_raw` 支持 detail_only 参数
- [x] 1.3 `intel/db.py`：`count_detail_pending_analyze(task_id)` 供 progress/stats 使用

## 2. Analyze Drain 核心

- [x] 2.1 新增 `drain_analyze_ready()`（`intel/runner.py` 或 `intel/analyze_drain.py`）：incremental 候选 → analyze 锁 → `analyze_candidates` → 更新 progress
- [x] 2.2 Run 级 analyze 执行锁（threading.Lock 或 DB flag），batch/timer/manual 互斥
- [x] 2.3 `run_monitor_task` 收尾：非 crawl_only 时仅对 remaining detail pending 调用 `_run_analysis_phase`（补漏）

## 3. 双触发挂载

- [x] 3.1 `intel/investigation.py` `process_investigation_batch` 返回后触发 batch drain（respect crawl_only / analyze_during_crawl）
- [x] 3.2 `intel/keyword_pipeline.py`：xhs 同页勘察批完成后触发 batch drain
- [x] 3.3 `intel/worker_pool.py` / `run_investigation_crawl` on_poll：定时 drain（`last_drain_at` 节流）
- [x] 3.4 `sync_task_subtask_progress` / `update_task_status`：写入 `progress.analyze_drain` 与 stats 字段

## 4. busy 语义与 API

- [x] 4.1 `intel/run_state.py`：`is_monitor_busy` 或等价 helper 支持 crawling 态同 task incremental reanalyze
- [x] 4.2 `intel/api.py`：`enrich_task_row` 更新 `can_reanalyze`；`POST /api/monitor/reanalyze` crawling + incremental 放行，full_replace 拒绝
- [x] 4.3 `reanalyze_monitor_task` 复用 `drain_analyze_ready(trigger=manual)` 与 detail_only 过滤

## 5. analyze 并行与限流

- [x] 5.1 评估并调整 `intel/analyze.py` 非主线程 `parallel_batches=1` 限制（during-crawl drain 路径）
- [x] 5.2 可选：`monitor.analyze_drain_max_batches_per_tick` 防止 LLM 与 list_triage 叠加过载

## 6. UI

- [x] 6.1 `static/panel-intel.js`：crawling 态启用「增量 AI」；展示 `analyze_drain` 双进度（勘察 + 分析）
- [x] 6.2 crawling 态禁用「全量重分析」并 tooltip 说明

## 7. 测试与文档

- [x] 7.1 `scripts/test_analyze_drain.py`：detail_only 过滤、incremental 去重、mock drain 不分析 list
- [x] 7.2 `scripts/test_analyze_drain.py`：busy 规则 — crawling 允许 incremental reanalyze、禁止 full_replace
- [x] 7.3 更新 `docs/API对接说明.md`、`代码说明.md`
- [x] 7.4 `openspec/verification-pending.md` 登记手动验证：Run 内 investigation 与 analyze 重叠 wall-clock、定时兜底、手动增量 AI
