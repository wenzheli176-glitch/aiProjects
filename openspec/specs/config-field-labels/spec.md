# config-field-labels Specification

## Purpose
TBD - created by archiving change intel-ux-normalize-prompts. Update Purpose after archive.
## Requirements
### Requirement: 全站字段标签注册表

系统 SHALL 维护集中式字段元数据（`label`、`group`、`type`、`help`），Web 控制台所有配置表单 MUST 以「中文（english_key）」展示字段名；未知键 MUST fallback 为 english_key 本身。

#### Scenario: 数据源 Tab 标签

- **当** 用户打开数据源 Tab 的 CrawlProfile 或 Normalize 表单
- **则** 每个字段 label 必须为「中文（键名）」格式
- **且** 不得仅显示 snake_case 英文键

#### Scenario: 系统设置与大模型 Tab

- **当** 用户打开系统设置或大模型 Tab
- **则** 所有带 `data-field-key` 或 registry 注册的输入项 MUST 使用同一 registry 标签
- **且** 标签文案必须与数据源 Tab 同键一致

#### Scenario: 导出与 API 文档

- **当** 文档或导出列头引用配置/情报字段
- **则** 中文列名 MUST 与 registry 中 label 一致（不含括号内键名时可取 label 中文部分）

### Requirement: 字段元数据可扩展

系统 SHALL 允许按模块扩展 registry（crawl、normalize、analysis、auth、server 等 group），新增 config 键时 MUST 同步注册 label。

#### Scenario: 新增 normalize 键

- **当** 为 heimao 新增 normalize 配置键
- **则** 必须在 registry 中注册后才可在 UI 暴露
- **且** PATCH profile API 白名单与 registry 键集合一致

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

