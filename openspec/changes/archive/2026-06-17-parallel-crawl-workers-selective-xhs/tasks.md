## 1. 源级 crawl_mode + 混合源单进程（Phase A）

- [x] 1.1 `source_profiles.py` / `config.sources.*`：`crawl_mode`、`allowed_modes`；xhs 强制 list_first
- [x] 1.2 `intel/runner.py`：`resolve_source_crawl_mode(source_id)`；混合源分支 — heimao `_run_legacy_crawl` 片段 + xhs list_crawl 片段（单进程串行可先验证逻辑）
- [x] 1.3 `run_list_triage` 调用方：仅传入 `crawl_phase=list` 的 raw
- [x] 1.4 `build_investigation_queue`：排除 heimao legacy 已 fetch_detail 的 raw
- [x] 1.5 监测任务 UI：说明 crawl 策略源级决定；task.crawl_mode 降级/隐藏
- [x] 1.6 `reanalyze_monitor_task`：`shared_pool` 按源 crawl_mode 判定
- [x] 1.7 单元测试：混合源路由；heimao 不进 investigation；xhs routine 无 fetch_detail

## 2. Run 状态机 + diagnose 门禁（Phase B0，先于 Worker）

- [x] 2.1 新建 `intel/run_state.py`：active run 查询、stop_requested、替代 `S.running` 的 API 层判断
- [x] 2.2 `intel/db.py`：`monitor_runs` 扩展 `stop_requested`、可选 `worker_state_json`
- [x] 2.3 `intel/api.py`、`intel/scheduler.py`：`can_run` / `skip_if_running` 改查 run_state（**非** S.running）
- [x] 2.4 单进程路径：Run 开始前 diagnose（复用 `diagnose_login`）；失败按源 partial / 全失败规则
- [x] 2.5 `POST /api/stop`：设 stop_requested；runner 内 `is_stop_requested(run_id)` 中止
- [x] 2.6 单元测试：stop_requested；active run 检测（`scripts/test_run_state.py`）

## 3. Crawl 工作队列（Phase B1 基础）

- [x] 3.1 `intel/db.py`：`crawl_work_queue` 表（双形态 payload_json、claimed_at、heartbeat_at、skip_reason）
- [x] 3.2 `intel/crawl_queue.py`：enqueue list_crawl / legacy_crawl / investigation；claim / done / fail / skip / reclaim_stale
- [x] 3.3 `intel/run_metrics.py`：`worker_instances`、`cookie_diagnose_failed`、`sources_degraded` 等 stats
- [x] 3.4 单元测试：原子认领；stale reclaim；dedup 不变

## 4. 多进程 Worker + heimao ∥ xhs（Phase B1）

- [x] 4.1 `config.py` / `config.json.example`：`monitor.workers.*`、`run_state.*`；`config.auth` 与 workers instances[0] 默认对齐
- [x] 4.2 `crawler_web.py`：`prepare_worker_browser(port, user_data_dir)`、`connect_cdp(port)`；手动 crawl 409 冲突检测
- [x] 4.3 `auth_utils.py`：按路径注入 cookies_file（实例级）
- [x] 4.4 `intel/worker.py`：子进程；diagnose → claim routine items → 执行 adapter
- [x] 4.5 `intel/runner.py` Orchestrator：spawn heimao + xhs Worker；routine barrier；progress 汇总
- [x] 4.6 `login_gate.py`：WorkerRuntime；登录等待写 DB；Orchestrator 聚合至 `/api/status`
- [x] 4.7 Worker 日志写入 run logs（DB 或文件）；Run 详情 API 合并展示
- [x] 4.8 单元/集成测试：heimao ∥ xhs routine 并行；stop 广播

## 5. Investigation 按源回派（Phase B2）

- [x] 5.1 investigation enqueue：`phase=investigation` + source 路由
- [x] 5.2 heimao/xhs Worker claim investigation items；复用现有 `crawl_investigation`
- [x] 5.3 Orchestrator：investigation barrier 后进入 analyze
- [x] 5.4 手动验证：xhs 弹窗在 xhs Worker Chrome；heimao 详情在 heimao Worker

## 6. Cookie 管理 + config 统一（Phase C）

- [x] 6.1 API：`GET/POST /api/cookie-instances`（列表、上传、手动 diagnose）；路径校验、admin 写权限
- [x] 6.2 UI：Cookie 实例 Tab；失效横幅；多实例 login_wait 展示
- [x] 6.3 手动验证：更新 Cookie → diagnose 通过 → Run 成功

## 7. xhs investigation 配额（Phase D）

- [x] 7.1 `source_profiles.py` 白名单：`investigation_detail.max_modal_per_run`
- [x] 7.2 Orchestrator **Run 级** quota 扣减；Worker claim 前检查剩余额度
- [x] 7.3 超限 skip + `investigation_skipped_quota` / `investigation_modal_done`
- [x] 7.4 `field_labels.py` + `static/field-labels.json` + Run 历史表头
- [x] 7.5 单元测试：多 xhs 实例共享配额；skip 后 run 不 failed；analyze 仍处理 list triage

## 8. 分析并行（Phase E）

- [x] 8.1 `config`：`analysis.parallel_batches` 默认 5
- [x] 8.2 `intel/analyze.py`：ThreadPoolExecutor；stats/token 锁；单批失败仍跳过该批
- [x] 8.3 手动验证：parallel_batches=5 缩短 analyze wall-clock

## 9. 文档、迁移与非回归

- [x] 9.1 DB migration：`monitor_tasks.crawl_mode` 注释/文档；旧任务行为说明
- [x] 9.2 更新 `代码说明.md`、`DEPLOY.md`（多 Chrome 端口/profile）
- [x] 9.3 更新 `docs/API对接说明.md`：cookie-instances、run stats、run_state
- [x] 9.4 `openspec/verification-pending.md` 登记 § parallel-crawl-workers-selective-xhs
- [x] 9.5 非回归：early_stop、task_timeout 分段、incremental analyze
- [x] 9.6 手动验证：混合源 Run 总耗时下降；partial diagnose 降级；max_modal skip stats
