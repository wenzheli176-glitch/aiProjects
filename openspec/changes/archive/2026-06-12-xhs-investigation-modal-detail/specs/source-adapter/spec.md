## MODIFIED Requirements

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
