## Why

当前监测任务按 **合作方 × 数据源** 串行爬取，且默认 **每条抓详情**，在百级合作方、多源、日更场景下耗时与封禁风险不可接受。实际业务中合作方多为相同或相近行业，关键词高度重叠，适合 **「爬一次、匹配多方」** 的共享采集池。需要在不引入多 Chrome 集群（Stage 3）的前提下，先落地 **Stage 2**：列表摘要采集 + 行业关键词合并 + 动态定级 + 业务系统可指定优先级，并对 **高相关高风险增量信号** 做列表大模型初筛后的 **重点勘察（补详情 + 深分析）**。

## What Changes

- 监测爬取单元从 `partner × source` 改为 **`source × industry_keyword_batch`**，同一批关键词只爬一次，结果写入共享 raw 池后由 PartnerMatcher 匹配多个合作方。
- 常规监测默认 **`fetch_detail=false`**，仅保留列表页可得的 title / 摘要 / link / 时间等字段；允许 NormalizedRecord **字段不全**。
- 新增 **列表初筛（List Triage）**：对列表级候选调用轻量 LLM，输出 relevance 粗分与是否进入勘察队列。
- 新增 **重点勘察（Investigation）**：对「高相关 + 高风险 + 增量」条目单独 `fetch_detail=true` 补爬详情，再进入完整 AnalyzePipeline。
- 合作方引入 **动态优先级 P0/P1/P2**（默认由近期情报风险自动升降，业务系统可通过 API 覆盖指定）。
- 合作方可配置 **行业 cohort**（如「新能源整车」），用于关键词合并与调度配额。
- MonitorTask / Run 增加阶段：`list_crawl` → `list_triage` → `investigation_crawl` → `analyze`。
- **BREAKING（行为默认）**：新建监测任务默认 `crawl_mode=list_first`（列表优先）；旧任务可保留 `legacy_partner_source` 兼容一轮。

## Capabilities

### New Capabilities

- `shared-crawl-pool`: 按源与行业关键词批次共享爬取、raw 去重、多方匹配归属
- `list-triage-investigation`: 列表 LLM 初筛、勘察队列、增量重点详情补爬与深分析
- `dynamic-partner-priority`: P0/P1/P2 动态定级、调度配额与业务系统覆盖
- `business-system-integration`: 业务系统指定合作方优先级、勘察策略、行业 cohort 的 API 契约

### Modified Capabilities

- `intel-pipeline`: 允许字段不全的 NormalizedRecord；分析分「列表初筛 / 完整分析 / 勘察分析」三档
- `source-adapter`: CrawlAdapter 支持 `list_only` 与 `investigation_urls` 两种爬取模式
- `partner-registry`: Partner 增加 `industry_cohort`、`priority_tier`、业务覆盖字段
- `monitor-task-runs`: Run 阶段与 metrics 扩展（list_triage、investigation 计数）

## Impact

- **代码**：`intel/runner.py`（编排重构）、`intel/matcher.py`、`intel/analyze.py`、新建 `intel/triage.py` / `intel/investigation.py`；`intel/sources/*.py`；`intel/db.py`（partners、raw_records、investigation_queue 表）；`intel/api.py`；`config.py` / `config.json` 新增 `monitor.crawl_mode`、`monitor.industry_batch`、`analysis.list_triage.*`
- **站点**：heimao / xhs 列表路径不变；详情仅在勘察阶段触发，仍走 `login_gate` 与 xhs 弹窗详情
- **API**：`PATCH /api/partners/:id/priority`、业务系统批量指定接口；Run 进度 JSON 新 phase
- **非目标（Stage 3）**：多 Chrome 实例、按域名的独立 Worker 队列、跨机器调度
