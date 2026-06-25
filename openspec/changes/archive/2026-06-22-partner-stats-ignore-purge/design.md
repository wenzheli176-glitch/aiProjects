## Context

- 合作方详情钻取（`partner-detail-drilldown`）已实现 `GET /api/partners/{id}/context` 计数，但 **列表 API 无 stats**。
- 分析管线 `_build_candidates_from_raw`（`intel/runner.py`）仅做增量/全量判断，无任务级时间截止。
- 清理能力仅有 `clear_intel_for_task`（全量重分析）与删任务 CASCADE，无按条件批量 purge。
- 任务已有 `business_spec_json`（`force_investigation_partner_ids`、`min_triage_relevance`）。

## Goals / Non-Goals

**Goals:**

- 合作方列表展示 **情报（中+/总数）**、**源数据（default_task）**，数字可点击进详情子 Tab。
- 任务配置 **`ignore_before`**（YYYY-MM-DD）：raw **入库**，分析 **跳过** `published_at < ignore_before`；`published_at` 为空 **仍分析**。
- 管理员 **`task_id` 必填** 的 raw/intel 批量清理，支持 `partner_id`、`published_before` 筛选与 `dry_run`。

**Non-Goals:**

- 爬取阶段不入库（用户要求入库）。
- investigation/triage 阶段过滤旧文（首版仅分析前过滤；可后续扩展）。
- 列表统计按 ignore_before 过滤（统计反映库内实际存量）。
- 非管理员操作员 purge 权限。
- 新 config.json 全局字段（ignore 存任务 business_spec）。

## Decisions

### 1. 列表 stats 聚合

复用 `get_partner_drilldown_context` 的 default_task 解析 SQL（`monitor_task_partners` + `ORDER BY updated_at DESC`）。

```python
# list_partners() 增强或 list_partners_with_stats()
# 1) partners 基表
# 2) intel: GROUP BY partner_id → intel_total, intel_medium_plus
# 3) default_task: 子查询/窗口 per partner_id
# 4) raw: COUNT WHERE task_id=default_task AND partner_id=?
```

`GET /api/partners` 每条增加：

```json
"stats": {
  "default_task_id": 100001,
  "intel_medium_plus": 5,
  "intel_total": 12,
  "raw_total": 340
}
```

无关联任务时 `default_task_id=null`，`raw_total=0`。

### 2. 列表 UI

新增列「情报」「源数据」：

- 情报：`{medium_plus}/{total}`，点击 `navigatePartnerIntel(id)`
- 源数据：`{raw_total}` 或 `-`，点击 `navigatePartnerRaw(id)`

### 3. ignore_before 存储

写入 `monitor_tasks.business_spec_json`：

```json
{ "ignore_before": "2025-01-01" }
```

任务创建/编辑 Modal 增加日期输入（可清空）；`update_monitor_task` / `create_monitor_task` 合并 business_spec。

Run 时从 `task.business_spec.ignore_before` 读取；`POST /api/monitor/run` 的 run 级 business_spec 可覆盖（与现有 merge 逻辑一致）。

### 4. 分析过滤实现

在 `_build_candidates_from_raw` 内，normalize 得到 `published_at` 后：

```python
def _should_skip_ignore_before(published_at, ignore_before):
    if not ignore_before:
        return False
    if not (published_at or '').strip():
        return False  # 空日期：不比较，仍分析
    return published_at < ignore_before  # YYYY-MM-DD 字符串比较
```

跳过时 `run_metrics.record_intel_skipped_ignore_before(1)`（或扩展现有 skipped 计数 + stats 字段）。

**full_replace** 同样应用 ignore_before（清除 intel 后仍不分析旧 raw）。

### 5. Purge API

```
POST /api/admin/purge/raw
POST /api/admin/purge/intel
@require_admin
```

Body:

```json
{
  "task_id": 100001,
  "partner_id": 7,
  "published_before": "2025-01-01",
  "dry_run": true
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `task_id` | **是** | 限定监测任务，防误删全库 |
| `partner_id` | 否 | 限定合作方 |
| `published_before` | 否 | 删除 `published_at < 日期` 的记录（空 published_at **不删**） |
| `dry_run` | 否 | true 仅返回 `matched_count` |

**purge raw**：`DELETE FROM raw_records WHERE task_id=? AND ...`；关联 intel 若 FK CASCADE 则一并删，否则先删 intel 再删 raw（实现时查 schema）。

**purge intel**：`DELETE FROM intel_records WHERE task_id=? AND ...`；raw 保留，后续增量 run 可再分析。

响应：`{ ok, matched_count, deleted_count, dry_run }`

任务 `crawling/analyzing` 时 **拒绝 purge**（409 或 400）。

### 6. Purge UI

- **监测任务 Tab**：行操作或 Modal 内「清理数据」→ 选 raw/intel、可选 partner、published_before → 预览 → Confirm。
- **合作方详情**：管理员可见「清理该合作方数据」→ `task_id` 来自 default_task 或下拉，partner 固定。

共用 `openPurgeModal({ task_id, partner_id? })`。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 列表 stats 查询慢（合作方多） | 2～3 条聚合 SQL，无 N+1 |
| published_at 缺失仍分析旧 list | 与产品决策一致；recency 后处理兜底 |
| purge 误删 | task_id 必填 + dry_run + Confirm |
| raw purge 删关联 intel | 文档说明；dry_run 展示影响条数 |

## Migration Plan

纯增量：无 DB migration（business_spec 已有列）。部署后任务可配置 ignore_before；管理员 purge 立即可用。

## Open Questions

（无——用户已确认：default_task raw、中+/总数、入库不分析、空日期跳过比较、task 级配置、task_id 必填 purge、按任务清理。）
