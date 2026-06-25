# unified-web-console Specification

## Purpose
TBD - created by archiving change unified-console-source-admin. Update Purpose after archive.
## Requirements
### Requirement: 统一 Web 入口

系统 SHALL 提供单一 Web 壳作为默认入口，整合原爬虫控制台与风险看板功能；用户 MUST 通过同一 header 导航切换 Tab，不得依赖跳转到独立 `/dashboard` 页面完成主流程。

#### Scenario: 默认入口

- **WHEN** 用户访问 `/`
- **THEN** 必须返回统一 Web 壳（`app.html`）
- **且** 必须包含 Tab：监测看板、情报中心、源数据、合作方、监测任务、数据源、采集调试、系统设置、大模型

### Requirement: 全局运行状态可见

系统 SHALL 在 Web 壳层轮询 `/api/status`，在所有 Tab 展示 Chrome 状态、`S.running`、`login_wait` 横幅及可折叠日志。

#### Scenario: 监测任务等待登录

- **当** 监测或采集任务处于 `waiting_login`
- **则** 用户在监测看板 Tab 也必须看到登录等待横幅
- **且** 不得要求用户切回旧控制台页面

### Requirement: 静态样式抽离

系统 SHALL 将共用 UI 样式置于 `static/app.css`；Web 壳与各 Tab MUST 引用该文件，不得复制大段内联 `<style>`。

#### Scenario: 样式复用

- **当** 加载统一 Web 壳
- **则** 必须加载 `/static/app.css` 与 `static/ui-shell.js`
- **且** 来源 tag、按钮、卡片、表格样式 MUST 与浅色主题一致

### Requirement: 大模型配置唯一入口

系统 SHALL 仅在统一壳「大模型」Tab 提供 analysis 配置表单；不得在两套独立页面重复相同保存逻辑。

#### Scenario: 保存大模型配置

- **当** 管理员在大模型 Tab 保存
- **则** 必须调用 `POST /api/analysis/config`（需管理员 Session）
- **且** 保存后 AI 日志 Tab 必须仍可查看 `/api/analysis/logs`

### Requirement: 控制台交互组件与浅色主题

系统 SHALL 使用共享 UI 组件（Modal、Drawer、Toast、Confirm）与浅色 design tokens；列表页 MUST 采用摘要表 + 详情页/Drawer 模式，表单创建编辑 MUST 使用 Modal。

#### Scenario: 浅色主题

- **当** 加载任意 Tab
- **则** 必须应用 `static/app.css` 浅色 tokens（白/浅灰底、深色文字）
- **且** 不得保留全站深色 `#0f172a` 作为主背景

#### Scenario: Modal 表单

- **当** 用户在合作方或监测任务 Tab 添加或编辑
- **则** 必须在 Modal 中展示表单
- **且** 列表页 MUST 全宽展示，不得使用 split 右侧 form-box 占栏

#### Scenario: Drawer 只读详情

- **当** 用户在监测任务 Run 摘要表点击某 Run
- **则** 必须从右侧 Drawer 展示 Run 详情
- **且** 不得占用任务编辑 form-box 区域

#### Scenario: Toast 替代 alert

- **当** 非阻塞操作成功或失败（如刷新、校验提示）
- **则** SHOULD 使用 Toast 而非 `alert()`
- **且** 危险确认 MUST 使用 Confirm 组件而非原生 `confirm()`（MVP 可保留少量 confirm 但须列入排查清单）

### Requirement: 响应式布局

系统 SHALL 在 viewport 宽度 ≤1000px 时仍可使用主要 Tab：Nav 可折叠或换行，表格可横向滚动，Modal/Drawer 全宽或近全宽。

#### Scenario: 小屏监测任务

- **当** 用户在窄屏打开监测任务 Tab
- **则** Run 历史手风琴与 Drawer MUST 可正常展开与关闭
- **且** 操作按钮 MUST 不 irreversibly 遮挡表格内容

### Requirement: 数据源 Tab 切换

系统 SHALL 在「数据源」Tab 以 Tab 切换各 source 配置（如 heimao / xhs），而非纵向堆叠全部源 card。小红书 Tab MUST 在 crawl 配置下方包含登录账号池区块。

#### Scenario: 切换源

- **WHEN** 用户点击 heimao 或 xhs 子 Tab
- **THEN** MUST 仅展示该源配置表单
- **AND** xhs 子 Tab MUST 展示账号池表格

