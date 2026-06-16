## Context

当前 `intel/runner.py` 在 `run_monitor_task` 中按 `for partner in partners: for source_id in sources` 调用 CrawlAdapter，每条结果带 `partner_id` 入库；`fetch_detail` 默认 true，黑猫/小红书均逐条开详情。AnalyzePipeline 对全部 raw（增量过滤后）做完整 LLM 打标。实测 2 合作方 × 2 源 × 20 页 ≈ 3 小时，且小鹏方 0 条（关键词未命中）。

业务约束（已确认）：
- 合作方多为相同/相近行业，关键词可合并；
- 定级可按风险动态调整，并允许业务系统指定；
- 列表摘要足够做初筛，不必Routine 重抓详情；
- 字段不全可接受；
- 高相关 + 高风险 + 增量 → 重点勘察（补详情 + 深分析）。

## Goals / Non-Goals

**Goals:**

- **Stage 2 交付**：共享爬取池 + 列表优先 + 列表 LLM 初筛 + 勘察补详情 + 动态 P0/P1/P2 + 业务系统 API。
- 将单次 run 的 CDP 详情请求量降低 **一个数量级**（Routine 仅列表；详情仅勘察队列）。
- 保持现有 Source 插件、登录三门禁、IntelRecord schema 向后兼容（新增字段 optional）。
- 同一 URL 在 task 内仍 UPSERT 去重，增量逻辑延续。

**Non-Goals（留 Stage 3）:**

- 多 Chrome / 多进程 per-source Worker 农场；
- 跨 task 全局 raw 池（Stage 2 仍 scope 在 monitor_task）；
- 自动行业分类 ML（先用 Partner 手工 `industry_cohort`）；
- 业务系统权重计算（仍外置，本系统只输出 `source` + `relevance` + `risk_types`）。

## Decisions

### 1. 三阶段流水线（Stage 2 Run 状态机）

```
list_crawl ──▶ list_triage ──▶ investigation_crawl ──▶ analyze
     │               │                    │                  │
  fetch_detail    轻量 LLM           仅队列 URL          完整 LLM
  = false         批处理             fetch_detail=true   （勘察档）
```

- **list_crawl**：按 `source × keyword_batch` 爬取，keyword_batch 由 task 内 partners 的 `industry_cohort` + `monitor_keywords` 合并去重生成；`insert_raw_records` 时 `partner_id=NULL`，写入 `crawl_phase=list`。
- **list_triage**：对新增/更新的 list raw 构建 `{title, list_snippet, source, url}` 候选，调用 `analysis.list_triage` 配置（小 batch、短 prompt、低 max_body_chars）；输出 `triage_relevance`、`triage_risk_hint`、`needs_investigation`。
- **investigation_crawl**：将 `needs_investigation=true` 且（triage 为 high/medium 或规则命中 P0 合作方别名）且增量（raw 无 detail 或 content_hash 变）的 URL 入队；CrawlAdapter 新方法 `crawl_investigation(urls[])` 仅抓详情，更新同 dedup_key raw 的 payload（`crawl_phase=detail`）。
- **analyze**：仅对「已勘察」或「triage 标 medium+ 且业务要求全分析」的 raw 走现有 `analyze_candidates`；列表-only 且 triage=noise 的仅写 `intel_records` 轻量行或跳过完整分析（可配置）。

**备选**：爬取与 triage 并行 —— 否决，单 Chrome 下仍串行更简单。

### 2. 共享爬取池与多方匹配

- Raw 表新增可空 `matched_partner_ids_json`（匹配后填充）或保持 matcher 在分析阶段计算；**不在 crawl 阶段绑定单一 partner**。
- `match_all_partners(normalized, partners[])` 返回 **多命中** 列表（最长别名优先，exclude 仍保留 raw）。
- Intel 写入：每个命中 partner 各写一条 intel（同 dedup_key + 不同 partner_id），或主 partner + `related_partners[]`（Stage 2 选 **每 partner 一条**，与现看板一致）。

关键词合并算法：

```python
def build_keyword_batches(partners, max_keywords_per_batch=5):
    # group by industry_cohort (default cohort = partner.name industry field)
    # within cohort: union monitor_keywords + names + aliases, dedupe
    # split batches if > max_keywords_per_batch
```

### 3. 列表摘要归一化（允许字段不全）

