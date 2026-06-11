## ADDED Requirements

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

## MODIFIED Requirements

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
