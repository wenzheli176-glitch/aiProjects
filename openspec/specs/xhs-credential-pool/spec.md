# xhs-credential-pool Specification

## Purpose
TBD - created by archiving change xhs-credential-pool-rotation. Update Purpose after archive.
## Requirements
### Requirement: xhs 账号池文件索引

系统 SHALL 在 `credentials/xhs/accounts.json` 维护小红书账号列表；每个账号 MUST 拥有独立 `cookies_file` 与 `user_data_dir`，且二者 1:1 永久绑定，禁止同一 profile 轮换绑定多个账号。

#### Scenario: 账号记录字段

- **WHEN** 系统读取 `accounts.json`
- **THEN** 每条账号 MUST 含 `id`、`label`、`cookies_file`、`user_data_dir`、`enabled`
- **AND** MAY 含 `cooldown_until`、`ban_note`、`last_used_at`

#### Scenario: Cookie 路径安全

- **WHEN** 创建或更新账号 cookies 路径
- **THEN** 路径 MUST 位于 `credentials/xhs/` 下
- **AND** MUST 拒绝 `..` 与项目根目录越界

### Requirement: 旧配置自动迁移为 acc-default

系统 SHALL 在 `accounts.json` 不存在且存在旧 `credentials/xhs_cookies.json` 时，自动迁移为默认账号 `acc-default`。

#### Scenario: 首次迁移

- **WHEN** `load_xhs_accounts()` 且 `accounts.json` 缺失且 `credentials/xhs_cookies.json` 存在
- **THEN** MUST 复制 cookie 至 `credentials/xhs/acc_default_cookies.json`
- **AND** MUST 复制或映射 profile 至 `chrome_profiles/xhs/acc_default/`
- **AND** MUST 写入 `accounts.json` 含单条 `acc-default` 且 `migrated_from=legacy`
- **AND** MUST NOT 删除旧文件

#### Scenario: 已存在 accounts.json

- **WHEN** `accounts.json` 已存在
- **THEN** MUST NOT 重复迁移

### Requirement: 每 keyword 主动 round-robin 轮换

系统 SHALL 对每个 xhs keyword 子任务开始前，从 enabled 且未冷却的账号池中按 round-robin 选取下一账号；MUST 为主动轮换，不得整 Run 固定单号（除非池中仅 1 个 enabled 账号）。

#### Scenario: 相邻 keyword 交替

- **WHEN** Run 含 4 个 keyword 且池中有 acc-A、acc-B 均 enabled
- **THEN** keyword 执行顺序 MUST 按 A→B→A→B 绑定账号（从 cursor 继续）

#### Scenario: 记录 account_id

- **WHEN** keyword 子任务开始执行
- **THEN** `monitor_keyword_runs.stats_json` MUST 写入 `account_id`
- **AND** 日志 MUST 含账号 label 或 id

#### Scenario: 最少账号警告

- **WHEN** enabled 账号数小于 `min_accounts`（默认 2）
- **THEN** 控制台 MUST 显示警告横幅
- **AND** Run MAY 仍以可用账号继续（降级单号或交替）

### Requirement: 轮换失败跳过该号

系统 SHALL 在单 keyword 绑定账号时，若 diagnose 或 rebind 失败，跳过该账号并尝试池中下一候选；仅当本 keyword 全部候选失败时才标记 keyword failed。

#### Scenario: 单号 diagnose 失败

- **WHEN** keyword K 轮询到 acc-A 且 diagnose 失败
- **THEN** MUST 尝试 acc-B（若 enabled）
- **AND** MUST NOT 将 acc-A 永久禁用（除非管理员设冷却）

#### Scenario: 全部候选失败

- **WHEN** keyword K 所有 enabled 账号均无法通过 diagnose
- **THEN** 该 keyword MUST 标记 `failed` 且 error 含 `no_available_account`
- **AND** 其他 keyword MAY 继续执行

### Requirement: 账号冷却与禁用

系统 SHALL 支持管理员将账号 `enabled=false` 或设置 `cooldown_until` ISO 时间；pick 时 MUST 跳过禁用与冷却中的账号。

#### Scenario: 禁言冷却

- **WHEN** 管理员设置 acc-B `cooldown_until` 为未来日期
- **THEN** round-robin MUST 跳过 acc-B 直至到期

### Requirement: 控制台登录会话获取 Cookie

系统 SHALL 提供 API，使管理员在独立 Chrome profile 中打开小红书登录页，登录完成后导出 Cookie 至该账号 `cookies_file` 并执行 diagnose。

#### Scenario: 启动登录会话

- **WHEN** 管理员 `POST /api/xhs/accounts/{id}/login/start` 且非 monitor busy
- **THEN** MUST 使用该账号 `user_data_dir` 启动 Chrome（独立 login CDP 端口）
- **AND** MUST 导航至 `config.auth.xhs.login_url`
- **AND** MUST 返回 `session_id` 与 `status=waiting`

#### Scenario: monitor busy 拒绝

- **WHEN** `is_monitor_busy()` 为 true 且请求 login/start
- **THEN** MUST 返回 409

#### Scenario: 轮询登录状态

- **WHEN** 管理员 `GET /api/xhs/accounts/{id}/login/status`
- **THEN** MUST 返回 `waiting` | `logged_in` | `timeout` | `error`
- **AND** `logged_in` 当浏览器上下文满足 `has_xhs_session`

#### Scenario: 完成并保存 Cookie

- **WHEN** 管理员 `POST /api/xhs/accounts/{id}/login/finish` 且已登录
- **THEN** MUST `export_cookies_from_context` 写入账号 cookies_file
- **AND** MUST 执行 diagnose 并更新诊断缓存
- **AND** MUST 关闭登录 Chrome

#### Scenario: 取消登录

- **WHEN** 管理员 `POST /api/xhs/accounts/{id}/login/cancel`
- **THEN** MUST 关闭登录 Chrome 且不覆盖已有 cookies_file

#### Scenario: 登录超时

- **WHEN** 自 start 起超过 `login_wait_timeout_sec` 仍未登录
- **THEN** status MUST 为 `timeout`
- **AND** 服务端 SHOULD 关闭登录 Chrome

### Requirement: 账号池 CRUD API

系统 SHALL 提供 `GET/POST/PATCH/DELETE /api/xhs/accounts` 管理账号元数据；粘贴 Cookie 上传 MAY 通过 `POST /api/xhs/accounts/{id}/cookies` 完成。

#### Scenario: 创建账号

- **WHEN** 管理员 POST 创建账号含 `label`
- **THEN** MUST 分配 `id`（如 `acc-02`）、cookies 路径与 profile 目录
- **AND** MUST 创建空 profile 目录

#### Scenario: 粘贴 Cookie 备选

- **WHEN** 管理员 POST cookies 文本至账号
- **THEN** MUST 解析并写入 cookies_file
- **AND** MAY 触发 diagnose

