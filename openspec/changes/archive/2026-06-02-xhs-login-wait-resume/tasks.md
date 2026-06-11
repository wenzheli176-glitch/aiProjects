## 1. 配置与认证检测

- [x] 1.1 新增 `auth.xhs` 字段：`wait_timeout_sec`、`poll_interval_sec`、`required_cookie_names`（`web_session`、`webId`）、`auto_export_after_login`、`detail_probe_min_content_len`
- [x] 1.1b 在 `auth.heimao` 下增加相同等待/续跑字段（共用 `login_gate.py`）
- [x] 1.2 在 `auth_utils.py` 实现 `has_xhs_session(cookies)` 并加强 `site=xhs` 的 `check_login_on_page`
- [x] 1.3 新增 `is_xhs_detail_auth_failure` / `is_heimao_detail_auth_failure` 用于详情抓取后失败检测
- [x] 1.4 扩展 `diagnose_login`，为 xhs 增加 web_session / webId 提示

## 2. 爬取状态机

- [x] 2.1 扩展 `S`：`phase`（`running` | `waiting_login`）及 `login_wait` 元数据（site、started_at、timeout）
- [x] 2.2 实现 `wait_for_site_login(ctx, page, site)` 轮询循环，尊重 `S.running` 并支持停止
- [x] 2.3 接入 `crawl_xhs` 与 `crawl_heimao`：`fetch_detail` 时在搜索/详情前门禁；否则跳过强制等待
- [x] 2.4 等待成功后按配置调用 `export_cookies_from_context` + `save_site_cookies`

## 3. API 与状态

- [x] 3.1 扩展 `/api/status`，为 UI 返回 `phase` 与 `login_wait` 对象
- [x] 3.2 确保爬取处于 `WAITING_LOGIN` 时 `api_auth/open_login` 与 `api_auth/diagnose` 可用（无死锁；`S.running` 时跳过 `close_cdp`）

## 4. Web 界面

- [x] 4.1 当 `phase=waiting_login` 时在状态栏显示等待登录横幅
- [x] 4.2 显示已用时间/超时；等待期间保留「打开登录页」「登录诊断」
- [x] 4.3 在 UI 提示中说明：仅列表模式不要求登录

## 5. 文档与验证

- [x] 5.1 更新 `docs/如何获取登录凭证.md`，补充等待续跑流程（黑猫 + 小红书）
- [x] 5.2 手动测试：`fetch_detail=true` + 未登录 → 等待 → 扫码 → 自动续跑详情
- [x] 5.3 手动测试：`fetch_detail=false` + 未登录 → 列表仍可抓取
