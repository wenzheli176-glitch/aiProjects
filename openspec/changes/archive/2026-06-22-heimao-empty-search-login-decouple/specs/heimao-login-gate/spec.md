## MODIFIED Requirements

### Requirement: 搜索无结果时触发登录等待

搜索 HTML 中投诉链接数为 0 时，系统 MUST 先分类空搜索原因；**仅**在明确登录失效时进入 `WAITING_LOGIN`。不得仅因缺少 sid 且无链接而触发登录等待（除非 `heimao.empty_search.login_on_missing_sid=true`）。除登录恢复外，**不得**对空搜索结果执行重搜或重试。

#### Scenario: 有 sid 但无链接

- **WHEN** 存在 sid 但关键词无投诉链接
- **THEN** 系统 MUST 记录警告
- **且** MUST 立即结束当前关键词爬取（返回空结果）
- **且** MUST NOT 重搜、后缀剥离或进入 `WAITING_LOGIN`

#### Scenario: 无 sid 但微博 SUB 有效且无登录墙

- **WHEN** 投诉链接数为 0
- **且** 无 sid
- **且** `heimao_browser_has_weibo_session` 为 true
- **且** 页面无 `heimao_page_shows_login_prompt` 与 `page_has_login_fail_text`
- **THEN** `heimao_wait_if_search_empty` MUST NOT 调用 `wait_for_site_login`
- **且** MUST 记录「无 sid，会话仍有效，跳过」类 WARN
- **且** MUST 立即结束当前关键词并继续下一关键词或合作方
- **且** MUST NOT 重搜或登记 deferred

#### Scenario: 明确登录失效

- **WHEN** 投诉链接数为 0
- **且** 满足以下任一：`heimao_browser_has_weibo_session` 为 false；页面出现登录墙或 `login_fail_texts`；或 `heimao.empty_search.login_on_missing_sid=true` 且无 sid
- **THEN** `heimao_wait_if_search_empty` MUST 进入 `WAITING_LOGIN`
- **且** 登录成功后 MUST 通过 `redo_search` 回调重新搜索（**唯一**允许的空搜 redo 路径）

#### Scenario: 页面过短或明显拦截

- **WHEN** 投诉链接数为 0
- **且** HTML 长度低于 `heimao.min_html_len`
- **且** 无法确认为「正常空结果页」
- **THEN** 系统 MUST 按登录/拦截处理并 MAY 进入 `WAITING_LOGIN`

## REMOVED Requirements

### Requirement: 搜索无结果时触发登录等待

#### Scenario: 无投诉链接且无 sid

**Reason**: 「无 sid + 无链接」与登录失效混为一谈，导致误触发 WAITING_LOGIN。

**Migration**: 默认改为 Scenario「无 sid 但微博 SUB 有效且无登录墙」；若需旧行为，设置 `heimao.empty_search.login_on_missing_sid=true`。

## ADDED Requirements

### Requirement: 黑猫空搜不重试直接跳过

系统 SHALL 在黑猫关键词搜索无投诉链接时立即跳过，不进行 empty_page_retry、后缀再搜、deferred 轮末重试或其他空结果重试。

#### Scenario: 第 1 页无链接即跳过

- **WHEN** 搜索后投诉链接数为 0
- **且** 分类为 `no_results` 或 `empty_uncertain`
- **THEN** `crawl_heimao` MUST 返回空列表
- **且** MUST NOT 调用 `_redo_heimao_search`（除非刚完成登录恢复的 `redo_search`）
- **且** `heimao.early_stop.empty_page_retry` 默认 MUST 为 `0`

#### Scenario: 继续下一关键词

- **WHEN** 当前关键词因空结果被跳过
- **THEN** heimao CrawlAdapter MUST 立即进入 `partner_search_keywords` 中的下一关键词或下一合作方
- **且** RunMetrics MUST 递增 `heimao_skipped_empty`
