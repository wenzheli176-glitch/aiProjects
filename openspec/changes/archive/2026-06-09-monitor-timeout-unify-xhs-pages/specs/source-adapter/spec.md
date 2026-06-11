## ADDED Requirements

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

## MODIFIED Requirements

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
