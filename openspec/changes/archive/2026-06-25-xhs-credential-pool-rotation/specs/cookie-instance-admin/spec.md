## MODIFIED Requirements

### Requirement: Cookie 实例与 config.auth 统一

系统 SHALL 以 `monitor.workers.{source}.instances[].cookies_file` 为 Worker Cookie 权威路径；`config.auth.{site}.cookies_file` MUST 默认与对应 source 的首个 instance 对齐（启动 merge 或文档化同步）。**对 xhs**，运行时 keyword 执行前 MUST 从 `xhs-credential-pool` 选取账号并临时绑定该账号的 `cookies_file` 与 `user_data_dir`；config 中 instance 路径为 fallback / `acc-default` 对齐目标。

#### Scenario: 单轨 cookies_file

- **当** 管理员在 Cookie 管理页更新 heimao 实例 Cookie
- **则** MUST 写入 instance.cookies_file
- **且** Worker 与 diagnose MUST 读取同一路径

#### Scenario: xhs 运行时 rebind

- **当** xhs Worker 即将执行某 keyword 子任务
- **则** MUST 从账号池 pick 账号并绑定其 cookies_file 与 user_data_dir
- **且** MUST NOT 在同一 user_data_dir 上切换不同账号 Cookie

#### Scenario: 缺失 cookies_file

- **当** instance 或账号 cookies_file 不存在
- **则** diagnose MUST 失败；该实例 MUST NOT claim（xhs 轮换时跳过该账号）

## ADDED Requirements

### Requirement: xhs 多账号管理入口提示

Cookie 实例管理页对 xhs MUST 提示主入口为「数据源 · 小红书 · 登录账号池」。

#### Scenario: xhs 实例行提示

- **WHEN** 管理员打开 Cookie 实例 Tab 且存在 xhs 实例
- **THEN** MUST 显示引导文案指向数据源 Tab 管理多账号
