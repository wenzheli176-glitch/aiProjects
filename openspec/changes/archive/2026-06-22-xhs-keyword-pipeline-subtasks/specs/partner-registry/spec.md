## ADDED Requirements

### Requirement: 合作方数据源超时

系统 SHALL 在 `partners.source_timeouts_json` 持久化 per-source 最大爬取超时（秒），键为 source_id（如 `xhs`、`heimao`）；API 读写字段名为 `source_timeouts`。

#### Scenario: 创建合作方带超时

- **当** `POST /api/partners` 提交 `source_timeouts: {"xhs": 7200}`
- **则** 该合作方 xhs keyword 子任务 MUST 使用 7200 秒超时（不低于全局默认）

#### Scenario: 未配置时使用默认

- **当** 合作方未配置某 source 超时
- **则** MUST 使用 `xhs.keyword_timeout_sec` 或 `heimao.partner_timeout_sec` 全局默认

#### Scenario: 多合作方共享 keyword

- **当** 同一 keyword 匹配多个合作方且超时不同
- **则** MUST 取各合作方该源超时与全局默认的 **最大值**
