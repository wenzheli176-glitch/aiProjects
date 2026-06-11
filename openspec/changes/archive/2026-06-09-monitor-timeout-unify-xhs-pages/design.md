## Context

`config.json` 中 `monitor.task_timeout_sec` 默认为 7200（2 小时），自 partner-risk-intel 引入以来仅作文档占位。`intel/runner.py` 的 `run_monitor_task` 在 partner × source 双重循环中调用各 CrawlAdapter，无 wall-clock 上限；实测 Task #2 爬取+分析约 3h8m，且 XHS 单源占绝大部分时间。

`max_pages` 在 MonitorTask 中为单一整数字段，经 `intel/sources/heimao.py` 与 `xhs.py` 传入 `crawl_heimao` / `crawl_xhs`：

- **黑猫**：`max_pages=N` → URL 分页 `page=1..N`，日志「黑猫第 N/M 页」。
- **小红书**：同样 `for p in range(1, max_pages+1)`，但 `p>1` 才滚动；起始日志写「滚动 N 次」，语义与黑猫不一致，且第 1 页不滚动导致「页」与「滚动轮」混用。

全局状态 `crawler_web.S` 已有 `S.running` 标志，爬取循环内会检查；停止 API 可将其置 false。超时 enforcement 可复用该机制。

## Goals / Non-Goals

**Goals:**

- MonitorRunner 读取 `cfg('monitor', 'task_timeout_sec', default=7200)`，在任务 wall-clock 超限时停止爬取并更新 DB 状态。
- heimao 与 xhs 对 `max_pages` 采用相同产品语义：**采集 M 页结果**（M = `max_pages`）。
- xhs 每页采集前执行相同滚动预热（使用既有 `xhs.scroll_*` 配置），日志统一为「小红书第 N/M 页」/「XHS第 N/M 页」。
- 超时与页数语义在 `代码说明.md`、看板 UI 提示中同步。

**Non-Goals:**

- MonitorTask 不拆分为 per-source `max_pages`。
- 不为 AI 分析单独配置 `analysis_timeout_sec`（本变更仅全任务超时，见决策 1）。
- 不改变 heimao URL 分页实现或 xhs 弹窗详情路径（`login_gate.py` / `xhs_detail.py` 三条门禁不变）。

## Decisions

### 1. 超时范围：全任务（爬取 + 分析）

**选择**：自 `run_monitor_task` 入口记录 `started_at`，超时检查覆盖爬取循环 **与** `_run_analysis_phase`。

**理由**：配置项位于 `monitor.*` 而非 `analysis.*`，业务期望是「一次监测点击」的整体上限；仅截断爬取可能仍长时间跑 AI。

**替代**：仅爬取阶段超时 — 拒绝，因 AI 大批次仍可能超 2h。

**实现要点**：

```python
# intel/runner.py 伪代码
deadline = time.monotonic() + timeout_sec

def _timed_out():
    return time.monotonic() >= deadline

def _check_timeout(task_id, log_fn):
    if _timed_out():
        S.running = False
        update_task_status(task_id, 'failed', error_message='任务超时（%ds）' % timeout_sec)
        return True
    return False
```

在 partner×source 循环每步开始前、以及 `_run_analysis_phase` 每批 `analyze_candidates` 前调用。爬取侧 `crawl_heimao` / `crawl_xhs` 已检查 `S.running`，无需改 login_gate。

**进度字段**：超时时 `progress` 含 `phase` 与 `reason: timeout`。

### 2. 超时状态：`failed` + 明确 error_message

**选择**：使用现有 `failed` 状态，`error_message` 前缀 `任务超时（task_timeout_sec=7200）`。

**理由**：DB schema 无 `timeout` enum；与「用户停止」区分靠 error_message；看板已展示 error_message。

**替代**：新增 `status=timeout` — 需 migration，超出本变更范围。

### 3. `max_pages` 统一语义：「结果采集页数」

**选择**：对两源，`max_pages=M` 表示执行 M 次结果采集迭代：

| 源 | 实现 | 用户可见 |
|----|------|----------|
| heimao | URL `page=1..M` | 「黑猫第 i/M 页」 |
| xhs | 每页先滚动 `scroll_times_per_page` 次再 `query_selector_all` | 「小红书第 i/M 页」 |

**xhs 行为变更**：

- 删除起始日志「滚动%d次」，改为「开始爬取小红书: %s %d页」（与黑猫对齐）。
- **第 1 页也执行滚动预热**（原先仅 `p>1` 滚动）：使每页负载机制一致；第 1 页滚动后 DOM 可能略增，属预期。
- RawRecord 的 `page` 字段仍为 1..M，与 heimao 一致。

**替代**：xhs 用 `max_scroll_rounds` 单独字段 — 拒绝，违背「MonitorTask 单一 max_pages」目标。

### 4. 配置默认值不变

`monitor.default_max_pages=2`、`heimao.default_max_pages=2`、`xhs.default_max_pages=3` 保持；后者仅影响 **单次调试爬取** UI 默认值。MonitorTask 创建仍用 `monitor.default_max_pages`。

无需新增 config 键；文档注明 `xhs.scroll_times_per_page` 控制每页滚动深度。

### 5. reanalyze 不受 task_timeout_sec 约束

**选择**：`reanalyze_monitor_task` 不应用同一超时（无 CDP、通常较快）。

**理由**：超时主要为 Chrome/CDP 长任务；重跑 AI 单独路径，避免误杀。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 全任务超时在 AI 批处理中途触发，部分 intel 已写入 | 标记 `failed` + error_message；已写入 intel 保留；文档说明可「重跑 AI」或重新监测 |
| xhs 第 1 页增加滚动导致与历史 raw 数据 `page` 分布略有差异 | 语义更正；dedup 按 url/external_id，影响有限 |
| 用户期望 xhs 3 页 = 3 次滚动而非 3 页采集 | UI/文档统一说明「页数=采集轮次，非 URL 页码」 |
| 超时与手动停止均设 `S.running=False` | error_message 区分「任务已停止」vs「任务超时」 |

## Migration Plan

1. 部署 `runner.py` + `crawler_web.py` 变更，无需 DB migration。
2. 更新 `代码说明.md` 中「已知限制」与 monitor 配置表。
3. 现有进行中任务：重启服务后新逻辑生效；无 retroactive 修复。

**Rollback**：还原 runner/crawler 改动；`task_timeout_sec` 恢复为 no-op。

## Open Questions

- （无）若后续需要 per-source 页数，另开变更扩展 MonitorTask schema。
