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
- **且** `published_at` 必须为日期级 ISO 8601（`YYYY-MM-DD`）或空字符串
- **且** 解析 MUST 通过共用 `parse_published_date`，以 raw `captured_at`（或 raw `created_at`）为相对时间锚点
- **且** 扩展字段必须放入 `extra` JSON

#### Scenario: 详情时间覆盖列表

- **当** raw payload 同时含列表级 `time` 与详情级 `time`（detail-phase）
- **则** NormalizeAdapter MUST 优先采用详情时间解析 `published_at`

#### Scenario: heimao 归一化

- **当** 源为 heimao
- **则** NormalizeAdapter 必须基于 `reports.structure_heimao_record` 映射
- **且** `external_id` 必须为投诉编号

#### Scenario: xhs 归一化

- **当** 源为 xhs
- **则** NormalizeAdapter 必须基于 `structure_xhs_record`（待实现）映射
- **且** `external_id` 必须为笔记 id 或 url 稳定片段

### Requirement: 发布时间日期解析

系统 SHALL 提供 `parse_published_date(text, anchor_date)`，将黑猫/小红书常见时间文本规范为 `YYYY-MM-DD`。

#### Scenario: 绝对日期

- **当** 输入含 `YYYY-MM-DD` 或可解析的日期文本
- **则** 必须返回该日期字符串

#### Scenario: 相对时间

- **当** 输入为「N天前」「昨天」「今天」等相对表述
- **则** 必须基于 `anchor_date` 反推并返回 `YYYY-MM-DD`

#### Scenario: 无法解析

- **当** 输入为空或无法识别
- **则** 必须返回空字符串
- **且** 不得伪造日期

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

系统 SHALL 将 MonitorTask 与 CrawlAdapter 的 `max_pages` 参数定义为 **结果采集页数上限 M**：对 heimao 为 URL 分页最多 1..M，对 xhs 为最多 M 次滚动采集轮次；两源 MUST 使用一致的「第 i/M 页」日志与 RawRecord `page` 字段（`page` 为实际采集页码，1≤page≤i≤M）。当 `early_stop.enabled=true` 且检测到分页见底时，实际采集页数 i  MAY 小于 M。

#### Scenario: 黑猫分页语义不变

- **当** heimao CrawlAdapter 收到 `max_pages=M`
- **则** 必须访问搜索 URL 第 1 页起顺序分页，最多至第 M 页
- **且** 日志必须使用「黑猫第 i/M 页」格式

#### Scenario: 黑猫分页见底早停

- **当** `config.heimao.early_stop.enabled=true`
- **且** 已连续 `empty_pages_threshold` 页无新链接（`seen` 去重后 `new_count=0`）
- **且** 当前页码 i ≥ `min_pages`
- **则** 必须停止后续分页
- **且** 日志必须包含 `early_stop: heimao · reason=empty_page · stopped_at=i/M`

#### Scenario: 黑猫第 1 页零结果保护

- **当** `protect_first_page=true` 且第 1 页 `new_count=0`
- **则** 必须重试搜索或等待（次数 ≤ `empty_page_retry`），复用 `login_gate` 既有等待逻辑
- **且** 重试后仍无新链接时必须停止，不得无意义翻至第 2 页
- **且** 第 1 页零结果 alone 不得计入连续空页阈值（除非重试后仍空并停止）

#### Scenario: 小红书页数与黑猫对齐

- **当** xhs CrawlAdapter 收到 `max_pages=M`
- **则** 必须执行最多 M 次结果采集迭代（非「滚动次数」独立参数）
- **且** 起始日志必须使用「开始爬取小红书: {keyword} {M}页」，不得使用「滚动 N 次」作为主语义
- **且** 循环内日志必须使用「XHS第 i/M 页」或「小红书第 i/M 页」

#### Scenario: 小红书每页滚动预热一致

- **当** xhs 执行第 i 页采集（i 为 1..M）
- **则** 在 `query_selector_all` 之前 MUST 按 `config.xhs.scroll_times_per_page`（及 `scroll_pixels`、`scroll_wait_seconds`）滚动加载
- **且** 第 1 页与后续页 MUST 使用相同滚动预热逻辑

#### Scenario: 小红书 end 标志早停

- **当** `config.xhs.early_stop.enabled=true`
- **且** 滚动预热后页面出现 `end_texts` 中任一条（默认含 `- THE END -`）或匹配 `end_selectors`
- **且** 当前轮次 i ≥ `min_pages`
- **则** 必须停止后续滚动轮次
- **且** 日志必须包含 `early_stop: xhs · reason=end_marker · stopped_at=i/M`

#### Scenario: 小红书滚动饱和早停

