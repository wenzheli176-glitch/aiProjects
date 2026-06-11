# login-wait-resume（共享）

`login_gate.py` 为黑猫与小红书共用的登录门禁与等待续跑模块。

### 需求：共享的等待与续跑状态

爬取运行时（`crawler_web.S`）必须向 Web 界面与状态 API 暴露登录等待状态。

#### 场景：进入等待登录

- **当** `wait_for_site_login` 针对站点 `heimao` 或 `xhs` 启动时
- **则** `S.phase` 必须为 `waiting_login`
- **且** `S.login_wait` 必须包含 site、started_at、timeout_sec、message、elapsed_sec

#### 场景：等待成功后续跑

- **当** 登录轮询成功时
- **则** 必须清除 `S.phase` 与 `S.login_wait`
- **且** 爬取必须在同一线程内继续，无需新的 API 请求

#### 场景：超时

- **当** 配置的 `wait_timeout_sec` 届满仍未成功时
- **则** `wait_for_site_login` 必须返回 false
- **且** 爬取必须记录明确错误并停止

### 需求：等待期间保持 CDP 会话

#### 场景：爬取过程中的认证 API

- **当** `S.running` 为 true 且爬取处于 `WAITING_LOGIN` 时
- **则** `close_cdp()` 不得断开 Playwright（除非显式关闭浏览器）
- **且** `/api/auth/open_login` 与 `/api/auth/diagnose` 必须仍可使用

### 需求：等待结束后可选导出 Cookie

#### 场景：已配置自动导出

- **当** 登录等待成功结束
- **且** `auth.<site>.auto_export_after_login` 为 true 时
- **则** 系统必须通过 `maybe_export_after_login` 将浏览器 Cookie 导出到配置的凭证文件

### 需求：勾选详情时门禁登录；仅列表时不强制

#### 场景：爬取详情

- **当** `fetch_detail=true` 或 `auth.<site>.require_login=true` 时
- **则** `ensure_login_for_detail` 必须阻塞，直至登录成功或等待超时

#### 场景：仅抓列表

- **当** `fetch_detail=false` 且 `require_login=false` 时
- **则** 系统可按配置注入 Cookie，但不得在任务开始时进入强制登录等待

### 需求：状态 API 暴露等待状态

#### 场景：等待期间轮询状态

- **当** 爬取处于 `WAITING_LOGIN` 时
- **则** `/api/status` 必须返回 `phase=waiting_login` 及包含站点、已用时间、超时的 `login_wait` 对象