NormalizeAdapter 新增 `normalize_list_item(payload)`：
- **必填**：`source`, `url`, `title`（title 可 fallback 列表预览）
- **可选**：`body`（列表 snippet）、`published_at`、`author`、`extra`
- `body` 为空时 triage 仍可进行；完整 analyze 在勘察后补全。

`intel/normalizers/*.py` 与 `reports.py` 不强制 detail 字段。

### 4. 动态 P0/P1/P2

Partner 表新增：
- `priority_tier`: `P0` | `P1` | `P2`（默认 P1）
- `priority_source`: `auto` | `business` | `manual`
- `priority_updated_at`

自动规则（`intel/priority.py`，每日或 run 开始前）：
- 近 7 天 intel：`relevance=high` 且 `risk_types` 含严重类 ≥ N → 升 P0
- 30 天无 medium+ 信号 → 降 P2
- `priority_source=business` 时 **不自动降级**（仅业务 API 可改）

调度配额（Stage 2 简版，单 Chrome 内）：
- P0 cohort：优先执行，分配 50% keyword_batch 时间片
- P1：30%，P2：20%（可 config 覆盖）

### 5. 业务系统集成

新增 API（内网，与现有 `/api/intel/*` 并列）：

| 方法 | 路径 | 用途 |
|------|------|------|
| PATCH | `/api/partners/:id/priority` | `{ tier, source: "business", reason }` |
| POST | `/api/partners/bulk-priority` | 批量指定 |
| GET | `/api/partners/priority` | 导出当前定级与 auto 原因 |

MonitorTask 可选 `business_spec_json`：业务系统传入 `{ partner_ids, force_investigation, min_triage_relevance }` 仅对当次 run 生效。

### 6. CrawlAdapter 扩展

```python
class CrawlAdapter:
    def crawl_list_batch(self, ctx, task, keyword_batch, options) -> list
    def crawl_investigation(self, ctx, task, urls, options) -> list  # 仅详情
```

- `crawl_list_batch`：内部 `fetch_detail=False`；heimao 仍走搜索框；xhs 仍滚动列表。
- `crawl_investigation`：heimao `new_page` 详情；xhs 弹窗详情；遵守 login_gate。

### 7. config.json 新增字段

```json
"monitor": {
  "crawl_mode": "list_first",
  "industry_batch_max_keywords": 5,
  "priority_quota": { "P0": 0.5, "P1": 0.3, "P2": 0.2 }
},
"analysis": {
  "list_triage": {
    "enabled": true,
    "model": "MiniMax-M3",
    "batch_size": 20,
    "max_body_chars": 400,
    "investigation_threshold": { "min_relevance": "medium", "min_risk_hint": "elevated" }
  }
}
```

auth.* / heimao.* / xhs.* **不变**；勘察阶段仍走现有登录门禁。

### 8. 兼容与迁移

- 现有 MonitorTask：`crawl_mode` 默认 `legacy`（保持 partner×source 行为）直至用户切换。
- 新任务默认 `list_first`。
- DB migration：`partners` 加列；`raw_records` 加 `crawl_phase`, `list_triage_json`；新表 `investigation_queue`。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 列表 triage 误判漏掉高风险 | P0 合作方别名规则命中强制入勘察；triage prompt 高召回；noise 仍保留 raw |
| 多方匹配误归属同行业 | subject_hits 审计；业务 exclude_words；intel 分 partner 写入 |
| 勘察仍触发登录墙 | 复用 login_gate；investigation 批次限流 |
| 列表无 body 导致 analyze 质量差 | 仅勘察后做完整 analyze；列表档只写 triage 结果 |
| keyword 合并跨 cohort 污染 | cohort 硬分组；未设 cohort 的 partner 单独 batch |

## Migration Plan

1. DB migration + config 默认值（legacy 兼容）
2. 实现 `shared-crawl-pool` runner 分支（feature flag `monitor.crawl_mode`）
3. 实现 list triage + investigation 队列
4. 实现 priority 模块 + API
5. UI：任务创建增加 crawl_mode；合作方 industry_cohort / tier 字段
6. 文档 `代码说明.md` + DEPLOY 更新

回滚：task 级设 `crawl_mode=legacy` 恢复旧路径。

## Open Questions

- 列表 triage 结果是否持久化为独立表，还是写入 raw `list_triage_json`？→ **Stage 2 写 raw 列**，减少 join。
- 同一 URL 匹配 3+ partner 是否合并为 1 次 LLM？→ **triage 1 次，analyze 按 partner 模板各 1 次**（可后续优化）。
