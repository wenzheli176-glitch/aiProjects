## Why

当前爬虫控制台（`/`）与风险看板（`/dashboard`）为两套独立 HTML，样式与导航重复；大模型配置、系统配置分散在两处且无写入权限控制。数据源仅有 `config.json` 中 `sources.*.enabled/label` 与 `heimao.*`/`xhs.*` 爬取参数，缺少可视化「开关 + 调参」界面，运维需直接改 JSON。产品已具备监测主路径，应将入口整合为单一 Web 壳，并引入管理员鉴权保护配置写入，同时保留采集调试 Tab 供 CDP/登录门禁排查。

## What Changes

- 新增 **统一 Web 壳** `templates/app.html` + `static/app.css`（及共享 JS）：左侧/顶栏 Tab 整合监测看板、合作方、监测任务、**数据源**、**采集调试**、系统设置、大模型；全局 Chrome 状态、登录等待横幅、可折叠日志在所有 Tab 可见。
- **路由整合**：`/` 为新壳主入口；`/dashboard` 与旧控制台路径 **301/redirect** 到对应 Tab（如 `/?tab=intel`）；逐步废弃独立 `index.html`/`dashboard.html` 或仅作 redirect 占位。
- 新增 **数据源管理 Tab**：展示 Registry 已注册源（heimao/xhs）；管理员可切换 `enabled`、编辑 `label`、可视化编辑 CrawlProfile 常用参数（页数、滚动、等待、URL 模板等）；UI 明确声明「新增数据源需在代码中注册 Adapter，无法仅靠配置添加」。
- 新增 **管理员鉴权**：`config.admin.*` + Session Cookie；**管理员**可写配置/源/合作方/密钥/Cookie；**操作员**（匿名或只读会话）可查看情报、创建/运行/停止监测任务、使用采集调试，但不可改系统配置与源参数。
- 新增/扩展 **分区写 API**：`PATCH /api/sources/{id}`、`PATCH /api/sources/{id}/profile`、`PATCH /api/monitor/defaults`；写操作须 `@require_admin`；保留 `POST /api/config` 供 JSON 高级（管理员）。
- **CSS 抽离**：共用组件样式迁入 `static/app.css`，删除两页重复内联 `<style>` 的主体部分。
- 修正采集调试/源配置 UI 文案：小红书「默认滚动次数」改为「默认采集页数」，与已归档页数语义一致。
- Intel REST **读 API** 仍内网开放；**写 API** 从「MVP 无鉴权」升级为「写操作需管理员 Session」（**BREAKING** 对依赖裸写 `POST /api/config` 的脚本）。

## Capabilities

### New Capabilities

- `admin-console-auth`：管理员登录/登出、Session、操作员 vs 管理员权限矩阵、写 API 保护。
- `unified-web-console`：单入口 Web 壳、Tab 导航、全局状态/日志、静态资源抽离、旧路由 redirect。

### Modified Capabilities

- `source-adapter`：数据源管理 UI + 分区 PATCH API；enabled/label/profile 可调；声明不可 UI 注册新源。
- `risk-dashboard-export-api`：看板并入统一壳；Intel REST 写操作鉴权要求更新（读仍内网开放）。

## Impact

**站点与模块**

| 区域 | 影响 |
|------|------|
| heimao / xhs | 爬取逻辑不变；参数改走源 Profile PATCH 或现有 config merge |
| login_gate | 无行为变更；采集调试 Tab 复用现有门禁与 `/api/auth/*` |
| 共用 | 新 `auth_admin.py` 或 `intel/admin_auth.py`；`crawler_web.py` 静态路由、`intel/api.py` 权限装饰器 |

**config.json 新增/变更**

| 字段 | 说明 |
|------|------|
| `admin.enabled` | 是否启用管理员鉴权（默认 true） |
| `admin.password_hash` 或 `admin.password_env` | 管理员口令 |
| `admin.session_secret_env` | Session 签名密钥环境变量名 |
| `admin.session_ttl_hours` | Session 有效期 |
| `sources.*.enabled` / `label` | 已有；由 UI 写入 |
| `heimao.*` / `xhs.*` | 已有；Profile PATCH 写入 tier A/B 子集 |
| `monitor.default_sources` / `default_max_pages` / `task_timeout_sec` | 已有；`PATCH /api/monitor/defaults` |

**前端**

- 新增 `templates/app.html`、`static/app.css`、`static/app.js`
- `templates/index.html`、`templates/dashboard.html` 废弃或 redirect

**API**

- 新增：`POST /api/admin/login|logout`、`GET /api/admin/session`
- 新增：`PATCH /api/sources/{id}`、`GET/PATCH /api/sources/{id}/profile`、`PATCH /api/monitor/defaults`
- 变更：写 config/analysis/partners/tasks/sources 需管理员 Session

**非目标**

- UI 动态注册第三数据源（weibo 等仍靠代码 + registry）
- 通用 config schema 编辑器（整包 JSON 高级 Tab 保留给管理员）
- OAuth / 多用户账号体系
