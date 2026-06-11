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

## ADDED Requirements

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
