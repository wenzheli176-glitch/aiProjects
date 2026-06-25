## MODIFIED Requirements

### Requirement: 同机 Crawl Worker 进程池

系统 SHALL 支持同机多进程 Crawl Worker；每个 Worker 绑定单一 `source_id`、独立 CDP 端口、user_data_dir 与 cookies_file。

#### Scenario: heimao 与 xhs Worker 并行 routine crawl

- **当** 监测 Run 进入 routine crawl 且 task.sources 含 heimao 与 xhs
- **则** Orchestrator MUST 同时启动 heimao Worker 与 xhs Worker（各至少 1 实例）
- **且** heimao `legacy_crawl` 与 xhs `list_crawl` wall-clock 并行
- **且** 汇合 barrier 后 MUST 才进入 list_triage

#### Scenario: 同源单实例串行

- **当** 同一 xhs Worker 实例处理 investigation 弹窗
- **则** MUST 顺序执行，不得在同一 Chrome 内并行多个弹窗操作

#### Scenario: Worker 实例上限

- **当** 配置的 instances 超过 `max_instances` 或 `max_workers_total`
- **则** 启动时 MUST 拒绝或截断至上限

#### Scenario: xhs 每 keyword 换 profile

- **WHEN** xhs Worker 完成上一 keyword 并开始下一 keyword
- **THEN** Orchestrator MUST shutdown 当前 xhs Chrome（若 user_data_dir 变化）
- **AND** MUST 按新账号 user_data_dir 重启 Chrome 后 claim 下一工作项
- **AND** MUST 在 rebind 后执行 Cookie diagnose

## ADDED Requirements

### Requirement: 登录 Chrome 与 Worker 端口隔离

进行 xhs 账号登录会话时，系统 MUST 使用 `login_cdp_port_base` 偏移端口，不得占用监测 Worker 正在使用的 CDP 端口。

#### Scenario: 登录与 Run 并行拒绝

- **WHEN** 监测 Run 进行中
- **THEN** login/start MUST 返回 409
- **AND** Worker Run MUST NOT 使用 login 专用端口
