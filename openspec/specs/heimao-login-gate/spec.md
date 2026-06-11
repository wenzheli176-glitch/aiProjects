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

#### 场景：无投诉链接且无 sid

- **当** 搜索 HTML 中投诉链接数为 0
- **且** 无可用 sid 时
- **则** `heimao_wait_if_search_empty` 必须进入 `WAITING_LOGIN`
- **且** 成功后须通过 `redo_search` 回调重新搜索

#### 场景：有 sid 但无链接

- **当** 存在 sid 但关键词无链接时
- **则** 系统必须记录警告并继续（可能确无结果）

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
