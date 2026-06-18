## ADDED Requirements

### Requirement: Cookie 实例管理 Tab

统一 Web 控制台 SHALL 提供 Cookie / Worker 实例管理入口。

#### Scenario: 导航入口

- **当** 管理员登录
- **则** MUST 可进入 Cookie 实例管理页

#### Scenario: 失效横幅

- **当** 任一实例 diagnose 失败
- **则** MUST 显示全局或监测页横幅

### Requirement: 多实例登录等待展示

系统 SHALL 在多个 Worker 处于 login_gate 等待时聚合展示各实例状态。

#### Scenario: 多 Worker 横幅聚合

- **当** 多个 Worker 处于 login_gate 等待
- **则** `/api/status` 或监测页 MUST 聚合展示各 instance 的 site + elapsed（来自 run_state/worker_login_wait）

#### Scenario: 停止等待

- **当** 用户停止 Run
- **则** 所有 Worker login 等待 MUST 终止
