## ADDED Requirements

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

## MODIFIED Requirements

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
