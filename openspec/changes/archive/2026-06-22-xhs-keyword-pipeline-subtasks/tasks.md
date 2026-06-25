## 1. 数据与子任务

- [x] 1.1 `monitor_keyword_runs` 表与 CRUD（schema v9）
- [x] 1.2 `sync_task_subtask_progress` 写入任务 progress
- [x] 1.3 `partners.source_timeouts_json`（schema v10）与 API

## 2. Keyword 流水线

- [x] 2.1 `crawl_xhs_list_with_dom` + `intel/keyword_pipeline.py`
- [x] 2.2 Worker `keyword_pipeline` phase；队列按 keyword 入队
- [x] 2.3 跳过 xhs 批量 `_run_post_list_crawl_phases`
- [x] 2.4 `intel/source_timeout.py` 合作方×源超时解析
- [x] 2.5 黑猫 legacy 应用合作方超时

## 3. API

- [x] 3.1 `GET /api/monitor/runs/{id}/keywords`
- [x] 3.2 `GET /api/monitor/tasks/{id}/keywords/failed`
- [x] 3.3 `POST /api/monitor/retry-keywords`

## 4. 控制台

- [x] 4.1 合作方表单：xhs/黑猫超时字段
- [x] 4.2 Run 详情：keyword 子任务表 + 重跑失败按钮
- [x] 4.3 任务列表：subtasks 进度摘要

## 5. 验证

- [x] 5.1 `scripts/test_keyword_pipeline.py`
- [x] 5.2 手动：执行含 xhs 任务，Run 详情见子任务；失败 keyword 重跑
