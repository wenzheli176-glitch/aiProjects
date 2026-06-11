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

