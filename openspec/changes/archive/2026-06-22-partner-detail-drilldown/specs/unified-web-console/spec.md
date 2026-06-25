## ADDED Requirements

### Requirement: 合作方详情页与子 Tab

系统 SHALL 在「合作方」Tab 提供列表视图与合作方详情视图；详情 MUST 含 **情报**、**源数据** 两个子 Tab，对应列表行的两个查看按钮。

#### Scenario: URL 深链

- **WHEN** URL 含 `?tab=partners&partner_id={id}&partner_tab=intel|raw`
- **THEN** MUST 展示合作方详情视图并激活对应子 Tab
- **且** `partner_tab=raw` 时若含 `task_id` MUST 使用该任务加载源数据列表

#### Scenario: 返回列表

- **WHEN** 用户在合作方详情点击「返回」
- **THEN** MUST 清除 `partner_id`、`partner_tab`、`task_id` query
- **且** 展示合作方列表视图

#### Scenario: 查看情报按钮

- **WHEN** 用户点击某行的「查看情报」
- **THEN** MUST 打开详情且子 Tab 为情报
- **且** 情报列表 MUST 使用 `partner_id` 筛选且默认 `relevance_min=medium`

#### Scenario: 查看源数据按钮

- **WHEN** 用户点击某行的「查看源数据」
- **THEN** MUST 打开详情且子 Tab 为源数据
- **且** MUST 带 `task_id`（默认来自 context API 的 `default_task_id`）
- **且** MUST 提供任务下拉以切换关联任务并刷新列表

#### Scenario: 子 Tab 切换

- **WHEN** 用户在详情内切换情报/源数据子 Tab
- **THEN** MUST 更新 `partner_tab` query
- **且** 切换到源数据时 MUST 保留或补全 `task_id`

## MODIFIED Requirements

### Requirement: 统一 Web 入口

系统 SHALL 提供单一 Web 壳作为默认入口，整合原爬虫控制台与风险看板功能；用户 MUST 通过同一 header 导航切换 Tab，不得依赖跳转到独立 `/dashboard` 页面完成主流程。

#### Scenario: 默认入口

- **WHEN** 用户访问 `/`
- **THEN** 必须返回统一 Web 壳（`app.html`）
- **且** 必须包含 Tab：监测看板、情报中心、源数据、合作方、监测任务、数据源、采集调试、系统设置、大模型
