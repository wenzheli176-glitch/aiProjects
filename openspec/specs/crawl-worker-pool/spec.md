# crawl-worker-pool Specification

## Purpose
TBD - created by archiving change parallel-crawl-workers-selective-xhs. Update Purpose after archive.
## Requirements
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

### Requirement: 双形态 Crawl 工作队列

系统 SHALL 使用 `crawl_work_queue` 管理两类 routine 工作项及 investigation 工作项。

#### Scenario: xhs list_crawl 工作项

- **当** enqueue xhs routine
- **则** `phase` MUST 为 `list_crawl`
- **且** `payload_json` MUST 含 `keyword_batch`（cohort 合并结果）

#### Scenario: heimao legacy_crawl 工作项

- **当** enqueue heimao routine
- **则** `phase` MUST 为 `legacy_crawl`
- **且** `payload_json` MUST 含 `partner_id` 与搜索 `keyword`
- **且** MUST NOT 使用 keyword_batch 作为 heimao legacy 单元

#### Scenario: investigation 工作项按源路由

- **当** investigation 阶段开始
- **则** MUST enqueue `phase=investigation` 且 `source_id` 为 heimao 或 xhs
- **且** 仅对应 source 的 Worker MAY claim 该 item

#### Scenario: 原子认领

- **当** Worker 请求认领 pending 工作项
- **则** MUST 单条 UPDATE 保证同一 item 仅一 Worker 持有

#### Scenario: stale claim 回收

- **当** item 为 `claimed` 且 `now - claimed_at > claim_timeout_sec` 且无近期 heartbeat
- **则** Orchestrator MUST 重置为 `pending` 以便 reclaim

#### Scenario: 结果入库去重

- **当** 多工作项命中相同 URL
- **则** MUST 按 dedup_key UPSERT

### Requirement: Investigation 按源 Worker 执行

investigation_crawl MUST NOT 在 Orchestrator 主进程单 Chrome 内串行替代 Worker；MUST 通过 queue 回派至对应 source Worker。

#### Scenario: xhs investigation 在 xhs Worker

- **当** xhs investigation item 被 claim
- **则** MUST 在该 xhs 实例 Chrome 上执行弹窗详情
- **且** MUST 遵守 xhs-detail-modal 与弹窗配额

#### Scenario: heimao investigation 在 heimao Worker

- **当** heimao investigation item 被 claim（若存在）
- **则** MUST 在 heimao Worker Chrome 上执行 new_page 详情

### Requirement: Run 级状态与停止

系统 SHALL 以 active `monitor_runs` 状态替代全局 `S.running` 作为监测 Run 互斥依据。

#### Scenario: 禁止并发 monitor run

- **当** 已有 run 处于 running/crawling/analyzing
- **则** 新 `run_monitor_task` MUST 拒绝或排队（与现网一致：拒绝）

#### Scenario: 停止 Run

- **当** 用户 `POST /api/stop`
- **则** Orchestrator MUST 设置 `stop_requested`
- **且** MUST 通知所有 Worker 停止 claim/执行
- **且** Worker MUST 在合理超时内退出当前 crawl

#### Scenario: Worker 日志聚合

- **当** Run 进行中 Worker 产生日志
- **则** MUST 写入 run 可查询日志存储
- **且** Run 详情 MUST 可展示合并日志（含 instance 标识）

### Requirement: Run 前 Cookie 自动诊断

每个 Crawl Worker 在首次 claim 前 MUST diagnose 绑定实例 Cookie。

#### Scenario: 诊断通过

- **当** diagnose 成功
- **则** Worker 可 claim 并执行

#### Scenario: 单源诊断失败 partial

- **当** heimao 实例 diagnose 失败且 xhs 实例成功
- **则** heimao Worker MUST NOT claim
- **且** xhs Worker MUST 可继续
- **且** Run stats MUST 记录 `cookie_diagnose_failed`
- **且** Run MAY 以 done/partial 完成（非整 run failed）

#### Scenario: 全源诊断失败

- **当** 任务所需全部 source 实例 diagnose 均失败
- **则** Run MUST `status=failed` 且不进入 crawl

### Requirement: 手动调试爬取与 Worker 端口隔离

手动调试爬取 API MUST 与 Worker 占用端口隔离，争用时返回明确错误。

#### Scenario: 端口争用返回 409

- **当** Worker 已占用某 `cdp_port` 且 Run 进行中
- **则** 手动 `/api/crawl_*` 若争用同端口 MUST 返回 409
- **且** MUST 提示使用 Cookie 管理或等待 Run 结束

### Requirement: 登录 Chrome 与 Worker 端口隔离

进行 xhs 账号登录会话时，系统 MUST 使用 `login_cdp_port_base` 偏移端口，不得占用监测 Worker 正在使用的 CDP 端口。

#### Scenario: 登录与 Run 并行拒绝

- **WHEN** 监测 Run 进行中
- **THEN** login/start MUST 返回 409
- **AND** Worker Run MUST NOT 使用 login 专用端口

