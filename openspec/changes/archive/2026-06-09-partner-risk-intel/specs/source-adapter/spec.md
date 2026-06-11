## ADDED Requirements

### Requirement: SourceRegistry 插件注册

系统 SHALL 提供 SourceRegistry，通过 `source_id` 解析 CrawlAdapter 与 NormalizeAdapter；新增数据源不得修改 MonitorRunner、IntelRecord 核心字段或 API 响应结构。

#### Scenario: 注册 MVP 源

- **当** 应用启动且 `config.sources.heimao.enabled=true`
- **则** Registry 必须注册 `source_id=heimao` 的 crawler 与 normalizer
- **且** 对 `xhs` 同理

#### Scenario: 列出已注册源

- **当** 客户端调用 `GET /api/sources`
- **则** 必须返回已注册且 enabled 的源列表，含 `source_id` 与 `label`
- **且** 未 enabled 的源不得出现在默认 MonitorTask 来源选项中

#### Scenario: 禁用源不可爬取

- **当** `config.sources.<id>.enabled=false`
- **则** MonitorRunner 不得调用该源的 CrawlAdapter
- **且** 若任务显式包含禁用源必须返回明确错误

### Requirement: CrawlAdapter 契约

每个数据源 MUST 实现 CrawlAdapter：`source_id`、`crawl(ctx, task, partner, options) -> list[RawRecord]`，并可声明 `supports_fetch_detail`。

#### Scenario: heimao 适配现有爬虫

- **当** heimao CrawlAdapter 执行爬取
- **则** 必须复用 `crawler_web.py` / `login_gate.py` / `heimao_session.py` 的登录与搜索逻辑
- **且** 结果必须写入 SQLite `raw_records`，含 `task_id`、`partner_id`、`source=heimao`

#### Scenario: xhs 适配弹窗详情

- **当** xhs CrawlAdapter 且 `fetch_detail=true`
- **则** 必须通过 `xhs_detail.py` 弹窗路径抓取详情
- **且** 不得将 `goto(/explore/)` 作为主详情策略（与 `xhs-detail-modal` spec 一致）

#### Scenario: 登录门禁三条路径

- **当** 某源爬取需要登录
- **则** CrawlAdapter 必须通过 `login_gate.py` 处理任务开始门禁、搜索页二次门禁、详情弹窗路径
- **且** 不得在各 adapter 内重复实现独立登录轮询逻辑

### Requirement: NormalizeAdapter 契约

每个数据源 MUST 实现 NormalizeAdapter，将源特有 RawRecord 映射为 NormalizedRecord 最小公约字段。

#### Scenario: NormalizedRecord 必填字段

- **当** NormalizeAdapter 输出记录
- **则** 每条必须包含 `source`、`external_id`、`url`、`title`、`body`
- **且** `published_at` 必须尽力解析为 ISO 8601 或留空；扩展字段必须放入 `extra` JSON

#### Scenario: heimao 归一化

- **当** 源为 heimao
- **则** NormalizeAdapter 必须基于 `reports.structure_heimao_record` 映射
- **且** `external_id` 必须为投诉编号

#### Scenario: xhs 归一化

- **当** 源为 xhs
- **则** NormalizeAdapter 必须基于 `structure_xhs_record`（待实现）映射
- **且** `external_id` 必须为笔记 id 或 url 稳定片段

### Requirement: 源级 CrawlProfile 配置

系统 SHALL 允许在 `config.json` 的 `sources.<id>` 下配置标签、enabled 及源特有爬取参数，而不在 MonitorTask 或 IntelRecord 中硬编码源差异。

#### Scenario: 配置读取

- **当** CrawlAdapter 初始化
- **则** 必须从 `config.sources.<source_id>` 与既有 `auth.*`、`heimao.*`、`xhs.*` 读取参数
- **且** 新增第三源时仅需新增配置块与 adapter 实现

#### Scenario: 新增源不改交付 schema

- **当** 注册 future 源（如 weibo）
- **则** IntelRecord API 与导出 JSON 的顶层字段集合必须不变
- **且** 源特有字段仅允许出现在 `extra` 或 `raw_payload`
