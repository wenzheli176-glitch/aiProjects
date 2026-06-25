# business-system-integration Specification

## Purpose
TBD - created by archiving change crawl-scale-stage2. Update Purpose after archive.
## Requirements
### Requirement: 业务系统指定优先级

系统 SHALL 暴露 REST API 供业务系统覆盖合作方 `priority_tier` 与来源标记。

#### Scenario: 单个合作方指定

- **当** 业务系统 `PATCH /api/partners/:id/priority` 提交 `{ tier, reason }`
- **则** 必须更新 `priority_tier` 与 `priority_source=business`
- **且** 必须记录 `priority_updated_at` 与可选 reason 审计字段

#### Scenario: 批量指定

- **当** 业务系统 `POST /api/partners/bulk-priority` 提交 partner_id 列表与 tier
- **则** 必须批量更新
- **且** 返回成功与失败明细

#### Scenario: 查询当前定级

- **当** 调用 `GET /api/partners/priority`
- **则** 必须返回各 partner 的 tier、source、updated_at 及 auto 规则摘要（若 source=auto）

### Requirement: 单次 Run 业务规格

系统 SHALL 允许 MonitorTask 或 run 请求携带 `business_spec_json`，仅对当次 run 生效。

#### Scenario: 强制勘察合作方

- **当** business_spec 含 `force_investigation_partner_ids`
- **则** 这些合作方命中的 list raw 必须强制 `needs_investigation=true`

#### Scenario: 最低初筛相关度

- **当** business_spec 含 `min_triage_relevance`
- **则** 低于该档位的条目不得进入 investigation（P0 强制规则除外）

### Requirement: Intel 交付字段不变

业务系统加权仍基于 IntelRecord 的 `source`、`relevance`、`risk_types`；本变更 MUST NOT 在服务端计算最终风险分。

#### Scenario: API 向后兼容

- **当** 业务系统消费 `GET /api/intel/records`
- **则** 现有字段语义不变
- **且** 新增 optional 字段（如 `crawl_phase`、`triage_relevance`）不得破坏旧消费者

### Requirement: 任务 ignore_before 配置

系统 SHALL 在 MonitorTask 的 `business_spec_json` 支持 `ignore_before`（YYYY-MM-DD 字符串），用于分析阶段跳过过旧内容。

#### Scenario: 任务持久化

- **WHEN** 创建或更新 monitor_task 且提交 `business_spec.ignore_before`
- **THEN** MUST 写入 `business_spec_json`
- **且** 空字符串或 null MUST 表示不启用

#### Scenario: Run 读取

- **WHEN** MonitorRunner 执行分析阶段
- **THEN** MUST 读取任务级 `ignore_before`
- **且** `POST /api/monitor/run` 提交的 run 级 `business_spec` MAY 覆盖任务默认值（merge 后生效）

