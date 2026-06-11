## 1. 基础设施与存储

- [x] 1.1 新增 `intel/db.py`：SQLite 连接、迁移/init schema（partners、monitor_tasks、raw_records、intel_records、analysis_jobs）
- [x] 1.2 在 `config.py` / `config.json` 增加 `database.path`、`sources.*`、`monitor.*`、`analysis.*` 默认值
- [x] 1.3 实现 Partner CRUD 数据访问层与 `GET/POST/PUT/DELETE /api/partners`

## 2. Source 插件与 MVP 适配

- [x] 2.1 实现 `SourceRegistry`（register/get crawler & normalizer）
- [x] 2.2 实现 `heimao` CrawlAdapter：封装现有 `crawl_heimao`，写入 raw_records
- [x] 2.3 实现 `xhs` CrawlAdapter：封装 `crawl_xhs` + `xhs_detail` 弹窗详情，写入 raw_records
- [x] 2.4 实现 `heimao` NormalizeAdapter：基于 `reports.structure_heimao_record`
- [x] 2.5 新增 `structure_xhs_record` 与 `xhs` NormalizeAdapter
- [x] 2.6 实现 `GET /api/sources` 返回已注册且 enabled 的源

## 3. 监测任务与编排

- [x] 3.1 实现 MonitorTask CRUD 与 `POST /api/monitor/tasks`、`GET /api/monitor/tasks/{id}`
- [x] 3.2 实现 `MonitorRunner`：partner × source 编排、状态机 queued→crawling→analyzing→done|failed
- [x] 3.3 实现 `POST /api/monitor/run` 手动触发与浏览器/任务互斥策略
- [x] 3.4 实现 PartnerMatcher（别名、排除词、subject_hits）

## 4. AI 分析管道

- [x] 4.1 实现 `AnalyzePipeline`：OpenAI-compatible 批调用、JSON 解析、重试
- [x] 4.2 实现高召回 prompt（`prompt_version=v1-high-recall`）与 body 截断
- [x] 4.3 写入 intel_records（dedup_key、audit 字段）与 analysis_jobs 状态
- [x] 4.4 实现 `GET /api/intel/records` 分页与过滤参数

## 5. 看板与导出

- [x] 5.1 新增看板 UI（合作方/来源/相关度/风险类型筛选，默认 high+medium）
- [x] 5.2 实现 JSON 导出（含 schema_version）
- [x] 5.3 实现 Excel 导出（含数据来源列）
- [x] 5.4 实现 `GET /api/intel/export?format=json|xlsx`

## 6. 文档与扩展模板

- [x] 6.1 更新 `openspec/config.yaml` context：多源情报平台定位
- [x] 6.2 编写「新增第三数据源」开发者说明（CrawlAdapter + NormalizeAdapter + config 注册）
- [x] 6.3 API 对接说明：source 权重外置、relevance 语义、无鉴权前提

## 7. 手动验证（监测全链路）

- [x] 7.1 创建 2 个合作方（含别名），手动触发 heimao+xhs 监测任务，确认 raw_records 入库
- [x] 7.2 未登录 heimao/xhs 时：确认 login_gate 等待登录后续跑，任务不写入无效详情（沿用既有门禁）
- [x] 7.3 xhs 详情：确认弹窗路径抓取成功，无 App 墙误报为有效正文
- [x] 7.4 AI 分析完成后：看板默认展示 medium+，API 可按 source/partner 过滤
- [x] 7.5 导出 JSON/Excel，确认每条含 `source` 与 `schema_version`