- **当** `config.xhs.early_stop.enabled=true`
- **且** 连续 `saturation_rounds` 轮满足：本轮 `new_count=0` 且 note-item 总数较上一轮未增加
- **且** 当前轮次 i ≥ `min_pages`
- **则** 必须停止后续滚动轮次
- **且** 日志必须包含 `early_stop: xhs · reason=scroll_saturated · stopped_at=i/M`

#### Scenario: 早停关闭跑满上限

- **当** `config.{source}.early_stop.enabled=false`
- **则** 必须采集至第 M 页/轮（不因见底提前结束）
- **且** 不得应用本变更新增的 empty_page / end_marker / scroll_saturated 早停逻辑

#### Scenario: MonitorTask 单一 max_pages

- **当** MonitorRunner 为各源传递 `task.max_pages`
- **则** heimao 与 xhs 必须接收相同数值
- **且** 不得引入 per-source 独立页数字段

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

### Requirement: CrawlAdapter 列表批次模式

系统 SHALL 为 CrawlAdapter 提供 `crawl_list_batch(ctx, task, keyword_batch, options)`，内部固定 `fetch_detail=false`。

#### Scenario: 黑猫列表批次

- **当** heimao adapter 执行 crawl_list_batch
- **则** 必须调用 crawl_heimao(keyword, max_pages, fetch_detail=False)
- **且** 仍必须通过搜索框输入关键词

#### Scenario: 小红书列表批次

- **当** xhs adapter 执行 crawl_list_batch
- **则** 必须调用 crawl_xhs(..., fetch_detail=False)
- **且** 不要求登录即可列表（与现有 xhs-login-gate 一致）

### Requirement: CrawlAdapter 勘察详情模式

系统 SHALL 提供 `crawl_investigation(ctx, task, urls[], options)`，仅对给定 URL 列表抓详情。

#### Scenario: 黑猫勘察

- **当** heimao investigation 执行
- **则** 必须 new_page 打开详情
- **且** 未登录时必须走 login_gate

#### Scenario: 小红书勘察

- **当** xhs investigation 执行
- **则** 必须调用 `fetch_xhs_details_by_urls` 的弹窗实现（`xhs_detail.find_note_item_for_url` + `fetch_xhs_detail_via_modal`）
- **且** 不得对笔记 explore URL 使用 `page.goto` 作为主详情策略
- **且** fetch_detail=true 时必须走 xhs 登录门禁
- **且** 必须从关联 raw 读取搜索 keyword 用于 search_result 上下文与批量重搜

#### Scenario: 勘察 DOM 失败不阻塞任务

- **当** 单条 URL DOM 定位失败且已满足 skip/重搜规则
- **则** 必须标记该条 investigation 失败并继续队列
- **且** 不得因单条失败 abort 整个 monitor task

### Requirement: MonitorTask fetch_detail 语义

系统 SHALL 在 `crawl_mode=list_first` 下忽略 task 级 `fetch_detail=true` 对 routine crawl 的影响；详情仅由 investigation 阶段触发。

#### Scenario: 列表优先默认

- **当** crawl_mode=list_first
- **则** routine crawl 必须等价 fetch_detail=false
- **且** UI 必须说明详情在勘察阶段补抓

### Requirement: 源级 early_stop 配置

系统 SHALL 在 `config.heimao.early_stop` 与 `config.xhs.early_stop` 提供分源早停配置；`crawler_web.py` MUST 在 `crawl_heimao` / `crawl_xhs` 读取并应用。CrawlProfile API MAY 通过白名单暴露 `early_stop` 对象。

#### Scenario: 默认配置

- **当** 未在 `config.json` 中覆盖 early_stop
- **则** 必须使用 `config.py` DEFAULT 中各源 early_stop 默认值（`enabled=true`）
- **且** xhs 默认 `end_texts` 必须包含 `- THE END -`

#### Scenario: heimao early_stop 键

- **当** 读取 `config.heimao.early_stop`
- **则** 必须支持：`enabled`、`min_pages`、`empty_pages_threshold`、`protect_first_page`、`empty_page_retry`

#### Scenario: xhs early_stop 键

- **当** 读取 `config.xhs.early_stop`
- **则** 必须支持：`enabled`、`min_pages`、`protect_first_page`、`end_texts`、`end_selectors`、`saturation_rounds`

#### Scenario: list_first 与调试爬取共用

- **当** MonitorRunner 调用 `crawl_list_batch` 或客户端调用 `/api/crawl_heimao`、`/api/crawl_xhs`
- **则** 早停行为必须与对应源 `crawl_*` 一致
- **且** 不得仅在某一入口启用早停

