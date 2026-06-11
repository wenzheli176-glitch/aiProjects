## Why

当前系统具备黑猫/小红书采集与登录门禁能力，但缺少面向**商业合作伙伴风险排查**的情报层：无法按合作方名单持续监测、无法将多源信号归一为统一口径、也无法通过看板/API 交付给业务系统。业务侧需要对一组合作方进行高召回风险信号采集与 AI 打标，自行按 `source` 加权决策；因此需要在现有爬虫之上建设可扩展的多源情报平台。

## What Changes

- 新增 **合作方名单（Partner）** 与 **监测任务（MonitorTask）** 管理，以名单驱动监测（非单次 ad-hoc 关键词）。
- 引入 **Source 插件架构**：黑猫、小红书为 MVP 首批源；后续新源仅需实现 CrawlAdapter + NormalizeAdapter 并注册。
- 建立 **统一情报管道**：RawRecord → NormalizedRecord → PartnerMatcher → 云模型 AnalyzePipeline → **IntelRecord**（SQLite 持久化）。
- 新增 **内部风险看板**：按合作方/来源/相关度/风险类型筛选，默认展示 high + medium（高召回策略）。
- 新增 **交付能力**：JSON/Excel 导出 + REST API（`/api/intel/*`、`/api/monitor/*`），内网暂不做鉴权。
- 监测任务 **先手动触发**（UI 或 `POST /api/monitor/run`）；定时调度留待后续。
- 新增 `config.json` 配置块：`partners.*`、`monitor.*`、`sources.*`、`analysis.*`（云模型 OpenAI-compatible 端点、prompt 版本、批大小、token 预算）。
- 现有单次爬取 API（`crawler_web.py`）**保留**为单源调试入口；监测主路径逐步迁移至 MonitorRunner（非 BREAKING，并行共存）。

## Capabilities

### New Capabilities

- `partner-registry`：合作方名单 CRUD、别名/排除词/监测词、MonitorTask 创建与手动触发、SQLite 存储。
- `source-adapter`：SourceRegistry、CrawlAdapter/NormalizeAdapter 插件契约、heimao/xhs MVP 适配、源级 CrawlProfile 配置。
- `intel-pipeline`：NormalizedRecord 最小公约、PartnerMatcher、异步 AnalyzePipeline、IntelRecord schema、高召回 AI 打标与审计字段。
- `risk-dashboard-export-api`：统一风险看板、JSON/Excel 导出、REST API 分页过滤、`GET /api/sources` 列出已注册源。

### Modified Capabilities

- （无）既有 `openspec/specs/` 中登录门禁、弹窗详情等采集能力需求不变；本变更在其之上新增情报层，不修改既有 spec 行为。

## Impact

**站点与模块**

| 区域 | 影响 |
|------|------|
| heimao | 现有 `crawl_heimao`、`reports.structure_heimao_record` 封装为 heimao CrawlAdapter + NormalizeAdapter |
| xhs | 现有 `crawl_xhs`、`xhs_detail.py` 封装为 xhs CrawlAdapter；新增 `structure_xhs` 作为 NormalizeAdapter |
| login_gate | 各源 CrawlAdapter 复用 `login_gate.py` / `auth_utils.py` 门禁，不改动门禁语义 |
| 共用 | 新增 `intel/` 或 `core/` 包：registry、matcher、analyze、db；Flask 路由扩展 |

**新增/变更 config.json 字段（概要）**

- `sources.heimao` / `sources.xhs`：`enabled`、`label`、crawler/normalizer 模块引用
- `monitor.*`：默认来源列表、任务超时
- `analysis.*`：`endpoint`、`model`、`api_key_env`、`prompt_version`、`batch_size`、`max_body_chars`、`relevance_defaults`
- `database.path`：SQLite 文件路径

**依赖与系统**

- 新增 SQLite（stdlib `sqlite3` 或轻量 ORM）
- 云模型 HTTP 客户端（OpenAI-compatible JSON 模式）
- 可选：`openpyxl` 或等价库用于 Excel 导出

**非目标（本变更不包含）**

- 综合风险权重评分、法律结论自动化
- API 鉴权、定时 cron、截图存证、embedding 去重
- 第三数据源的具体实现（仅预留插件契约与注册机制）
