## Context

舆情爬虫 v9 已具备：Flask Web、`crawler_web.py` 爬取入口、黑猫/小红书 CDP 采集、`login_gate.py` 登录等待续跑、`xhs_detail.py` 弹窗详情、`reports.py` 黑猫结构化报表。采集结果目前存于内存 `S.results_*` 并支持 JSON/CSV 导出，无持久化、无名单驱动、无 AI 情报层。

产品目标：对**合作方名单**持续采集多源信号，规则归一 + 云模型高召回打标，经统一看板与 API 交付；业务系统对 `source` 自行加权。已拍板：SQLite、手动触发监测、内网 API 无鉴权、黑猫/小红书为 MVP 源、架构按 N 源可插拔设计。

## Goals / Non-Goals

**Goals:**

- 名单驱动的 MonitorTask，手动触发，状态机 `queued → crawling → analyzing → done | failed`
- SourceRegistry + CrawlAdapter + NormalizeAdapter，新增源不改 IntelRecord 核心 schema
- 源无关 PartnerMatcher + AnalyzePipeline，高召回（medium+ 默认展示，noise 极少）
- SQLite 持久化 partners、tasks、raw_records、intel_records、analysis_jobs
- 看板 + JSON/Excel + REST API，每条 IntelRecord 必填 `source`

**Non-Goals:**

- 本系统内权重/综合分、法律定性结论
- 定时调度、API Key 鉴权、第三源实现
- 爬取循环内同步调模型（AI 与爬取解耦）
- 修改既有登录门禁/弹窗详情行为（见 `login_gate.py`、`xhs_detail.py` 现有 spec）

## Decisions

### 1. 分层架构：采集与情报解耦

```
Partner Registry + MonitorTask
        │
        ├─▶ CrawlAdapter[source_id]  ──▶ raw_records (SQLite)
        ├─▶ NormalizeAdapter[source_id] ──▶ normalized (内存或表)
        ├─▶ PartnerMatcher (全局)
        ├─▶ AnalyzePipeline (全局, 云模型, 异步)
        └─▶ intel_records ──▶ 看板 / 导出 / API
```

**理由**：爬取耗时长且站点差异大；AI 批处理可重试、可审计。新源只动左侧两个 adapter。

**备选**：爬取后立即同步 LLM —— 拒绝，会拖垮 CDP 稳定性与任务超时控制。

### 2. Source 插件双注册（代码 + 配置）

- 运行时 `SourceRegistry.register_crawler(source_id, cls)` / `register_normalizer(...)`
- `config.json` → `sources.<id>.enabled`, `label`, 引用模块名
- MVP：`heimao`、`xhs` 在应用启动时注册

**理由**：配置可开关源；代码注册保证类型安全、便于单测 mock。

### 3. CrawlAdapter 契约

```python
# 概念接口（实现于 intel/sources/ 或 crawler/sources/）
class SourceCrawler(Protocol):
    source_id: str
    supports_fetch_detail: bool
    def crawl(self, ctx, task, partner, options) -> list[RawRecord]: ...
```

- `MonitorRunner` 编排：`for partner in task.partners: for source in task.sources: crawler.crawl(...)`
- heimao 适配：内部调用现有 `crawl_heimao` 逻辑，关键词来自 partner 主名+别名
- xhs 适配：内部调用 `crawl_xhs` + `xhs_detail.fetch_xhs_detail_via_modal`（弹窗路径）
- 登录：各 adapter 通过 `login_gate` 处理「任务开始门禁」「搜索页二次门禁」「详情弹窗」三条路径，不重复实现

**理由**：避免 `MonitorRunner` 内 `if source == 'heimao'` 扩散。

### 4. NormalizeAdapter 与 NormalizedRecord 最小公约

| 字段 | 说明 |
|------|------|
| `source` | 源 ID |
| `external_id` | 投诉编号 / 笔记 id |
| `url` | 可追溯链接 |
| `published_at` | ISO 时间（尽力解析） |
| `title`, `body` | AI 主输入 |
| `author`, `extra` | JSON 扩展 |
| `raw_payload` | 可选，保留源 dict |

- heimao：`reports.structure_heimao_record` → 映射
- xhs：新增 `structure_xhs_record` → 同一结构
- 未来源：新 Normalizer，扩展字段仅入 `extra`

### 5. IntelRecord 交付 schema

