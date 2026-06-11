# source-adapter Specification

## Purpose
TBD - created by archiving change partner-risk-intel. Update Purpose after archive.
## Requirements
### Requirement: SourceRegistry 插件注册

系统 SHALL 提供 SourceRegistry，通过 `source_id` 解析 CrawlAdapter 与 NormalizeAdapter；新增数据源不得修改 MonitorRunner、IntelRecord 核心字段或 API 响应结构。已注册源的 `enabled` 与 `label` MUST 可通过数据源管理 API/UI 配置；CrawlProfile 常用参数 MUST 可通过 `profile` API 配置，但注册新 `source_id` MUST 仍通过代码完成。

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

每个数据源 MUST 实现 CrawlAdapter：`source_id`、`crawl(ctx, task, partner, options) -> list[RawRecord]`，并可声明 `supports_fetch_detail`。`options.max_pages` MUST 表示该源的结果采集页数，语义与 heimao URL 分页页数一致；xhs 通过滚动实现同等页数，不得使用独立的「滚动次数」含义。

#### Scenario: heimao 适配现有爬虫

- **当** heimao CrawlAdapter 执行爬取
- **则** 必须复用 `crawler_web.py` / `login_gate.py` / `heimao_session.py` 的登录与搜索逻辑
- **且** 结果必须写入 SQLite `raw_records`，含 `task_id`、`partner_id`、`source=heimao`
- **且** 每条 raw 的 `page` 字段必须为 1..`max_pages` 中的 URL 页码

#### Scenario: xhs 适配弹窗详情

- **当** xhs CrawlAdapter 且 `fetch_detail=true`
- **则** 必须通过 `xhs_detail.py` 弹窗路径抓取详情
- **且** 不得将 `goto(/explore/)` 作为主详情策略（与 `xhs-detail-modal` spec 一致）
- **且** `max_pages` 必须控制采集轮次数，每条 raw 的 `page` 字段必须为 1..`max_pages`

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

### Requirement: max_pages 跨源统一语义

系统 SHALL 将 MonitorTask 与 CrawlAdapter 的 `max_pages` 参数定义为 **结果采集页数 M**：对 heimao 为 URL 分页 1..M，对 xhs 为 M 次滚动采集轮次；两源 MUST 使用一致的「第 i/M 页」日志与 RawRecord `page` 字段 1..M。

#### Scenario: 黑猫分页语义不变

- **当** heimao CrawlAdapter 收到 `max_pages=M`
- **则** 必须访问搜索 URL 第 1 至 M 页
- **且** 日志必须使用「黑猫第 i/M 页」格式

#### Scenario: 小红书页数与黑猫对齐

- **当** xhs CrawlAdapter 收到 `max_pages=M`
- **则** 必须执行 M 次结果采集迭代（非「滚动次数」独立参数）
- **且** 起始日志必须使用「开始爬取小红书: {keyword} {M}页」，不得使用「滚动 N 次」作为主语义
- **且** 循环内日志必须使用「XHS第 i/M 页」或「小红书第 i/M 页」

#### Scenario: 小红书每页滚动预热一致

- **当** xhs 执行第 i 页采集（i 为 1..M）
- **则** 在 `query_selector_all` 之前 MUST 按 `config.xhs.scroll_times_per_page`（及 `scroll_pixels`、`scroll_wait_seconds`）滚动加载
- **且** 第 1 页与后续页 MUST 使用相同滚动预热逻辑

#### Scenario: MonitorTask 单一 max_pages

- **当** MonitorRunner 为各源传递 `task.max_pages`
- **则** heimao 与 xhs 必须接收相同数值
- **且** 不得在本变更中引入 per-source 独立页数字段

### Requirement: 数据源管理 UI

系统 SHALL 在统一 Web 壳提供「数据源」Tab，展示 SourceRegistry 已注册源；管理员可切换 enabled、编辑 label 与 CrawlProfile 常用参数；UI MUST 声明新增数据源需在代码中注册 Adapter，无法仅靠配置添加。

#### Scenario: 展示已注册源

- **当** 用户打开数据源 Tab
- **则** 必须列出 `registry` 中已注册且 config 存在的 source_id
- **且** 每项必须显示 label、enabled 状态、是否支持 fetch_detail

#### Scenario: 不可 UI 添加源

- **当** 用户查看数据源 Tab
- **则** 界面必须包含说明：新源需开发 CrawlAdapter/NormalizeAdapter 并注册
- **且** 不得提供「添加数据源」向导创建未注册 source_id

#### Scenario: 管理员切换启用

- **当** 管理员关闭某源 enabled 并保存
- **则** `config.sources.<id>.enabled` 必须为 false
- **且** `GET /api/sources` 默认列表不得包含该源

#### Scenario: 操作员只读

- **当** 操作员打开数据源 Tab
- **则** 可查看源列表与参数
- **但** 保存按钮必须禁用或隐藏；PATCH 必须 403

### Requirement: 数据源分区写 API

系统 SHALL 提供 `PATCH /api/sources/{source_id}` 与 `GET/PATCH /api/sources/{source_id}/profile`，仅允许修改已注册 source_id；写入 MUST deep_merge 至 `config.json` 对应子树。

#### Scenario: 更新 label 与 enabled

- **当** 管理员 `PATCH /api/sources/heimao` 提交 `{enabled:false, label:"黑猫"}`
- **则** 必须更新 `config.sources.heimao` 对应字段

#### Scenario: 更新 CrawlProfile

- **当** 管理员 `PATCH /api/sources/xhs/profile` 提交 tier A 字段（如 default_max_pages、scroll_times_per_page）
- **则** 必须 merge 至 `config.xhs.*`
- **且** 不得接受未在白名单内的键（或忽略并警告）

#### Scenario: 未注册源不可 PATCH

- **当** `PATCH /api/sources/weibo` 且 registry 未注册 weibo
- **则** 必须返回 404 或 400

#### Scenario: 爬取进行中禁止保存

- **当** `S.running=true` 且管理员 PATCH profile
- **则** 必须拒绝保存（与现有 config POST 行为一致）

### Requirement: NormalizeProfile 可配置清洗

系统 SHALL 为 heimao、xhs 提供 `config.{source_id}.normalize.*` 配置块；NormalizeAdapter MUST 读取并应用；数据源 Tab MUST 分组展示「采集参数」与「清洗/归一化」。

#### Scenario: heimao 清洗开关

- **当** `heimao.normalize.include_reply_in_body=false`
- **则** 归一化 body 不得包含 reply 文本
- **且** 默认值必须与变更前行为一致（均为 true）

#### Scenario: 正文长度截断

- **当** `normalize.body_max_chars>0`
- **则** NormalizeAdapter 必须在写入 NormalizedRecord 前截断 body
- **且** 截断策略 MUST 在 registry help 中说明（字符数、非 token）

#### Scenario: profile API 暴露 normalize 键

- **当** `GET /api/sources/heimao/profile`
- **则** 响应必须包含 normalize 键列表与当前值
- **且** `PATCH` 仅接受白名单 normalize 键

