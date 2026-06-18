## Context

- Stage 2：`list_first` + `list_triage` + `investigation` 弹窗已在 `crawler_web.py` / `xhs_detail.py` 实现。
- 生产痛点：任务若走 **legacy + fetch_detail**，xhs routine 逐条弹窗；单 Chrome + `runner.py` 串行；多账号依赖单一 profile。
- 架构审查结论：heimao legacy 与 xhs list_first 是 **两种编排模型**，不可强行统一为单一 `keyword_batch × phase`。
- 用户已确认约束（冻结）：xhs 强制 list_first；heimao legacy；Cookie 文件 + 管理页；max_modal skip+stats；同机多进程；parallel_batches=5；Run 前 diagnose；heimao∥xhs 并行。

## Goals / Non-Goals

**Goals:**

- 混合源监测 Run：heimao legacy routine ∥ xhs list_crawl 并行；汇合后 triage → investigation（按源 Worker）→ analyze。
- xhs：routine 零弹窗；investigation 弹窗 + Run 级配额。
- Cookie 可运维；Run 级状态替代 `S.running`；多 Worker 日志与登录等待可观测。
- analyze LLM 批并行（默认 5）。

**Non-Goals:**

- 跨机器 Worker 农场；heimao 迁 list_first；xhs goto explore；同 Chrome 内并行弹窗。

## Decisions

### 1. 源级 crawl_mode（非任务级）

| 源 | crawl_mode | routine 单元 | routine 详情 |
|----|------------|--------------|--------------|
| xhs | **list_first**（强制） | `keyword_batch × list_crawl` | 禁止 |
| heimao | **legacy**（默认） | `partner × legacy_crawl` | 按 task.fetch_detail |

- `monitor_tasks.crawl_mode` **保留列**但降级：仅当任务 **仅含 heimao** 且未开 Worker 时作 fallback；混合源任务 **忽略** task 级值，改读 `config.sources.{id}.crawl_mode`。
- UI：任务编辑页说明「爬取策略由数据源配置决定」；隐藏或禁用 xhs legacy 选项。

### 2. 混合源 Run 状态机

```
Orchestrator (Flask)
  │
  ├─ enqueue routine work items
  │     xhs:  phase=list_crawl,  payload=keyword_batch_json
  │     heimao: phase=legacy_crawl, payload=partner_id + keyword
  │
  ├─ spawn Workers (diagnose → claim → execute)
  │     heimao Worker ∥ xhs Worker(s)   [wall-clock 并行]
  │
  ├─ barrier: 所有 routine items done/skipped/failed
  │
  ├─ list_triage（Orchestrator，仅 crawl_phase=list 的 raw）
  │
  ├─ build_investigation_queue（heimao 已 fetch_detail 的 raw 排除）
  │
  ├─ enqueue investigation work items（按 source 分组）
  │     → heimao Worker / xhs Worker 各自 claim
  │
  └─ analyze（Orchestrator，ThreadPool parallel_batches）
```

### 3. 工作单元与队列（双形态）

```python
# crawl_work_queue 列（概念）
run_id, task_id, source_id,
phase,           # list_crawl | legacy_crawl | investigation
payload_json,    # 见下
priority_score,
worker_instance_id, claimed_at, heartbeat_at,
status,          # pending | claimed | done | failed | skipped
error_message, skip_reason
```

**payload_json 形态：**

| phase | source | payload |
|-------|--------|---------|
| `list_crawl` | xhs | `{ "keyword_batch": {...}, "cohort": "..." }` |
| `legacy_crawl` | heimao | `{ "partner_id": 1, "keyword": "小鹏" }` |
| `investigation` | heimao/xhs | `{ "queue_item_ids": [12, 13], "urls": [...], "items": [...] }` |

- 认领：单条 `UPDATE ... WHERE status='pending'`（SQLite WAL）。
- **Reclaim**：`claimed_at` 超过 `monitor.run_state.claim_timeout_sec`（默认 600）且无 heartbeat → Orchestrator 重置为 `pending`。
- 入库：仍 `insert_raw_records` + dedup_key UPSERT。

### 4. Worker 进程与 Chrome 生命周期

- **启动责任**：Orchestrator 在 spawn Worker 前调用 `prepare_worker_browser(instance_cfg)`，按 `cdp_port` + `user_data_dir` 启动独立 Chrome；Worker 仅 `connect_over_cdp(port)`。
- **目录**：`chrome_profiles/{source}_{instance_id}/`；与现有 `chrome_heimao_profile/` 迁移文档化。
- **Cookie**：实例 `cookies_file` 为权威来源；`config.auth.{site}.cookies_file` **默认指向** `monitor.workers.{site}.instances[0].cookies_file`（启动时 merge，避免双轨）。
- **手动调试爬取**（`/api/crawl_*`）：若 Run 进行中或端口被 Worker 占用，必须返回 409 + 明确错误；不得与 Worker 争用 CDP。

### 5. Run 前 diagnose 与部分失败

- 每 Worker **首次 claim 前** diagnose 绑定实例 Cookie。
- **单源 diagnose 失败**：该源 Worker 不 claim；run stats `cookie_diagnose_failed` += 1；记录 `worker_instances[].status=diagnose_failed`；**其他源继续**。
- **全部启用源 diagnose 失败**：Run `status=failed`，不进入 triage/analyze。
- **部分源 crawl 成功**：Run 可 `status=done` 或 `partial`（新增 stats `sources_degraded`）；UI 展示降级说明。

### 6. Investigation 按源回派 + Run 级弹窗配额