核心字段：`id`, `task_id`, `partner_id`, `partner_name`, `source`, `url`, `title`, `body`, `published_at`, `captured_at`, `relevance` (high|medium|low|noise), `risk_types[]`, `subject_hits[]`, `summary`, `export_tier` (include|review|exclude), `prompt_version`, `model`, `dedup_key`, `schema_version`.

**高召回策略**：prompt 要求「主体存疑标 medium，仅明确无关标 noise」；看板默认 filter `relevance in (high, medium)`；API 默认返回全量，由调用方按 `relevance_min` 过滤。

**权重外置**：IntelRecord 不含 `weighted_score`；文档说明业务系统对 `source` 加权。

### 6. SQLite 表设计（MVP）

- `partners`, `partner_aliases`（或 aliases JSON 列）
- `monitor_tasks`, `monitor_task_partners`, `monitor_task_sources`
- `raw_records` (task_id, partner_id, source, payload JSON, created_at)
- `intel_records` (交付主表，索引 task_id, partner_id, source, relevance)
- `analysis_jobs` (task_id, status, model, prompt_version, error, finished_at)

**理由**：单文件部署简单，与合作方/任务量级匹配。Postgres 留 Phase 2。

### 7. 云模型 AnalyzePipeline

- OpenAI-compatible chat/completions，`response_format` JSON
- 批大小 10–20，`max_body_chars` 截断（如 2000）
- 输入：partner 别名列表 + source + title + body
- 输出：`relevance`, `risk_types`, `summary`, `subject_hits`
- `config.analysis.api_key_env` 读环境变量，不落盘
- 失败重试 + `analysis_jobs` 记录；部分失败不阻塞整 task 标记 done（可配置 strict 模式）

### 8. Flask 路由与现有 UI 演进

- 新增 `/dashboard` 或扩展 `templates/index.html`  Tab
- 保留现有 `/api/crawl/*` 调试；新增 `/api/partners`, `/api/monitor/tasks`, `/api/monitor/run`, `/api/intel/records`, `/api/intel/export`, `/api/sources`
- 内网裸奔：无 middleware 鉴权（design 明确安全风险，接受内网前提）

### 9. config.json 新增块

```json
{
  "database": { "path": "data/intel.db" },
  "sources": {
    "heimao": { "enabled": true, "label": "黑猫投诉" },
    "xhs": { "enabled": true, "label": "小红书" }
  },
  "monitor": { "default_sources": ["heimao", "xhs"], "task_timeout_sec": 7200 },
  "analysis": {
    "endpoint": "https://api.example.com/v1/chat/completions",
    "model": "gpt-4o-mini",
    "api_key_env": "INTEL_LLM_API_KEY",
    "prompt_version": "v1-high-recall",
    "batch_size": 15,
    "max_body_chars": 2000
  }
}
```

既有 `auth.*`、`heimao.*`、`xhs.*` 仍由各 CrawlAdapter 读取，本变更不合并 auth 配置结构。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| MonitorRunner 与现有 `S.running` 爬取冲突 | 监测任务独立 job 状态；或互斥锁禁止并行 |
| 高召回导致 noise 进入 review 桶过多 | 看板默认 medium+；export_tier 区分 include/review |
| 云模型费用与延迟 | batch + token 预算；analysis 异步，UI 显示进度 |
| 新源 Normalize 映射不全 | `extra` + `raw_payload` 保留；schema_version 演进 |
| API 无鉴权 | 文档限定内网；Phase 2 可选 API Key |
| 小红书 structure 缺失 | MVP 任务中优先实现 `structure_xhs` |

## Migration Plan

1. **Phase 1**：SQLite schema + Partner/MonitorTask CRUD + SourceRegistry + heimao/xhs adapter 写入 raw → normalize → intel（可先 mock AI）
2. **Phase 2**：AnalyzePipeline 接云模型 + 看板 + 导出/API
3. **Phase 3**：文档化「新增第三源」模板（crawler + normalizer + config 一行）

回滚：关闭 `sources.*.enabled`；旧爬取 UI 仍可用；SQLite 可删文件重置。

## Open Questions

- Excel 导出是否按合作方分 sheet（MVP 可先单 sheet + source 列）
- `MonitorRunner` 与现有 Chrome 单实例：是否要求监测任务独占浏览器（建议互斥）
- 人工复核 UI（标记已处理）是否纳入 MVP（建议 P1，API 可先只读）
