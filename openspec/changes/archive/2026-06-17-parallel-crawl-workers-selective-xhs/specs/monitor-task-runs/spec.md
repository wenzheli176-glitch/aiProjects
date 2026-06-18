## ADDED Requirements

### Requirement: Worker 与队列 Run 指标

系统 SHALL 在 monitor run stats 中记录 Worker、配额与诊断相关指标。

#### Scenario: 并行 crawl timing

- **当** heimao 与 xhs Worker 并行
- **则** stats MUST 含 `timing_by_source`
- **且** MAY 含 `worker_instances`（source、instance_id、status、diagnose_ok）

#### Scenario: investigation 配额 stats

- **当** xhs investigation 执行
- **则** MUST 含 `investigation_modal_done` 与 `investigation_skipped_quota`（若有）

#### Scenario: Cookie 诊断与 partial

- **当** 部分实例 diagnose 失败
- **则** MUST 含 `cookie_diagnose_failed` 计数
- **且** MAY 含 `sources_degraded` 或 run `status` 表达 partial success

#### Scenario: Run 详情展示

- **当** 用户查看 Run 详情
- **则** MUST 展示失败 instance、skip 配额、合并 Worker 日志入口

### Requirement: Run stats 字段标签

Run 历史与详情 UI 展示 stats 时 MUST 使用 `field_labels` 中文标签；新增 stats 键 MUST 同步注册。

#### Scenario: 新增字段标签

- **当** stats 含 `investigation_modal_done`、`investigation_skipped_quota`、`cookie_diagnose_failed`
- **则** field_labels MUST 提供中文名
- **且** Run 历史表头 MUST 使用 label
