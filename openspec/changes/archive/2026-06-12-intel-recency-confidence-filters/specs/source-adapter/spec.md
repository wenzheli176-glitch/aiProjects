## MODIFIED Requirements

### Requirement: NormalizeAdapter 契约

每个数据源 MUST 实现 NormalizeAdapter，将源特有 RawRecord 映射为 NormalizedRecord 最小公约字段。

#### Scenario: NormalizedRecord 必填字段

- **当** NormalizeAdapter 输出记录
- **则** 每条必须包含 `source`、`external_id`、`url`、`title`、`body`
- **且** `published_at` 必须为日期级 ISO 8601（`YYYY-MM-DD`）或空字符串
- **且** 解析 MUST 通过共用 `parse_published_date`，以 raw `captured_at`（或 raw `created_at`）为相对时间锚点
- **且** 扩展字段必须放入 `extra` JSON

#### Scenario: 详情时间覆盖列表

- **当** raw payload 同时含列表级 `time` 与详情级 `time`（detail-phase）
- **则** NormalizeAdapter MUST 优先采用详情时间解析 `published_at`

#### Scenario: heimao 归一化

- **当** 源为 heimao
- **则** NormalizeAdapter 必须基于 `reports.structure_heimao_record` 映射
- **且** `external_id` 必须为投诉编号

#### Scenario: xhs 归一化

- **当** 源为 xhs
- **则** NormalizeAdapter 必须基于 `structure_xhs_record` 映射
- **且** `external_id` 必须为笔记 id 或 url 稳定片段

## ADDED Requirements

### Requirement: 发布时间日期解析

系统 SHALL 提供 `parse_published_date(text, anchor_date)`，将黑猫/小红书常见时间文本规范为 `YYYY-MM-DD`。

#### Scenario: 绝对日期

- **当** 输入含 `YYYY-MM-DD` 或可解析的日期文本
- **则** 必须返回该日期字符串

#### Scenario: 相对时间

- **当** 输入为「N天前」「昨天」「今天」等相对表述
- **则** 必须基于 `anchor_date` 反推并返回 `YYYY-MM-DD`

#### Scenario: 无法解析

- **当** 输入为空或无法识别
- **则** 必须返回空字符串
- **且** 不得伪造日期
