## ADDED Requirements

### Requirement: 统一 Web 入口

系统 SHALL 提供单一 Web 壳作为默认入口，整合原爬虫控制台与风险看板功能；用户 MUST 通过同一 header 导航切换 Tab，不得依赖跳转到独立 `/dashboard` 页面完成主流程。

#### Scenario: 默认入口

- **当** 用户访问 `/`
- **则** 必须返回统一 Web 壳（`app.html`）
- **且** 必须包含 Tab：监测看板、合作方、监测任务、数据源、采集调试、系统设置、大模型

#### Scenario: 旧 URL 重定向

- **当** 用户访问 `/dashboard`
- **则** 必须重定向到统一壳的监测看板 Tab（如 `/?tab=intel`）

#### Scenario: 采集调试 Tab 保留

- **当** 用户切换到采集调试 Tab
- **则** 必须提供原 `index.html` 的手工爬取、结果列表、停止/清空及 `/api/auth/*` 登录辅助能力
- **且** 不得移除 CDP 调试入口

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
- **则** 必须加载 `/static/app.css`
- **且** 来源 tag、按钮、卡片、表格样式必须与整合前视觉一致或等价

### Requirement: 大模型配置唯一入口

系统 SHALL 仅在统一壳「大模型」Tab 提供 analysis 配置表单；不得在两套独立页面重复相同保存逻辑。

#### Scenario: 保存大模型配置

- **当** 管理员在大模型 Tab 保存
- **则** 必须调用 `POST /api/analysis/config`（需管理员 Session）
- **且** 保存后 AI 日志 Tab 必须仍可查看 `/api/analysis/logs`