### Requirement: Cookie 实例管理 Tab

统一 Web 控制台 SHALL 提供 Cookie / Worker 实例管理入口。

#### Scenario: 导航入口

- **当** 管理员登录
- **则** MUST 可进入 Cookie 实例管理页

#### Scenario: 失效横幅

- **当** 任一实例 diagnose 失败
- **则** MUST 显示全局或监测页横幅

### Requirement: 多实例登录等待展示

系统 SHALL 在多个 Worker 处于 login_gate 等待时聚合展示各实例状态。

#### Scenario: 多 Worker 横幅聚合

- **当** 多个 Worker 处于 login_gate 等待
- **则** `/api/status` 或监测页 MUST 聚合展示各 instance 的 site + elapsed（来自 run_state/worker_login_wait）

#### Scenario: 停止等待

- **当** 用户停止 Run
- **则** 所有 Worker login 等待 MUST 终止

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

### Requirement: 合作方列表统计列

系统 SHALL 在合作方列表表格展示情报与源数据统计，并支持点击钻取。

#### Scenario: 情报列格式

- **WHEN** 渲染合作方列表
- **THEN** MUST 展示 `intel_medium_plus/intel_total` 格式（如 `5/12`）
- **且** 点击 MUST 打开合作方详情情报子 Tab

#### Scenario: 源数据列

- **WHEN** 渲染合作方列表
- **THEN** MUST 展示 `raw_total`（无 default_task 时显示 `-` 或 `0`）
- **且** 点击 MUST 打开合作方详情源数据子 Tab

### Requirement: 任务 ignore_before 表单

系统 SHALL 在监测任务创建/编辑 Modal 提供「忽略早于」日期字段，映射 `business_spec.ignore_before`。

#### Scenario: 保存与展示

- **WHEN** 管理员保存任务且填写日期
- **THEN** MUST 持久化到 business_spec
- **WHEN** 再次打开编辑
- **THEN** MUST 回显已保存日期

### Requirement: 管理员数据清理 UI

系统 SHALL 为管理员提供批量清理 Modal，支持清理 raw 或 intel。

#### Scenario: 任务 Tab 入口

- **WHEN** 管理员在监测任务 Tab 打开清理
- **THEN** MUST 预填 `task_id`
- **且** MUST 支持 dry_run 预览与确认删除

#### Scenario: 合作方详情入口

- **WHEN** 管理员在合作方详情打开清理
- **THEN** MUST 预填 `partner_id`
- **且** MUST 提供关联任务选择（默认 default_task）

#### Scenario: 非管理员不可见

- **WHEN** 用户非管理员且 `admin.enabled=true`
- **THEN** 清理入口 MUST 隐藏或禁用

### Requirement: 合作方数据源超时表单

合作方新建/编辑 Modal MUST 提供「小红书超时(秒)」「黑猫超时(秒)」字段；留空表示使用全局默认；保存至 `source_timeouts`。

#### Scenario: 编辑合作方超时

- **当** 用户填写 xhs 超时 7200 并保存
- **则** `PUT /api/partners/{id}` MUST 持久化 `source_timeouts.xhs=7200`

### Requirement: Run keyword 子任务面板

Run 详情 MAY 保留 keyword 子任务表；**任务详情 → 子任务 Tab** MUST 为分源子任务的主入口，展示 keyword 与队列统一列表及阶段用时列。存在 failed keyword 时 MUST 提供「重跑失败 keyword」按钮。

#### Scenario: 查看子任务

- **WHEN** 用户在任务详情子任务 Tab 选择 Run
- **THEN** MUST 请求 subtasks API 并渲染分源块与子任务表
- **且** 表格 MUST 含列表爬取 / 详情勘察 / 分析 用时列

### Requirement: 任务列表子任务进度

监测任务列表状态列 MUST 在 `progress.subtasks` 或 `progress.sources` 存在时显示子任务/分源进度摘要（含 failed 计数）。

#### Scenario: 运行中任务

- **WHEN** 任务 crawling 且 progress 含分源或 keyword 汇总
- **THEN** 状态列 MUST 显示可读进度摘要（非原始 JSON）

### Requirement: 监测任务详情页

系统 SHALL 在监测任务 Tab 提供列表视图与任务详情视图；详情 MUST 含 **概览**、**执行历史**、**子任务**、**源数据**、**情报** 五个子 Tab。

