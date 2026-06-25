# cookie-instance-admin Specification

## Purpose
TBD - created by archiving change parallel-crawl-workers-selective-xhs. Update Purpose after archive.
## Requirements
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

### Requirement: Cookie 实例管理页

系统 SHALL 提供 Web 管理界面，按 Worker 实例展示路径、诊断状态，并支持上传/更新 Cookie。

#### Scenario: 展示实例状态

- **当** 管理员打开 Cookie 管理页
- **则** MUST 列出 source + instance_id + cdp_port + cookies_file + 最近 diagnose 结果

#### Scenario: Cookie 失效提示

- **当** 任一实例 diagnose 失败
- **则** 控制台 MUST 显示横幅引导更新

#### Scenario: 上传 Cookie

- **当** 管理员上传或粘贴 Cookie 至指定实例
- **则** MUST 写入配置的 cookies_file
- **且** 下次 Run 前 diagnose 使用新文件

### Requirement: Run 前 Cookie 诊断门禁

每个 Crawl Worker 在首次 claim 前 MUST 执行 Cookie diagnose。

#### Scenario: 诊断通过

- **当** cookies 有效且 diagnose 成功
- **则** 该实例 MAY claim

#### Scenario: 诊断失败阻断该实例

- **当** 某实例 diagnose 失败
- **则** 该实例 MUST NOT claim
- **且** MUST 记录 `cookie_diagnose_failed`（含 source + instance_id）

#### Scenario: Chrome 由 Orchestrator 启动

- **当** Worker 即将启动
- **则** Orchestrator MUST 按 instance 配置启动独立 Chrome（cdp_port + user_data_dir）
- **且** Worker MUST 仅 connect CDP，不得与手动 crawl 默认端口冲突（见 crawl-worker-pool）

### Requirement: xhs 多账号管理入口提示

Cookie 实例管理页对 xhs MUST 提示主入口为「数据源 · 小红书 · 登录账号池」。

#### Scenario: xhs 实例行提示

- **WHEN** 管理员打开 Cookie 实例 Tab 且存在 xhs 实例
- **THEN** MUST 显示引导文案指向数据源 Tab 管理多账号

