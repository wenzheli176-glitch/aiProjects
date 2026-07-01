## MODIFIED Requirements

### Requirement: CrawlAdapter 契约

每个数据源 MUST 实现 CrawlAdapter：`source_id`、`crawl(ctx, task, partner, options) -> list[RawRecord]`，并可声明 `supports_fetch_detail`。`options.max_pages` MUST 表示该源的结果采集页数（滚动采集轮次上限）；heimao 与 xhs MUST 使用相同语义，不得对 heimao 单独使用 URL 分页页数含义。

#### Scenario: heimao 适配现有爬虫

- **当** heimao CrawlAdapter 执行爬取
- **则** 必须复用 `crawler_web.py` / `login_gate.py` / `heimao_session.py` 的登录与搜索逻辑
- **且** 结果必须写入 SQLite `raw_records`，含 `task_id`、`partner_id`、`source=heimao`
- **且** 每条 raw 的 `page` 字段必须为 1..`max_pages` 中的滚动采集轮次

#### Scenario: xhs 适配弹窗详情

- **当** xhs CrawlAdapter 且 `fetch_detail=true`
- **则** 必须通过 `xhs_detail.py` 弹窗路径抓取详情
- **且** 不得将 `goto(/explore/)` 作为主详情策略（与 `xhs-detail-modal` spec 一致）
- **且** `max_pages` 必须控制采集轮次数，每条 raw 的 `page` 字段必须为 1..`max_pages`

#### Scenario: 登录门禁三条路径

- **当** 某源爬取需要登录
- **则** CrawlAdapter 必须通过 `login_gate.py` 处理任务开始门禁、搜索页二次门禁、详情弹窗路径
- **且** 不得在各 adapter 内重复实现独立登录轮询逻辑

### Requirement: max_pages 跨源统一语义

系统 SHALL 将 MonitorTask 与 CrawlAdapter 的 `max_pages` 参数定义为 **结果采集页数上限 M**：对 heimao 与 xhs 均为最多 M 次滚动采集轮次；两源 MUST 使用一致的「第 i/M 页」日志与 RawRecord `page` 字段（`page` 为实际采集轮次，1≤page≤i≤M）。当 `early_stop.enabled=true` 且检测到列表见底时，实际轮次 i MAY 小于 M。

#### Scenario: 黑猫滚动采集语义

- **当** heimao CrawlAdapter 收到 `max_pages=M`
- **则** 必须在搜索框提交关键词后，执行最多 M 轮滚动采集
- **且** 每轮 MUST 在解析 DOM 前按 `config.heimao.scroll_*` 滚动加载
- **且** 日志必须使用「黑猫第 i/M 页」格式，并 SHOULD 输出「黑猫下拉加载: N 次滚动」

#### Scenario: 黑猫第 1 轮零结果保护

- **当** `protect_first_page=true` 且第 1 轮 `new_count=0`
- **且** `empty_page_retry=0`（默认）
- **则** 必须立即停止当前关键词（`reason=empty_page`）
- **且** MUST NOT 因缺少 sid 进入 `WAITING_LOGIN`
- **且** MUST NOT 重搜同一关键词（除非刚完成登录恢复的 `redo_search`）

#### Scenario: 黑猫滚动饱和早停

- **当** `config.heimao.early_stop.enabled=true`
- **且** 连续 `saturation_rounds` 轮满足：本轮 `new_count=0` 且 DOM 投诉链接总数较上一轮未增加
- **且** 当前轮次 i ≥ `min_pages`
- **则** 必须停止后续滚动轮次
- **且** 日志必须包含 `early_stop: heimao · reason=scroll_saturated · stopped_at=i/M`

#### Scenario: 黑猫显式配置 empty_page_retry 大于 0

- **当** 管理员显式设置 `heimao.early_stop.empty_page_retry>0`
- **且** `protect_first_page=true` 且第 1 轮 `new_count=0`
- **则** MAY 重试搜索（次数 ≤ `empty_page_retry`）
- **且** 重试后仍无新链接时必须停止

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
- **且** 不得应用 empty_page / end_marker / scroll_saturated 早停逻辑

#### Scenario: MonitorTask 单一 max_pages

- **当** MonitorRunner 为各源传递 `task.max_pages`
- **则** heimao 与 xhs 必须接收相同数值
- **且** 不得引入 per-source 独立页数字段

## ADDED Requirements

### Requirement: heimao 滚动加载配置

系统 SHALL 在 `config.heimao` 提供滚动加载参数；`crawl_heimao` MUST 读取并应用；CrawlProfile API MAY 通过白名单暴露下列键。

#### Scenario: 默认 scroll 配置

- **当** 未在 `config.json` 中覆盖 scroll 参数
- **则** 必须使用 `config.py` DEFAULT：`scroll_times_per_page=3`、`scroll_pixels=1500`、`scroll_wait_seconds=2`、`scroll_to_bottom=true`

#### Scenario: 内部滚动容器

- **当** 管理员设置 `scroll_container_selector` 为非空 CSS 选择器
- **则** `heimao_scroll_load_batch` MUST 滚动该容器而非仅 window

#### Scenario: heimao 关键词数量

- **当** `max_keywords_per_partner=0`（默认）
- **则** heimao CrawlAdapter MUST 对合作方爬取全部 `partner_search_keywords`
- **当** `max_keywords_per_partner>0`
- **则** MUST 仅爬取前 N 个关键词

## MODIFIED Requirements

### Requirement: 源级 early_stop 配置

系统 SHALL 在 `config.heimao.early_stop` 与 `config.xhs.early_stop` 提供分源早停配置；`crawler_web.py` MUST 在 `crawl_heimao` / `crawl_xhs` 读取并应用。CrawlProfile API MAY 通过白名单暴露 `early_stop` 对象。

#### Scenario: 默认配置

- **当** 未在 `config.json` 中覆盖 early_stop
- **则** 必须使用 `config.py` DEFAULT 中各源 early_stop 默认值（`enabled=true`）
- **且** heimao 默认 `empty_page_retry` 必须为 `0`
- **且** heimao 默认 `saturation_rounds` 必须为 `2`
- **且** xhs 默认 `end_texts` 必须包含 `- THE END -`

#### Scenario: heimao early_stop 键

- **当** 读取 `config.heimao.early_stop`
- **则** 必须支持：`enabled`、`min_pages`、`protect_first_page`、`empty_page_retry`、`saturation_rounds`

#### Scenario: xhs early_stop 键

- **当** 读取 `config.xhs.early_stop`
- **则** 必须支持：`enabled`、`min_pages`、`protect_first_page`、`end_texts`、`end_selectors`、`saturation_rounds`

#### Scenario: list_first 与调试爬取共用

- **当** MonitorRunner 调用 `crawl_list_batch` 或客户端调用 `/api/crawl_heimao`、`/api/crawl_xhs`
- **则** 早停行为必须与对应源 `crawl_*` 一致
- **且** 不得仅在某一入口启用早停