#### Scenario: URL 深链

- **WHEN** URL 含 `?tab=tasks&monitor_task_id={id}&task_tab=overview|runs|subtasks|raw|intel`
- **THEN** MUST 展示任务详情视图并激活对应子 Tab

#### Scenario: 返回列表

- **WHEN** 用户在详情点击「返回」
- **THEN** MUST 清除 `monitor_task_id`、`task_tab`、`run_id` query
- **且** 展示任务列表视图

#### Scenario: 列表行进入详情

- **WHEN** 用户点击任务列表行或「详情」
- **THEN** MUST 打开任务详情（不得仅展开 Run Drawer 作为唯一入口）

### Requirement: 任务详情子任务 Tab

子任务 Tab MUST 按数据源分块展示队列与 keyword 合并列表；每行 MUST 含细粒度状态（排队 / 爬取列表 / 勘察详情 / 分析 / 完成 / 失败）及三列阶段用时：**列表爬取**、**详情勘察**、**分析**（毫秒，运行中增量更新）。

#### Scenario: 选择 Run 并刷新

- **WHEN** 用户选择 Run 并点击「刷新」
- **THEN** MUST 请求 `GET /api/monitor/runs/{run_id}/subtasks`
- **且** 渲染每源 `subtask_items` 表格

#### Scenario: 运行中增量刷新

- **WHEN** 任务 crawling/analyzing 且用户位于子任务 Tab
- **THEN** 轮询 MUST 通过 patch 更新状态与阶段用时
- **且** 不得整页替换为「加载中…」

#### Scenario: 重跑失败 keyword

- **WHEN** xhs 源存在 failed 子任务
- **THEN** MUST 提供「重跑失败」按钮调用 `POST /api/monitor/retry-keywords`

### Requirement: 任务详情源数据与情报 Tab

详情页源数据/情报 Tab MUST 展示该任务下 raw/intel 列表（各最多 100 条）；运行中轮询 MUST 增量 patch 表格行，保留滚动位置，不得闪屏。

#### Scenario: 手动刷新

- **WHEN** 用户点击 Tab 内「刷新」
- **THEN** MAY 显示加载态后渲染全表

#### Scenario: 自动刷新

- **WHEN** 任务运行中且用户位于源数据或情报 Tab
- **THEN** MUST 仅更新变更行与计数
- **且** 新增行插入列表顶部时 MUST 补偿 scrollTop

### Requirement: 任务列表无闪屏刷新与分源进度

监测任务列表在轮询刷新时 MUST 使用行级 patch（`patchTaskRow`）；状态列 MUST 在 `progress.sources` 存在时展示分源子任务摘要；`#taskStatus` MUST 显示中文进度摘要而非 JSON。

#### Scenario: 运行中轮询

- **WHEN** 存在 crawling/analyzing 任务且列表可见
- **THEN** 每 3s 刷新 MUST 不重建整表 DOM
- **且** 已展开 Run 历史行 MUST 保持展开状态

### Requirement: 数据源 xhs 登录账号池 UI

系统 SHALL 在「数据源」Tab · 小红书配置区提供「登录账号池」管理：列表、添加账号、登录获取 Cookie、粘贴 Cookie、诊断、禁用与冷却设置。

#### Scenario: 账号列表展示

- **WHEN** 管理员打开数据源 · 小红书
- **THEN** MUST 请求 `GET /api/xhs/accounts` 并展示 label、enabled、cooldown_until、cookie_count、最近 diagnose

#### Scenario: 添加账号并登录

- **WHEN** 管理员点击「添加账号」并选择「打开登录页」
- **THEN** MUST 调用 login/start 并展示等待登录说明
- **AND** MUST 轮询 login/status 直至 logged_in 或 timeout
- **AND** logged_in 后 MUST 提供「完成并保存」调用 login/finish

#### Scenario: 启用账号不足警告

- **WHEN** enabled 账号数小于 2
- **THEN** MUST 在账号池区域显示黄色警告（建议添加账号以启用轮换）

#### Scenario: 设置冷却

- **WHEN** 管理员为账号设置禁言冷却日期
- **THEN** MUST PATCH 账号 `cooldown_until` 并刷新列表

#### Scenario: 操作员只读

- **WHEN** 非管理员访问数据源 xhs 账号池
- **THEN** 写操作按钮 MUST 隐藏或禁用（与 `admin-only-save` 一致）

