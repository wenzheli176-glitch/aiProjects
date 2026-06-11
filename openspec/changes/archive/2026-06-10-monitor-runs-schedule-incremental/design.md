## Context

当前 `run_monitor_task`（`intel/runner.py`）每次执行更新 `monitor_tasks.status/progress_json`，无独立 run 历史。`insert_raw_records`（`intel/db.py`）对同 dedup key 直接 skip，payload 永不更新。`_build_candidates_from_raw` 加载全部 raw 送 `analyze_candidates`，LLM 全量调用后 `insert_intel_record` 才 dedup 跳过写入。`reanalyze_monitor_task(replace=True)` 清空 intel 后全量分析。`partner-registry` spec 禁止自动定时。

用户决策（已锁定）：
- 定时触发 **同一 monitor_task**
- payload 更新 → **自动重分析**（覆盖该条 intel）
- 全量重分析 → **clear + 全量覆盖写**
- cron 表达式存储，**前端可视化选择器**生成
- token 按 **run + source** 汇总

## Goals / Non-Goals

**Goals:**
- 每次执行创建 `monitor_task_run`，记录 wall-clock 分源爬取/分析时长
- raw UPSERT + `content_hash`；unchanged skip、changed update
- 增量分析：仅「无 intel」或「raw.updated_at > intel.analyzed_at」入队；更新 intel 前先 DELETE 同 dedup_key
- 全量模式：`analyze_mode=full_replace` → `clear_intel_for_task` + 全量 LLM
- APScheduler 读 DB schedule，到点 `run_monitor_task(..., trigger='schedule')`
- UI：cron 预设/频率/时间/星期控件；run 历史表格；token/时长分源展示

**Non-Goals:**
- 跨 task 合并 raw/intel
- 分布式调度 / 多实例 leader 选举
- cron 手输编辑（仅只读预览）
- intel UPSERT 保留 id（全量一律覆盖写）
- 按 partner 维度 token 汇总（MVP 仅 source）

## Decisions

### D1 Run 一等公民

新表 `monitor_task_runs`：

| 列 | 说明 |
|----|------|
| `id` | PK |
| `task_id` | FK monitor_tasks |
| `trigger` | `manual` / `schedule` |
| `analyze_mode` | `incremental` / `full_replace` |
| `status` | `running` / `done` / `failed` / `skipped_overlap` |
| `started_at` / `finished_at` | ISO UTC |
| `crawl_duration_ms` / `analyze_duration_ms` | 阶段 wall time |
| `timing_by_source_json` | `{source:{crawl_ms, analyze_ms, raw_new, raw_updated, intel_written}}` |
| `token_usage_json` | `{total:{...}, by_source:{heimao:{prompt,completion,total}, ...}}` |
| `stats_json` | raw_new/skipped/updated, intel_written/replaced, errors |
| `error_message` | 失败摘要 |

`run_monitor_task` / `reanalyze_monitor_task` 入口创建 run，`analysis_jobs.run_id` 关联。

### D2 content_hash 与 raw UPSERT

```python
def _raw_content_hash(rec) -> str:
    # stable JSON serialize payload fields used for normalize
    return md5(canonical_json(rec))[:32]
```

`insert_raw_records` 改为 upsert 逻辑：
1. dedup key 不存在 → INSERT（`created_at=updated_at=now`）
2. key 存在且 hash 相同 → `skipped_unchanged++`
3. key 存在且 hash 不同 → UPDATE `payload_json`, `content_hash`, `updated_at`

迁移：为既有 raw 回填 `content_hash` 与 `dedup_key`。

### D3 增量分析队列

`_build_candidates_from_raw(task_id, partners, analyze_mode='incremental')`：

```sql
-- 概念：待分析 raw
LEFT JOIN intel_records i ON i.raw_record_id = r.id AND i.is_duplicate = 0
WHERE analyze_mode='incremental' AND (
  i.id IS NULL
  OR r.updated_at > i.created_at  -- analyzed_at alias
)
```

payload 更新重分析（runner 内、LLM 前）：
```python
delete_intel_by_dedup_key(task_id, cand['dedup_key'])
insert_intel_record(...)  # 覆盖写
```

`analyze_mode='full_replace'`：`clear_intel_for_task` 后不过滤，全量 candidates。

`analyze_candidates` 增加回调或返回值：每批按 `cand.source` 比例分摊 `prompt_tokens/completion_tokens` 至 run  accumulator。

### D4 分源分析时长

分析按 partner 批次，批内 mixed source。每批结束后：
- `batch_analyze_ms = time.monotonic() - t0`
- 按 batch 内各 source 条数比例分摊至 `timing_by_source[source].analyze_ms`

爬取时长：在 `runner.py` partner×source 循环，`crawl()` 前后 monotonic 差写入 `timing_by_source[source].crawl_ms`。

### D5 Cron 调度

依赖：`APScheduler`（BackgroundScheduler），在 `crawler_web.py` 启动时 `init_scheduler()`。

`monitor_tasks.schedule_json`：
```json
{
  "enabled": true,
  "cron": "0 8 * * *",
  "timezone": "Asia/Shanghai",
  "preset_id": "daily_08",
  "skip_if_running": true
}
```

调度器 job id = `monitor-task-{task_id}`；PATCH schedule 时 reload job。

到点执行：
```python
if S.running:
    create_run(status='skipped_overlap', trigger='schedule')
    return
run_monitor_task(task_id, trigger='schedule', analyze_mode='incremental')
```

全局开关：`config.monitor.scheduler_enabled`。

### D6 前端 Cron 选择器

`static/schedule-picker.js`（或并入 `panel-intel.js`）：

| 控件 | 生成规则 |
|------|----------|
| 频率 | daily → `M H * * *`；weekly → `M H * * DOW`；interval_hours → `0 */N * * *` |
| 时/分 | `<select>` 0–23 / 0–59 |
| 星期 | multi checkbox → cron DOW |
| 预览 | 「每天 08:00 · cron: 0 8 * * *」只读 |

保存：POST/PATCH task 时写 `schedule_json`；加载时 cron → 控件反解析（preset 子集）。

### D7 API 变更

| 路由 | 变更 |
|------|------|
| `POST /api/monitor/run` | body: `{ task_id, analyze_mode?: incremental }` |
| `POST /api/monitor/reanalyze` | body: `{ task_id, analyze_mode: incremental\|full_replace }`；`replace` 废弃映射 full_replace |
| `GET /api/monitor/tasks/{id}/runs` | 分页 run 列表 |
| `GET /api/monitor/runs/{run_id}` | run 详情含 timing/token |
| `PATCH /api/monitor/tasks/{id}` | 接受 `schedule` 对象 |

## Risks / Trade-offs

- **[Risk] 定时跑遇 login_gate 无人登录** → run 记 `failed`，日志提示；不阻塞后续 cron（下次再试）
- **[Risk] APScheduler 与 Flask 热重载** → 文档要求生产用稳定进程；scheduler 在 app factory 只 init 一次
- **[Risk] content_hash 算法变更** → 版本前缀或 migration 一次性重算
- **[Trade-off] 分源 token 按条数分摊** → 非精确计费，但足够评估效率；批次日志仍保留原始值

## Migration Plan

1. `SCHEMA_VERSION` +1：新表/新列，回填 hash
2. 部署后既有 task 默认 `schedule.enabled=false`
3. 首次 run 开始写 run 历史；旧任务无历史 run 可接受

## Open Questions

- （已关闭）定时对象、增量/全量、cron UI、token 汇总 — 见用户决策
