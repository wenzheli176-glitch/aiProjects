## ADDED Requirements

### Requirement: 源数据与情报中心列表分页

系统 SHALL 在统一 Web 壳「源数据」Tab 与「情报中心」Tab 的主列表提供分页控件；默认每页 20 条，可选 50/100/200；MUST 与后端 `page` / `page_size` 参数一致。

#### Scenario: 默认分页

- **WHEN** 用户打开源数据或情报中心 Tab 且无 URL query
- **THEN** MUST 请求 `page=1` 且 `page_size=20`
- **且** 列表下方 MUST 展示「第 X / Y 页」与上一页/下一页

#### Scenario: 计数展示

- **WHEN** API 返回 `total` 大于 0
- **THEN** MUST 展示「共 N 条 · 第 start–end 条」摘要
- **且** 不得仅显示当前页行数而隐藏全量 total

#### Scenario: URL 持久化

- **WHEN** 用户切换页码或每页条数
- **THEN** MUST 更新 URL query（`raw_page` / `raw_page_size` 或 `intel_page` / `intel_page_size`）
- **且** 刷新页面 MUST 恢复相同分页状态

#### Scenario: API 上限

- **WHEN** 客户端请求 `page_size` 大于 200
- **THEN** 服务端 MUST clamp 为 200
- **且** 小于 1 时 MUST 视为 1

## MODIFIED Requirements

### Requirement: 任务详情源数据与情报 Tab

详情页源数据/情报 Tab MUST 展示该任务下 raw/intel 列表（各最多 100 条）；运行中轮询 MUST 增量 patch 表格行，保留滚动位置，不得闪屏。**全局**源数据 Tab 与情报中心 Tab MUST 使用分页（见「源数据与情报中心列表分页」），不得固定仅请求第一页 100 条。

#### Scenario: 手动刷新

- **WHEN** 用户点击 Tab 内「刷新」
- **THEN** MAY 显示加载态后渲染全表

#### Scenario: 自动刷新

- **WHEN** 任务运行中且用户位于任务详情内的源数据或情报 Tab
- **THEN** MUST 仅更新变更行与计数
- **且** 新增行插入列表顶部时 MUST 补偿 scrollTop
