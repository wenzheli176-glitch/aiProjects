# admin-console-auth Specification

## Purpose
TBD - created by archiving change unified-console-source-admin. Update Purpose after archive.
## Requirements
### Requirement: 管理员 Session 登录

系统 SHALL 提供基于 Session Cookie 的管理员登录；口令从 `config.admin.password_env` 指定环境变量或 `config.admin.password_hash` 校验。

#### Scenario: 登录成功

- **当** 客户端 `POST /api/admin/login` 提交正确口令
- **则** 必须 Set-Cookie 签发管理员 Session
- **且** `GET /api/admin/session` 必须返回 `role=admin` 与 `logged_in=true`

#### Scenario: 登录失败

- **当** 口令错误
- **则** 必须返回 401 且不签发 Session

#### Scenario: 登出

- **当** 客户端 `POST /api/admin/logout`
- **则** 必须清除 Session Cookie
- **且** 后续写 API 必须视为操作员

### Requirement: 写操作须管理员权限

系统 SHALL 对配置与名单类写 API 施加 `@require_admin`；未登录管理员 MUST 收到 403。

#### Scenario: 操作员被拒绝写配置

- **当** 无管理员 Session 且 `POST /api/config` 或 `PATCH /api/sources/heimao/profile`
- **则** 必须返回 403 与明确错误信息

#### Scenario: 操作员可运行监测

- **当** 无管理员 Session 且 `POST /api/monitor/run` 或 `POST /api/stop`
- **则** 必须允许（内网操作员角色）

#### Scenario: 管理员可写合作方与任务

- **当** 有效管理员 Session 且 `POST/PUT/DELETE /api/partners/*` 或 monitor tasks CRUD
- **则** 必须允许

#### Scenario: 操作员不可改合作方名单

- **当** 无管理员 Session 且 `POST /api/partners`
- **则** 必须返回 403

#### Scenario: 开发模式关闭鉴权

- **当** `config.admin.enabled=false`
- **则** 写 API 可跳过 Session 检查
- **且** 文档必须声明仅限本地开发

### Requirement: 敏感配置脱敏

系统 SHALL 在 GET 配置时对 `analysis.api_key` 等敏感字段 mask；管理员保存时空值或 mask 不得覆盖已有密钥（沿用现有 merge 逻辑）。

#### Scenario: API Key mask

- **当** `GET /api/analysis/config` 或整包 config
- **则** 已配置 api_key 必须显示为 `***已配置***`

#### Scenario: Cookie 写入仅管理员

- **当** `POST /api/auth/save` 写入 Cookie 到 config
- **则** 必须要求管理员 Session

### Requirement: Cookie 实例写操作须管理员

Cookie 文件上传与 instance 配置写 API MUST 受 `@require_admin` 保护。xhs 账号池 API 与 Cookie 实例 upload 同等权限级别。

#### Scenario: 操作员不可上传 Cookie

- **当** 无管理员 Session 且 `POST /api/cookie-instances/.../upload`
- **则** MUST 返回 403

#### Scenario: 路径安全

- **当** 上传或 PATCH 指定 cookies_file
- **则** MUST 拒绝路径穿越（`..`、绝对路径越界）
- **且** MUST 限制在配置的 credentials/ 或项目允许目录内

#### Scenario: 操作员仍可运行监测

- **当** 无管理员 Session 且 `POST /api/monitor/run`
- **则** MUST 允许（与现有操作员角色一致）

### Requirement: 数据清理 API 须管理员

系统 SHALL 对 `POST /api/admin/purge/raw` 与 `POST /api/admin/purge/intel` 施加 `@require_admin`。

#### Scenario: 操作员被拒绝

- **WHEN** `config.admin.enabled=true` 且无管理员 Session
- **THEN** purge 请求 MUST 返回 403

#### Scenario: 管理员可清理

- **WHEN** 有效管理员 Session 且请求含合法 `task_id`
- **THEN** MUST 允许 dry_run 与删除

### Requirement: xhs 账号池写操作须管理员

账号池 CRUD、Cookie 粘贴、登录会话 start/finish/cancel MUST 受 `@require_admin` 保护；路径 MUST 限制在 `credentials/xhs/` 与 `chrome_profiles/xhs/`。

#### Scenario: 操作员不可启动登录会话

- **WHEN** 无管理员 Session 且 `POST /api/xhs/accounts/{id}/login/start`
- **THEN** MUST 返回 403

#### Scenario: 操作员不可创建账号

- **WHEN** 无管理员 Session 且 `POST /api/xhs/accounts`
- **THEN** MUST 返回 403

#### Scenario: 账号路径安全

- **WHEN** 创建账号或写入 cookies
- **THEN** MUST 拒绝路径穿越
- **AND** cookies_file MUST 位于 `credentials/xhs/`
- **AND** user_data_dir MUST 位于 `chrome_profiles/xhs/`

