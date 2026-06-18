## ADDED Requirements

### Requirement: Cookie 实例写操作须管理员

Cookie 文件上传与 instance 配置写 API MUST 受 `@require_admin` 保护。

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
