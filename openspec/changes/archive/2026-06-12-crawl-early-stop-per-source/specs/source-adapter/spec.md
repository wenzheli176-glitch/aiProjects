## MODIFIED Requirements

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

## ADDED Requirements

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
