## ADDED Requirements

### Requirement: Run 执行记录字段标签

系统 SHALL 在字段注册表中为 `monitor_task_runs` 相关键提供 `monitor_run` 分组的中文 label 与 help，供 Run 详情 UI 与文档引用。

#### Scenario: Run 顶层字段

- **当** UI 渲染 Run 详情中的 trigger、analyze_mode、status、crawl_duration_ms、analyze_duration_ms、started_at、finished_at、error_message
- **则** 必须使用 registry 中对应中文 label（格式「中文（english_key）」或 label + help tooltip）
- **且** 未知键 fallback 为 english_key

#### Scenario: stats 与分源子键

- **当** UI 渲染 `stats` 内 raw_new、raw_updated、raw_unchanged、intel_written、intel_replaced、intel_skipped
- **或** 渲染 timing/token 表头 crawl_ms、analyze_ms、prompt_tokens、completion_tokens、total_tokens
- **则** 必须在 registry 注册上述键的中文说明
- **且** help 文案须简要说明计数含义（如 raw_new=本次新增 raw 条数）
