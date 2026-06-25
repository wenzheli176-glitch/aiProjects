# heimao-login-gate

黑猫投诉登录检测、微博 SSO、sid、等待续跑。实现：`login_gate.py`（heimao 分支）、`heimao_session.py`、`crawler_web.crawl_heimao`。

### 需求：爬取详情须已登录微博

当 `fetch_detail=true` 时，系统必须在抓取前验证黑猫详情可访问。

#### 场景：任务开始门禁

- **当** `fetch_detail=true` 时
- **则** `ensure_login_for_detail` 必须在任务开始时执行一次 `heimao_ready_for_detail_crawl`
- **且** 失败时须通过 `wait_for_site_login` 进入 `WAITING_LOGIN`

#### 场景：仅抓列表

- **当** `fetch_detail=false` 且 `require_login=false` 时
- **则** 不得在任务开始时强制进入登录等待

### 需求：微博 SSO 登录页

#### 场景：等待期间打开登录

- **当** 为 `heimao` 进入 `WAITING_LOGIN` 时
- **则** `open_heimao_login_page` 必须优先打开 `passport.weibo.com/sso/signin?entry=general&source=heimao&url=...`
- **且** 轮询期间不得离开微博扫码页（`_heimao_login_ok_after_wait` 使用 Cookie + 页面文案，不强制跳转）

### 需求：实时会话与可选详情探测

#### 场景：具备详情爬取条件

- **当** 执行 `heimao_ready_for_detail_crawl` 时
- **则** 必须通过 `heimao_is_logged_in_live` 检查浏览器 SUB
- **且** 当存在 sid 且 `detail_probe_enabled` 为 true 时，可以执行 `probe_heimao_detail_access`
- **且** 探测结果不明确（无正文且无登录墙）时，不得单独因此判定未登录

#### 场景：实时检测时避免离开搜索页

- **当** 已在 `tousu.sina.com.cn` 且不在微博 passport 页时
- **则** `heimao_is_logged_in_live(navigate=False)` 不得无故再次跳转首页

### 需求：详情 URL 须带 sid

#### 场景：详情链接需要 sid

- **当** 打开投诉详情 URL 时
- **则** 系统必须通过 `ensure_heimao_detail_url` 从页面/Cookie/搜索链接附加 `sid`
- **且** 无法附加 sid 时必须跳过该详情

### 需求：搜索无结果时触发登录等待

搜索 HTML 中投诉链接数为 0 时，系统 MUST 先分类空搜索原因；**仅**在明确登录失效时进入 `WAITING_LOGIN`。不得仅因缺少 sid 且无链接而触发登录等待（除非 `heimao.empty_search.login_on_missing_sid=true`）。除登录恢复外，**不得**对空搜索结果执行重搜或重试。

#### 场景：有 sid 但无链接

- **当** 存在 sid 但关键词无投诉链接
- **则** 系统 MUST 记录警告
- **且** MUST 立即结束当前关键词爬取（返回空结果）
- **且** MUST NOT 重搜或进入 `WAITING_LOGIN`

#### 场景：无 sid 但微博 SUB 有效且无登录墙

- **当** 投诉链接数为 0
- **且** 无 sid
- **且** `heimao_browser_has_weibo_session` 为 true
- **且** 页面无 `heimao_page_shows_login_prompt` 与 `page_has_login_fail_text`
- **则** `heimao_wait_if_search_empty` MUST NOT 调用 `wait_for_site_login`
- **且** MUST 记录「无 sid，会话仍有效，跳过」类 WARN
- **且** MUST 立即结束当前关键词并继续下一关键词或合作方
- **且** MUST NOT 重搜

#### 场景：明确登录失效

- **当** 投诉链接数为 0
- **且** 满足以下任一：`heimao_browser_has_weibo_session` 为 false；页面出现登录墙或 `login_fail_texts`；或 `heimao.empty_search.login_on_missing_sid=true` 且无 sid
- **则** `heimao_wait_if_search_empty` MUST 进入 `WAITING_LOGIN`
- **且** 登录成功后 MUST 通过 `redo_search` 回调重新搜索（**唯一**允许的空搜 redo 路径）

#### 场景：页面过短或明显拦截

- **当** 投诉链接数为 0
- **且** HTML 长度低于 `heimao.min_html_len`
- **且** 无法确认为「正常空结果页」
- **则** 系统 MUST 按登录/拦截处理并 MAY 进入 `WAITING_LOGIN`

### 需求：黑猫空搜不重试直接跳过

系统 SHALL 在黑猫关键词搜索无投诉链接时立即跳过，不进行 `empty_page_retry` 或其他空结果重试。

#### 场景：第 1 页无链接即跳过

- **当** 搜索后投诉链接数为 0
- **且** 分类为 `no_results` 或 `empty_uncertain`
- **则** `crawl_heimao` MUST 返回空列表
- **且** MUST NOT 调用 `_redo_heimao_search`（除非刚完成登录恢复的 `redo_search`）
- **且** `heimao.early_stop.empty_page_retry` 默认 MUST 为 `0`

#### 场景：继续下一关键词

- **当** 当前关键词因空结果被跳过
- **则** heimao CrawlAdapter MUST 立即进入下一关键词或下一合作方
- **且** RunMetrics MUST 递增 `heimao_skipped_empty`
### 需求：详情鉴权失败判定

#### 场景：黑猫详情页

- **当** 详情 JS 返回空正文时
- **则** `is_heimao_detail_auth_failure` 仅在有登录墙/失败文案或缺少微博 SUB 时返回 true
- **且** 有有效 SUB 且无登录提示的空正文不得触发重新登录

### 需求：不在每条详情前做登录门禁

#### 场景：详情循环

- **当** 以 `fetch_detail=true` 遍历投诉链接时
- **则** 不得在每条详情前调用 `ensure_login_for_detail`
- **且** 仅当 `is_heimao_detail_auth_failure` 为 true 时才可以调用 `wait_for_site_login`

### 需求：跳过向未登录浏览器注入过期配置 Cookie

与小红书相同：浏览器无 SUB 但配置中有微博 Cookie 时，在 `skip_inject_if_browser_logged_out` 为 true 时跳过注入。
