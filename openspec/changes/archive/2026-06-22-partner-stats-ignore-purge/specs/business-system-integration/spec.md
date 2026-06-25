## ADDED Requirements

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
