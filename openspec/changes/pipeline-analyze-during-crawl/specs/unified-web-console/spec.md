## ADDED Requirements

### Requirement: crawling 态增量 AI 入口

系统 SHALL 在任务 `status=crawling` 且存在 detail-ready 未分析 raw 时，启用「增量 AI」操作。

#### Scenario: 按钮可用

- **WHEN** 任务正在爬取且 `can_reanalyze=true`（crawling + incremental 允许）
- **THEN** 任务详情与操作区 MUST 显示可点击的「增量 AI」
- **AND** 点击 MUST 调用 `POST /api/monitor/reanalyze`（incremental）

#### Scenario: 全量 AI 禁用

- **WHEN** task `status=crawling`
- **THEN** 「全量重分析」按钮 MUST disabled 并 tooltip 说明需等 crawl 结束

### Requirement: Analyze Drain 双进度展示

系统 SHALL 在任务详情展示 crawl 与 analyze drain 并行进度。

#### Scenario: 源级进度行

- **WHEN** Run 进行中且 `progress.analyze_drain` 存在
- **THEN** 任务列表/详情 MUST 显示「勘察 x/y · 分析 a/b（detail 待分析）」或等价文案

#### Scenario: 子任务区

- **WHEN** investigation 批进行中
- **THEN** 勘察批次进度与 analyze drain 计数 MUST 可同时刷新（轮询 `/api/monitor/tasks/{id}`）
