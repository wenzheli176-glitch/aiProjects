## 1. 合作方列表统计（后端）

- [x] 1.1 `intel/db.py`：`list_partners_with_stats()`（intel 聚合、default_task、raw_total；复用 drilldown 规则）
- [x] 1.2 `intel/api.py`：`GET /api/partners` 返回 `stats` 字段
- [x] 1.3 单元测试 `scripts/test_partner_list_stats.py`

## 2. ignore_before（后端）

- [x] 2.1 `intel/runner.py`：`_build_candidates_from_raw` 应用 `ignore_before`；空 `published_at` 不跳过
- [x] 2.2 `intel/run_metrics.py`（可选）：记录 `intel_skipped_ignore_before`
- [x] 2.3 单元测试 `scripts/test_ignore_before_filter.py`（跳过/空日期/未配置）

## 3. 管理员 Purge（后端）

- [x] 3.1 `intel/db.py`：`purge_raw_records` / `purge_intel_records`（task_id 必填、partner_id、published_before、dry_run）
- [x] 3.2 `intel/api.py`：`POST /api/admin/purge/raw`、`POST /api/admin/purge/intel`（`@require_admin`）
- [x] 3.3 单元测试 `scripts/test_admin_purge.py`（dry_run、403、运行中任务拒绝）

## 4. 前端

- [x] 4.1 合作方列表：情报（中+/总数）、源数据列，点击钻取详情子 Tab
- [x] 4.2 任务 Modal：`ignore_before` 日期字段，读写 `business_spec`
- [x] 4.3 管理员清理 Modal：任务 Tab + 合作方详情入口；dry_run 预览 → Confirm
- [x] 4.4 `app.css`：统计列样式（如需）

## 5. 文档

- [x] 5.1 更新 `代码说明.md`：stats、ignore_before、purge API
- [x] 5.2 更新 `docs/API对接说明.md`：purge 请求体与权限

## 6. 手动验证

- [x] 6.1 合作方列表 stats 与详情 context 计数一致；点击进对应子 Tab
- [x] 6.2 任务设 ignore_before 后 run：旧文 raw 入库但不产生 intel；空 published_at 仍分析
- [x] 6.3 管理员 purge dry_run 预览条数正确；确认删除后列表/详情计数更新
- [x] 6.4 非管理员无 purge 入口；purge API 403
- [x] 6.5 验证完成后 `python scripts/sync_verification_tasks.py push`
