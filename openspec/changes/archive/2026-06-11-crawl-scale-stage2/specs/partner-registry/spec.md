## ADDED Requirements

### Requirement: 行业 cohort

系统 SHALL 为 Partner 支持 `industry_cohort` 字段，用于共享爬取的关键词合并与调度分组。

#### Scenario: 创建合作方含 cohort

- **当** 用户提交 industry_cohort（如「新能源整车」）
- **则** 必须持久化到 partners 表
- **且** shared-crawl-pool 必须按 cohort 合并 keyword_batch

#### Scenario: 未设 cohort

- **当** industry_cohort 为空
- **则** 该 partner 单独成组（cohort  fallback 为 `partner:{id}`）

### Requirement: 优先级字段

系统 SHALL 在 partners 表存储 priority_tier、priority_source、priority_updated_at。

#### Scenario: UI 与 API 同步

- **当** 管理员在 UI 修改 tier
- **则** 必须写入 priority_source=manual
- **且** 与业务 API 写入可互相覆盖（后者更新 updated_at）

## MODIFIED Requirements

### Requirement: 合作方名单 CRUD

系统 SHALL 在 SQLite 中持久化合作方（Partner），并支持创建、读取、更新、删除与启用/停用。

#### Scenario: 创建合作方含别名

- **当** 用户通过 UI 或 `POST /api/partners` 提交主名称、别名列表、可选排除词与监测词
- **则** 系统必须写入 `partners` 表并返回唯一 `partner_id`
- **且** 别名必须可用于后续 PartnerMatcher 匹配
- **且** SHOULD 支持可选 industry_cohort 与 priority_tier

#### Scenario: 停用合作方不参与监测

- **当** 合作方 `enabled=false`
- **则** 新建 MonitorTask 时不得默认包含该合作方
- **且** 既有 intel_records 仍可查询
