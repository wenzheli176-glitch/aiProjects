## MODIFIED Requirements

### Requirement: 统一 Web 入口

系统 SHALL 提供单一 Web 壳作为默认入口，整合原爬虫控制台与风险看板功能；用户 MUST 通过同一 header 导航切换 Tab，不得依赖跳转到独立 `/dashboard` 页面完成主流程。

#### Scenario: 默认入口

- **当** 用户访问 `/`
- **则** 必须返回统一 Web 壳（`app.html`）
- **且** 默认 Tab MUST 为首页看板（home）
- **且** Nav MUST 包含：首页看板、情报中心、源数据、合作方、监测任务、数据源、采集调试、系统设置、大模型（顺序可调整但 home 为第一项）

#### Scenario: 旧 URL 重定向

- **当** 用户访问 `/dashboard`
- **则** 必须重定向到统一壳的首页看板 Tab（`/?tab=home`）

#### Scenario: 采集调试 Tab 保留

- **当** 用户切换到采集调试 Tab
- **则** 必须提供原 `index.html` 的手工爬取、结果列表、停止/清空及 `/api/auth/*` 登录辅助能力
- **且** 不得移除 CDP 调试入口

## ADDED Requirements

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

系统 SHALL 在「数据源」Tab 以 Tab 切换各 source 配置（如 heimao / xhs），而非纵向堆叠全部源 card。

#### Scenario: 切换源

- **当** 用户点击 heimao 或 xhs Tab
- **则** 必须仅展示该源 enabled、label、crawl、normalize 表单
- **且** 保存 MUST 仍调用 `PATCH /api/sources/{id}`

## MODIFIED Requirements

### Requirement: 静态样式抽离

系统 SHALL 将共用 UI 样式置于 `static/app.css`；Web 壳与各 Tab MUST 引用该文件，不得复制大段内联 `<style>`。

#### Scenario: 样式复用

- **当** 加载统一 Web 壳
- **则** 必须加载 `/static/app.css` 与 `static/ui-shell.js`
- **且** 来源 tag、按钮、卡片、表格样式 MUST 与浅色主题一致