- investigation **不得**在 Orchestrator 单 Chrome 串行；enqueue 为 `phase=investigation` work items，`source_id` 路由至对应 Worker。
- xhs 弹窗配额 **`max_modal_per_run` 为 Run 级全局计数**，存 `monitor_runs.stats_json` 或 Orchestrator 内存 + 定期 flush；多 xhs 实例 **共享**同一计数器（claim 前 Orchestrator 检查剩余额度）。
- 达上限：剩余 xhs queue items → `skipped` / `modal_quota_exceeded`；Run 不 failed。

### 7. list_triage 与 heimao investigation 去重

- `run_list_triage` **仅处理** `crawl_phase=list` 且尚无 `list_triage` 的 raw（不 triage heimao legacy raw）。
- `build_investigation_queue` **排除**：
  - `crawl_phase=detail`；
  - `source=heimao` 且 routine 已 `fetch_detail=true` 且 payload 含详情字段（`content`/`body` 超阈值）；
  - 无 `list_triage` 的 raw（xhs list 必须先 triage）。
- heimao legacy + fetch_detail=true：**routine 即深抓取**，investigation 仅补 triage 后仍缺详情且未在 routine 抓到的边 case（默认跳过）。

### 8. 全局状态迁移（S.running → Run 状态）

| 原 `S.running` 用途 | 新机制 |
|---------------------|--------|
| 阻止并发 monitor run | `monitor_runs.status IN ('running','crawling','analyzing')` 或 run_id 锁 |
| scheduler skip_if_running | 查上表，非 `S.running` |
| API can_run / can_reanalyze | 查 active run_id |
| adapter 内 `if not S.running` | Worker 局部 `WorkerRuntime.running` + run_id |
| login_gate 等待 | Worker 写 `worker_login_wait_json` 至 DB；`/api/status` 聚合 |
| POST /api/stop | Orchestrator 设 run `stop_requested`；广播 Worker；reclaim queue |

- 手动 crawl 面板：仍可用 **独立** CDP（config 默认 9222），与 Worker 端口隔离。

### 9. 日志与可观测性

- Worker 日志：结构化行 `{run_id, source, instance, phase, msg}` 写入 `monitor_run_logs` 表或 append 至 run 日志文件；Orchestrator `/api/monitor/runs/:id/logs` 合并展示。
- progress：`update_task_status` 汇总各源 queue done/total。

### 10. 分析并行与 investigation skip 后 analyze

- `analyze_candidates`：ThreadPoolExecutor(`parallel_batches`)；`run_metrics` 加锁。
- xhs raw 被 quota skip：**仍按 list_triage 结果**走 analyze（partial body）；不 fail run。
- `reanalyze_monitor_task`：`shared_pool = any(source.crawl_mode==list_first)` 或 task 含 xhs；不读 task.crawl_mode 单字段。

### 11. 配置示例

```json
"monitor": {
  "workers": {
    "heimao": {
      "instances": [{
        "instance_id": "heimao-0",
        "cdp_port": 9222,
        "user_data_dir": "chrome_profiles/heimao_0",
        "cookies_file": "credentials/heimao_cookies.json"
      }]
    },
    "xhs": {
      "max_instances": 2,
      "instances": [
        { "instance_id": "xhs-0", "cdp_port": 9230, "user_data_dir": "chrome_profiles/xhs_0", "cookies_file": "credentials/xhs_0.json" },
        { "instance_id": "xhs-1", "cdp_port": 9231, "user_data_dir": "chrome_profiles/xhs_1", "cookies_file": "credentials/xhs_1.json" }
      ]
    }
  },
  "max_workers_total": 4,
  "run_state": { "claim_timeout_sec": 600, "heartbeat_interval_sec": 30 }
},
"analysis": { "parallel_batches": 5 },
"xhs": {
  "investigation_detail": {
    "max_modal_per_run": 200,
    "dom_miss_skip": true
  }
}
```

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 混合源编排复杂 | Phase A 先源级路由（单进程）；Phase B 再上 Worker |
| 多 Chrome 内存 | max_workers_total；默认 heimao1+xhs1 |
| SQLite 并发 | WAL；短事务；quota 由 Orchestrator 串行扣减 |
| Worker 僵死 | claim_timeout + heartbeat reclaim |
| login_gate 多进程 | DB 聚合 login_wait |
| LLM 限流 | parallel_batches 可配；批失败仍跳过该批 |

## Migration Plan

1. **Phase A**：源级 crawl_mode + 混合源单进程编排（无 Worker）
2. **Phase B0**：Run 状态机 + diagnose 门禁（仍单 Chrome 可验证）
3. **Phase B1**：crawl_work_queue + 双 Worker 并行 routine crawl
4. **Phase B2**：investigation 按源回派 + 登录/停止/日志
5. **Phase C**：Cookie 管理页 + config.auth 统一
6. **Phase D**：Run 级弹窗配额 + stats 标签
7. **Phase E**：analyze parallel_batches

回滚：`monitor.workers.enabled=false` 恢复单进程（tag `ae6735c`）。

## Non-Regression（必须保持）

- `early_stop`（heimao/xhs）在 Worker 路径行为与现网一致
- `task_timeout_sec` / `analysis_timeout_sec` 分段；并行 crawl 后仍预留 analyze 预算
- scheduler `skipped_overlap` 语义不变（改查 Run 状态）
- incremental analyze / dedup / match_all_partners 不变
- xhs investigation 禁止 goto explore

## Open Questions

（已闭合，见上文 Decisions）
