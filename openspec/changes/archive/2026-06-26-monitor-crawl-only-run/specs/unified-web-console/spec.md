## ADDED Requirements

### Requirement: 仅爬取执行选项

监测任务 UI MUST 提供「仅爬取（稍后 AI 分析）」选项；保存至任务配置并在执行时传给 `POST /api/monitor/run`。

#### Scenario: 任务 Modal 配置 crawl_only

- **WHEN** 用户在创建/编辑监测任务 Modal 勾选「仅爬取」
- **THEN** MUST 将 `crawl_only=true` 持久化至任务记录
- **AND** 加载任务编辑 MUST 回显该选项

#### Scenario: 执行任务传递 crawl_only

- **WHEN** 用户点击任务「执行」且任务或执行确认中 crawl_only 为 true
- **THEN** MUST `POST /api/monitor/run` body 含 `crawl_only: true`

#### Scenario: Run 历史待分析标识

- **WHEN** Run 详情或执行历史中 `run.crawl_only=true` 且 `stats.analyze_deferred=true`
- **THEN** MUST 显示「待分析」状态标签
- **AND** MUST 提供「增量 AI」快捷操作（调用现有 reanalyze API）

#### Scenario: 执行按钮 tooltip

- **WHEN** 任务 crawl_only 为 true
- **THEN** 执行按钮 title/tooltip MUST 说明「仅爬取，不执行 AI 分析」
