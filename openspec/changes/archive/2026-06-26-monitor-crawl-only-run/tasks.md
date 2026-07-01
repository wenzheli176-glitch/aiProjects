## 1. 数据模型与配置

- [x] 1.1 `intel/db.py`：`monitor_task_runs` 增加 `crawl_only` 列（DEFAULT 0）；`create_task_run` / `get_task_run` / Run API 序列化支持
- [x] 1.2 `intel/db.py`：监测任务读写 `crawl_only`（`business_spec_json` 同级字段或 tasks 表列，与现网 JSON 模式一致）
- [x] 1.3 `config.py` / `config.json.example`：可选 `monitor.default_crawl_only`（默认 false）

## 2. 超时与编排

- [x] 2.1 `intel/timeout_budget.py`：`compute_monitor_deadlines(..., crawl_only=False)`；crawl_only 时 `analysis_reserve_sec=0`
- [x] 2.2 `intel/runner.py`：`run_monitor_task(..., crawl_only=False)`；爬取成功后分支跳过 `_run_analysis_phase`
- [x] 2.3 `intel/runner.py`：crawl_only 结束时写入 `stats_json.analyze_deferred`、`pending_analyze_raw_count`；progress `crawl_done` + `analyze_pending`
- [x] 2.4 `intel/runner.py`：resume / keyword retry / continue 路径继承原 run `crawl_only`
- [x] 2.5 抽取 `_count_pending_analyze_raw(task_id, ...)` 复用 `_build_candidates_from_raw` 过滤逻辑（仅计数）

## 3. API 与调度

- [x] 3.1 `intel/api.py`：`POST /api/monitor/run` 解析 `crawl_only`；与 `full_replace` 互斥返回 400
- [x] 3.2 `intel/api.py`：任务 CRUD 读写 `crawl_only`；enrich 任务列表 `can_reanalyze` 在 crawl_only done 后仍为 true
- [x] 3.3 `intel/scheduler.py`：定时触发传入 `task.crawl_only`
- [x] 3.4 `docs/API对接说明.md`：文档 `crawl_only` 参数与 Run stats 字段

## 4. 前端

- [x] 4.1 `static/panel-intel.js`：任务 Modal「仅爬取」checkbox；保存/加载任务
- [x] 4.2 `static/panel-intel.js`：`runTaskById` / 执行确认传递 `crawl_only`；tooltip 文案
- [x] 4.3 `static/panel-intel.js`：Run 历史/详情「待分析」tag + 快捷「增量 AI」
- [x] 4.4 `static/app.css`（若需）：待分析状态样式

## 5. 测试与文档

- [x] 5.1 `scripts/test_crawl_only_run.py`：mock 路径验证 skip analyze、stats 字段、timeout budget
- [x] 5.2 更新 `代码说明.md` Run 编排与 API 小节
- [x] 5.3 `openspec/verification-pending.md` 登记手动验证：crawl_only Run 完成后 reanalyze 产出 intel

## 6. 手动验证（Chrome）

- [x] 6.1 勾选「仅爬取」执行混合源任务：Run 在 crawl 后结束，无 analyzing 阶段，Chrome 已释放
- [x] 6.2 对同一任务点「增量 AI」：intel 正常写入，与 crawl_only Run 解耦
- [x] 6.3 crawl_only + `task_timeout_sec` 有限：爬取可用时间大于非 crawl_only 同配置（无 analysis 预留）
