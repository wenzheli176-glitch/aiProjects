## 1. 数据库与迁移

- [x] 1.1 `intel/db.py`：SCHEMA_VERSION+1；表 `monitor_task_runs`；`raw_records` 增 `dedup_key`/`content_hash`/`updated_at`；`analysis_jobs.run_id`；`monitor_tasks.schedule_json`/`last_run_id`
- [x] 1.2 迁移脚本：既有 raw 回填 dedup_key + content_hash
- [x] 1.3 CRUD：`create_task_run`/`finish_task_run`/`list_task_runs`/`get_task_run`；run 字段 merge helpers

## 2. Raw UPSERT

- [x] 2.1 `intel/db.py`：`insert_raw_records` 改 UPSERT（unchanged skip / changed update / new insert）
- [x] 2.2 抽取 `_raw_content_hash` / `_raw_dedup_key` 与 runner 侧 dedup 对齐
- [x] 2.3 `delete_intel_by_dedup_key(task_id, dedup_key)` 供 payload 更新重分析

## 3. 增量分析队列

- [x] 3.1 `intel/runner.py`：`_build_candidates_from_raw(..., analyze_mode)` 过滤待分析 raw
- [x] 3.2 `run_monitor_task` / `reanalyze_monitor_task` 增参 `trigger`/`analyze_mode`/`run_id`
- [x] 3.3 payload 更新路径：LLM 前删旧 intel，写入新 intel（覆盖）
- [x] 3.4 `full_replace`：`clear_intel_for_task` + 全量 candidates

## 4. Run 计时与 Token 汇总

- [x] 4.1 `runner.py`：partner×source 爬取 monotonic 计时 → `timing_by_source`
- [x] 4.2 `analyze.py`：批结束后按 source 条数分摊 analyze_ms 与 tokens → run accumulator
- [x] 4.3 run 结束写入 `crawl_duration_ms`/`analyze_duration_ms`/`token_usage_json`/`stats_json`
- [x] 4.4 `create_analysis_job(..., run_id=)` 关联 run

## 5. API

- [x] 5.1 `POST /api/monitor/run`：`analyze_mode`；创建 run
- [x] 5.2 `POST /api/monitor/reanalyze`：`analyze_mode` incremental|full_replace；废弃 replace 映射
- [x] 5.3 `GET /api/monitor/tasks/{id}/runs`、`GET /api/monitor/runs/{run_id}`
- [x] 5.4 `PATCH /api/monitor/tasks/{id}` 接受 `schedule`；返回 `next_run_at`/`last_run` 摘要
- [x] 5.5 `_enrich_task` 附加 schedule、last_run、can_run 等

## 6. Cron 调度器

- [x] 6.1 依赖：`APScheduler` 加入 requirements
- [x] 6.2 `intel/scheduler.py`（或 crawler_web）：init/reload/remove job；读 `monitor.scheduler_*`
- [x] 6.3 `crawler_web.py` 启动时 load 全部 enabled schedule
- [x] 6.4 skip_if_running → skipped_overlap run
- [x] 6.5 `config.py`/`config.json`：`monitor.scheduler_enabled`、`monitor.scheduler_timezone`

## 7. 前端

- [x] 7.1 `static/schedule-picker.js`：频率/时/分/星期 → cron；只读预览
- [x] 7.2 任务表单：启用定时 + schedule-picker；保存 schedule_json
- [x] 7.3 任务列表：最近 run 时间/时长/状态；展开分源 timing+token
- [x] 7.4 按钮：「执行（增量）」；「重跑 AI ▾」增量 / 全量覆盖
- [x] 7.5 field_labels：schedule 相关字段注册

## 8. 文档

- [x] 8.1 更新 `代码说明.md`：run 表、UPSERT、增量分析、scheduler
- [x] 8.2 更新 `docs/API对接说明.md`：runs API、analyze_mode、schedule

## 9. 手动验证

- [x] 9.1 同一 task 执行两次：第二次 raw 不变则 skip LLM；新 URL 仅分析新增
- [x] 9.2 模拟 payload 变化（如 heimao 回复增多）：raw updated_at 刷新且 intel 覆盖重写
- [x] 9.3 全量重分析：intel 清空后全部重写；run 记录 full_replace
- [x] 9.4 启用定时（短 cron 测试）：到点自动 run；运行中重叠 → skipped_overlap
- [x] 9.5 Run 详情：分源 crawl/analyze ms 与 token 与日志量级一致
- [x] 9.6 Schedule UI：选「工作日 09:00」保存重载后 cron 与预览正确
