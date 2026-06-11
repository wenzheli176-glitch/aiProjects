# prompt-version-store Specification

## Purpose
TBD - created by archiving change intel-ux-normalize-prompts. Update Purpose after archive.
## Requirements
### Requirement: Prompt 模板 SQLite 存储

系统 SHALL 在 SQLite 维护 `prompt_templates` 表，存储多版本 System Prompt 模板；每条 MUST 含 `id`（slug）、`name`、`body`、`is_builtin`、`is_active`、`created_at`、`updated_at`。

#### Scenario: 内置默认模板

- **当** 数据库首次初始化或表为空
- **则** 必须插入一条 builtin 模板（内容与 `DEFAULT_SYSTEM_PROMPT` 等价）
- **且** 必须设为唯一 active 模板

#### Scenario: 活跃模板唯一

- **当** 管理员激活某模板
- **则** 必须将其他模板 `is_active=0`
- **且** 同时更新 `config.analysis.active_prompt_id`

### Requirement: Prompt 版本 API

系统 SHALL 提供 Prompt CRUD 与激活 API；写操作 MUST 要求管理员 Session。

#### Scenario: 列表与读取

- **当** 调用 `GET /api/analysis/prompts`
- **则** 必须返回全部模板摘要（id、name、is_active、is_builtin、updated_at）
- **且** `GET /api/analysis/prompts/{id}` 必须返回完整 body

#### Scenario: 新建与更新

- **当** 管理员 `POST /api/analysis/prompts` 或 `PUT .../{id}`
- **则** 必须持久化 name 与 body
- **且** body 必须支持 `{partner_name}` `{aliases}` 占位符

#### Scenario: 激活模板

- **当** 管理员 `POST /api/analysis/prompts/{id}/activate`
- **则** 该模板 MUST 成为分析管道使用的 System Prompt
- **且** 后续 AI 写入的 `intel_records.prompt_version` 必须为该模板 id

#### Scenario: 删除保护

- **当** 删除 builtin 模板
- **则** 必须返回 400/403
- **且** 不得删除当前 active 模板（须先切换）

### Requirement: 大模型 Tab Prompt 回显

系统 SHALL 在大模型 Tab 回显当前 active 模板全文；用户 MUST 可切换版本、编辑并另存为新版本。

#### Scenario: 加载回显

- **当** 用户打开大模型 Tab
- **则** 编辑器 MUST 显示 active 模板 body（非空）
- **且** 版本下拉 MUST 列出全部模板并标记当前项

#### Scenario: 运行时取 Prompt

- **当** AnalyzePipeline 构建 system message
- **则** 必须从 active 模板 body 读取（非空 config.system_prompt 遗留字段）
- **且** 必须对合作方别名做 format 替换

