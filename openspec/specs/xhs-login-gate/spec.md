# xhs-login-gate

小红书登录检测、搜索页门禁、等待续跑。实现：`login_gate.py`（xhs 分支）、`crawler_web.crawl_xhs`。

### 需求：任务开始时详情爬取须已登录

当 `fetch_detail=true` 时，系统必须在抓取笔记前验证搜索页可访问。

#### 场景：开始时未登录或会话过期

- **当** 以 `fetch_detail=true` 启动小红书爬取
- **且** `xhs_check_logged_in_on_search` 打开该关键词的真实搜索 URL
- **且** `xhs_search_page_needs_login` 返回 true（登录墙、失败文案，或等待/滚动后 `.note-item` 为 0）
- **则** 爬取必须通过 `wait_for_site_login` 进入 `WAITING_LOGIN`
- **且** 在登录成功前不得抓取详情

#### 场景：仅抓列表

- **当** `fetch_detail=false` 且 `require_login=false` 时
- **则** 系统不得在任务开始时强制进入登录等待

### 需求：在搜索页检测登录（不能仅凭 Cookie）

不得仅凭 explore 页的 Cookie 推断已登录。

#### 场景：Cookie 过期且搜索无结果

- **当** 位于 `search_result` URL
- **且** 未出现配置的登录失败文案
- **且** 在 `search_results_wait_ms` 等待并滚动重试后 `.note-item` 仍为 0
- **则** 登录检测必须失败（视为未登录或会话过期），即使存在 `web_session`/`webId` Cookie

#### 场景：搜索页出现登录墙

- **当** 页面正文匹配 `auth.xhs.login_fail_texts` 或 `page_has_login_wall` 时
- **则** 登录检测必须失败

#### 场景：搜索可正常访问

- **当** 搜索页至少存在一个 `.note-item`
- **且** 未检测到登录墙文案时
- **则** 登录检测必须通过

### 需求：打开搜索后的二次门禁

#### 场景：首次检测后搜索仍被拦截

- **当** 打开搜索后执行 `xhs_wait_if_search_blocked`
- **且** 搜索仍不可用
- **则** 系统必须等待登录、重新打开搜索 URL，失败则中止

### 需求：等待用户登录后续跑

#### 场景：在首页/登录页轮询

- **当** 处于 `xhs` 的 `WAITING_LOGIN` 时
- **则** 轮询必须使用 `_xhs_login_ok_after_wait`（会话 Cookie + 无登录墙）
- **且** 用户尚在非搜索页完成登录时，不得要求已出现笔记条目

#### 场景：登录后验证搜索页

- **当** 轮询成功且已设置 `S.xhs_pending_keyword` 时
- **则** 系统必须打开该关键词的搜索 URL
- **且** 在结束等待前须再次执行 `xhs_search_page_needs_login`

#### 场景：续跑爬取

- **当** 等待返回 true 时
- **则** `crawl_xhs` 必须继续列表/详情抓取，无需新的爬取请求

### 需求：跳过向未登录浏览器注入过期配置 Cookie

#### 场景：浏览器未登录

- **当** 配置文件中存在小红书会话 Cookie 但浏览器 Profile 中不存在
- **且** `skip_inject_if_browser_logged_out` 为 true（默认）时
- **则** `apply_cookies_to_context` 必须跳过注入，避免误判「已登录」

### 需求：弹窗详情抓取时的鉴权失败

#### 场景：弹窗详情需要登录

- **当** `fetch_xhs_detail_via_modal` 经 `is_xhs_detail_auth_failure` 判定鉴权失败
- **则** 系统可以进入 `WAITING_LOGIN` 一次并重试同一笔记弹窗
- **且** 不得对每条笔记调用 `ensure_login_for_detail`（门禁仅在任务开始与搜索页）

### 需求：可观测的等待状态

与 `login-wait-resume` 规范一致：`/api/status`、界面横幅、Chrome 内日志引导。
