## ADDED Requirements

### Requirement: 合作方优先级档位

系统 SHALL 为每个 Partner 维护 `priority_tier`：P0（重点）、P1（常规）、P2（低频）。

#### Scenario: 默认值

- **当** 新建合作方且未指定 tier
- **则** 默认 `priority_tier=P1`
- **且** `priority_source=auto`

#### Scenario: 自动升降档

- **当** `priority_source=auto` 且系统执行定级刷新
- **则** 近 7 天 high relevance + 严重 risk_types 达阈值 MUST 升为 P0
- **且** 30 天无 medium+ 信号 MAY 降为 P2

#### Scenario: 业务指定冻结

- **当** `priority_source=business`
- **则** 自动规则不得降低或覆盖 tier
- **且** 仅业务 API 或管理员可修改 tier

### Requirement: 调度配额

系统 SHALL 在 `crawl_mode=list_first` 的 run 中，按 P0/P1/P2 配额分配 keyword_batch 执行顺序与时间片。

#### Scenario: 配额配置

- **当** 读取 `config.monitor.priority_quota`
- **则** P0/P1/P2 配额之和必须为 1.0（或归一化）
- **且** P0 batch 必须先于 P2 batch 执行

#### Scenario: Run 进度可观测

- **当** 调度执行中
- **则** progress JSON 必须包含当前 tier 与 batch 索引
