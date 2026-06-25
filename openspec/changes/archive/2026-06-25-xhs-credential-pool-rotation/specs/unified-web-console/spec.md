## ADDED Requirements

### Requirement: 数据源 xhs 登录账号池 UI

系统 SHALL 在「数据源」Tab · 小红书配置区提供「登录账号池」管理：列表、添加账号、登录获取 Cookie、粘贴 Cookie、诊断、禁用与冷却设置。

#### Scenario: 账号列表展示

- **WHEN** 管理员打开数据源 · 小红书
- **THEN** MUST 请求 `GET /api/xhs/accounts` 并展示 label、enabled、cooldown_until、cookie_count、最近 diagnose

#### Scenario: 添加账号并登录

- **WHEN** 管理员点击「添加账号」并选择「打开登录页」
- **THEN** MUST 调用 login/start 并展示等待登录说明
- **AND** MUST 轮询 login/status 直至 logged_in 或 timeout
- **AND** logged_in 后 MUST 提供「完成并保存」调用 login/finish

#### Scenario: 启用账号不足警告

- **WHEN** enabled 账号数小于 2
- **THEN** MUST 在账号池区域显示黄色警告（建议添加账号以启用轮换）

#### Scenario: 设置冷却

- **WHEN** 管理员为账号设置禁言冷却日期
- **THEN** MUST PATCH 账号 `cooldown_until` 并刷新列表

#### Scenario: 操作员只读

- **WHEN** 非管理员访问数据源 xhs 账号池
- **THEN** 写操作按钮 MUST 隐藏或禁用（与 `admin-only-save` 一致）

## MODIFIED Requirements

### Requirement: 数据源 Tab 切换

系统 SHALL 在「数据源」Tab 以 Tab 切换各 source 配置（如 heimao / xhs），而非纵向堆叠全部源 card。小红书 Tab MUST 在 crawl 配置下方包含登录账号池区块。

#### Scenario: 切换源

- **WHEN** 用户点击 heimao 或 xhs 子 Tab
- **THEN** MUST 仅展示该源配置表单
- **AND** xhs 子 Tab MUST 展示账号池表格
