## ADDED Requirements

### Requirement: heimao routine 空结果直接跳过

heimao CrawlAdapter 在 legacy routine crawl MUST 在关键词无投诉链接时立即进入下一项，不阻塞、不重试。

#### Scenario: 空结果不阻塞队列

- **WHEN** `crawl_heimao` 因空搜索返回空列表
- **且** 分类非 `auth_required`
- **THEN** Worker MUST NOT 进入 `login_wait`
- **且** MUST 立即 claim/执行下一 work item 或下一关键词

#### Scenario: 日志可观测

- **WHEN** 关键词因空结果被跳过
- **THEN** 日志 MUST 包含 `[heimao] 无结果，跳过` 与 keyword
- **且** Run 详情 MUST 可通过 RunMetrics 查看 `heimao_skipped_empty`

## MODIFIED Requirements

### Requirement: heimao 分页早停与空页重试

`config.heimao.early_stop.empty_page_retry` 默认值 MUST 为 `0`。第 1 页无新增投诉链接时，系统 MUST 立即停止当前关键词（`reason=empty_page`），**不得**执行 `_redo_heimao_search` 或额外重试。

#### Scenario: 默认不重试空第 1 页

- **WHEN** `protect_first_page` 启用且第 1 页 `new_count=0`
- **且** `empty_page_retry=0`（默认）
- **THEN** 系统 MUST 立即 early_stop
- **且** MUST NOT 因缺少 sid 进入 `WAITING_LOGIN`
- **且** MUST NOT 重搜同一关键词

#### Scenario: 显式配置 empty_page_retry 大于 0

- **WHEN** 管理员显式设置 `heimao.early_stop.empty_page_retry>0`
- **THEN** 系统 MAY 按配置重试（不推荐；与「空搜不重试」产品默认相悖）
