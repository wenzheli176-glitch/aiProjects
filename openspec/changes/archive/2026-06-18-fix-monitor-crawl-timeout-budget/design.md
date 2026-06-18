## Context

`intel/runner.py` 中 `run_monitor_task` 使用双 deadline：

```python
deadline = task_started + task_timeout_sec
analysis_reserve = clamp(analysis_timeout_sec, ...)
crawl_deadline = max(task_started + 300, deadline - analysis_reserve)
```

当 `analysis_timeout_sec == task_timeout_sec == 7200` 时，`analysis_reserve ≈ 6900`，`crawl_deadline ≈ task_started + 300`（5 分钟）。爬取阶段 `timeout_check('crawl')` 触发后，错误信息仍输出 `任务超时（task_timeout_sec=7200）`，用户无法区分「爬取预算耗尽」与「整任务超时」。

本次故障链：Worker routine（heimao legacy + xhs list）未完成 → 未进入 `_run_post_list_crawl_phases` → list_triage / investigation（xhs 弹窗）未执行。

现有 spec（`intel-pipeline`）将 crawling 超时描述为 `elapsed ≥ task_timeout_sec`，与实现（crawl 用 `crawl_deadline`）不一致。

## Goals / Non-Goals

**Goals:**

- 爬取阶段在典型配置下获得与任务规模匹配的 wall-clock 预算（默认至少 30 分钟量级，可配置保底）。
- 分析阶段仍从总 `task_timeout_sec` 内预留，但不得吞噬几乎全部爬取时间。
- 失败可观测：`error_message` / `progress.reason` / 日志明确 phase（crawl vs analyze vs task）。
- 修正 example 与文档，避免再次配置 `analysis_timeout_sec == task_timeout_sec`。
- 单元测试锁定预算公式。

**Non-Goals:**

- 不改变 list_triage / investigation 触发条件或 xhs 弹窗逻辑。
- 不改为 per-phase 独立 `task_timeout_sec`（保持单一总超时 + 内部分配）。
- 不重做 Worker queue 超时（`claim_timeout_sec` 另 spec）。

## Decisions

### D1：预算公式

引入 `compute_monitor_deadlines(task_timeout_sec, analysis_timeout_sec, min_crawl_timeout_sec)`（可放在 `intel/runner.py` 或新建 `intel/timeout_budget.py`）：

```
analysis_reserve = min(analysis_timeout_sec, task_timeout_sec - min_crawl_timeout_sec)
analysis_reserve = max(300, analysis_reserve)   # 分析至少 5 分钟
crawl_budget = task_timeout_sec - analysis_reserve
crawl_budget = max(min_crawl_timeout_sec, crawl_budget)
crawl_deadline = task_started + crawl_budget
deadline = task_started + task_timeout_sec   # 整任务硬顶不变
```

默认 `min_crawl_timeout_sec = 1800`（30 分钟），配置键 `monitor.min_crawl_timeout_sec`。

**理由**：即使 `analysis_timeout_sec` 配得过大，爬取仍有保底；总时长仍受 `task_timeout_sec` 约束。

**备选**：仅文档要求 `analysis_timeout_sec < task_timeout_sec` — 无法防止误配，已否决。

### D2：错误语义

| 触发点 | error_message 示例 | progress.reason |
|--------|-------------------|-----------------|
| crawl_deadline | `爬取阶段超时（crawl_budget_sec=3600）` | `crawl_timeout` |
| deadline（analyze） | `分析阶段超时（task_timeout_sec=7200）` | `timeout` |
| deadline（整任务兜底） | `任务超时（task_timeout_sec=7200）` | `timeout` |

日志：`[monitor] 爬取阶段超时 …` vs `[monitor] 任务超时 …`。

### D3：配置加载校验（软）

`load_config` 或 runner 启动时：若 `analysis_timeout_sec > task_timeout_sec - min_crawl_timeout_sec`，写 WARN 日志（不拒绝启动），并按 D1 公式 clamp。

`config.json.example`：`task_timeout_sec: 7200`，`analysis_timeout_sec: 3600`，`min_crawl_timeout_sec: 1800`。

### D4：爬取完成后分析预算

现有逻辑在 crawl 成功后重置 `deadline = now + analysis_budget`；保留，但 `analysis_budget` 取 `min(analysis_timeout_sec, 剩余 task_timeout)`，与 D1 一致。

### D5：测试

`scripts/test_monitor_timeout_budget.py`：表格驱动测试边界（7200/7200、7200/3600、600/3600 等）。

## Risks / Trade-offs

- **[Risk] 爬取保底过长导致分析时间不足** → `min_crawl_timeout_sec` 可配置；任务失败时 progress 标明 crawl_timeout，用户可调小任务或增大 task_timeout。
- **[Risk] 与旧 error_message 字符串匹配的外部监控** → 新文案更精确；属预期 **BREAKING** 仅影响依赖固定字符串的脚本。
- **[Risk] 超长 crawl 仍撞 task_timeout_sec 硬顶** → analyze 前检查剩余时间，不足则 failed + 明确 reason。

## Migration Plan

1. 合并代码 + 测试。
2. 更新 `config.json.example`；运维侧检查生产 `analysis_timeout_sec` 是否等于 `task_timeout_sec`，建议改为 3600。
3. 无需 DB 迁移。
4. 回滚：还原 runner 公式与配置即可。

## Open Questions

- `min_crawl_timeout_sec` 默认 1800 是否适合所有部署？可先与 `task_timeout_sec` 联动：`min(task_timeout * 0.5, 1800)`（实现阶段可简化固定 1800）。
