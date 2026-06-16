## ADDED Requirements

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
- **则** 必须使用弹窗详情路径（xhs_detail）
- **且** fetch_detail=true 时必须走 xhs 登录门禁

### Requirement: MonitorTask fetch_detail 语义

系统 SHALL 在 `crawl_mode=list_first` 下忽略 task 级 `fetch_detail=true` 对 routine crawl 的影响；详情仅由 investigation 阶段触发。

#### Scenario: 列表优先默认

- **当** crawl_mode=list_first
- **则** routine crawl 必须等价 fetch_detail=false
- **且** UI 必须说明详情在勘察阶段补抓
