## Context

- **现状 UI**：`templates/index.html`（爬虫控制台）与 `templates/dashboard.html`（风险看板）各自内联 ~200 行 CSS，通过 header 链接互跳。`index.html` 含系统配置 7 Tab（含 heimao/xhs/auth/analysis）；`dashboard.html` 重复大模型 Tab 并调用 `/api/analysis/config`。
- **现状 API**：`GET/POST /api/config` 整包 deep_merge；`GET /api/sources` 只读；无源 Profile 分区写；所有写接口无 Session（`risk-dashboard-export-api` spec 声明 MVP 无鉴权）。
- **现状 Registry**：`intel/registry.py` 硬编码 heimao/xhs；`config.sources.*` 仅 `enabled`+`label`。
- **用户决策**：数据源 UI = 开关 + 调参；加源靠开发；整合后保留**采集调试** Tab；配置写需**管理员**；样式抽 `static/app.css`。

## Goals / Non-Goals

**Goals:**

- 单一 Web 入口与 Tab 壳，全局 `S.running` / `login_wait` 全 Tab 可见。
- 数据源 Tab：已注册源列表、enabled/label、CrawlProfile 常用字段表单。
- 管理员 Session 保护配置/源/合作方 CRUD/密钥/Cookie 写入；操作员可跑监测与采集调试。
- 共用 `static/app.css` + `static/app.js`；旧 URL redirect。

**Non-Goals:**

- UI 注册第三源、动态 import adapter。
- 全字段 schema 驱动表单（高级 selector/regex 仍 JSON 或折叠高级区）。
- OAuth、多用户、审计日志（可后续）。

## Decisions

### 1. 单页壳 `app.html` + hash/query Tab

**选择**：`GET /` 返回 `templates/app.html`；Tab 用 `?tab=intel|crawl|sources|system|analysis|partners|tasks`（或 hash）切换 panel display，不引入前端框架。

**理由**：与现有 vanilla JS 一致；迁移时可逐 panel 从 index/dashboard copy 逻辑到 `app.js` 分区函数。

**Redirect**：

- `/dashboard` → `/?tab=intel`
- 可选：保留 `/crawl` → `/?tab=crawl` 便于书签

### 2. 静态资源

```
static/
  app.css      # 变量 + layout + components（从 index/dashboard 合并去重）
  app.js       # api(), tabRouter, statusPoll, adminSession, 各 panel init
templates/
  app.html     # shell + panel sections（或 {% include %} 若不用 Jinja 则纯 HTML section）
```

Flask：`app.route('/static/<path>')` 或使用 `static_folder='static'`。

### 3. 权限模型：两角色 + Session Cookie

| 能力 | 操作员（未登录 admin） | 管理员 |
|------|------------------------|--------|
| GET intel/partners/tasks/sources/status | ✓ | ✓ |
| POST monitor/run, stop, reanalyze | ✓ | ✓ |
| POST crawl_heimao/xhs, auth/open_login | ✓ | ✓ |
| PATCH sources, monitor/defaults | ✗ | ✓ |
| POST /api/config, analysis/config | ✗ | ✓ |
| POST partners CRUD, monitor tasks CRUD | ✗ | ✓ |
| POST auth/save (Cookie 落盘) | ✗ | ✓ |

**实现**：新模块 `admin_auth.py`：

- `config.admin.password_env`（默认 `ADMIN_PASSWORD`）或 `password_hash`（pbkdf2）
- `itsdangerous.URLSafeTimedSerializer` 或 Flask `session`（需 `secret_key` from `admin.session_secret_env`）
- `@require_admin` 装饰器：无有效 session → 403 JSON `{ok:false, msg:'需要管理员登录'}`

**登录 API**：

```
POST /api/admin/login  {password}
GET  /api/admin/session → {role:'admin'|'operator', logged_in: bool}
POST /api/admin/logout
```

**前端**：header 登录按钮；非 admin 时隐藏保存按钮、表单 `readonly`；403 时提示登录。

**替代**：HTTP Basic — 拒绝，对 SPA 式 Tab 体验差。

**`admin.enabled=false`**：开发模式跳过写保护（仅本地，文档警告）。

### 4. 数据源 API

**已注册源列表**（扩展 `GET /api/sources`）：

```json
{
  "sources": [
    {
      "source_id": "heimao",
      "label": "黑猫投诉",
      "enabled": true,
      "registered": true,
      "supports_fetch_detail": true,
      "profile_keys": ["default_max_pages", "..."]
    }
  ],
  "notice": "新增数据源需在代码中注册 CrawlAdapter"
}
```

- `registered=true`：`_crawlers` 中存在；`config` 有 entry 但无 crawler → 灰显不可启用。
- `PATCH /api/sources/{id}`：`{enabled, label}` → `save_config({sources:{id:{...}}})`
- `GET/PATCH /api/sources/{id}/profile`：读写 `config.{id}.*` 白名单字段（见下）

**Profile 白名单**（tier A+B，在 `config.py` 或 `source_profiles.py` 常量）：

| source | 字段示例 |
|--------|----------|
| heimao | default_max_pages, default_fetch_detail, search_url_template, page_timeout_ms, detail_wait_min/max, ... |
| xhs | default_max_pages, scroll_times_per_page, scroll_pixels, scroll_wait_seconds, search_url_template, note_item_selector, ... |

高级字段（link_regex、detail author_cats）可第二批加入 PATCH 白名单或仅 JSON 高级 Tab。

**PATCH /api/monitor/defaults`**：`default_sources`, `default_max_pages`, `task_timeout_sec`（管理员）。

### 5. 配置写入不互相覆盖

沿用 `config.save_config` deep_merge；各 PATCH 只提交子树。禁止操作员调用整包 POST。

爬取进行中（`S.running`）仍拒绝保存（现有逻辑保留）。

### 6. Panel 迁移顺序

1. Shell + CSS + status/login banner + tab router
2. 迁移 dashboard panels（intel, partners, tasks, analysis）
3. 迁移 index crawl panel + auth actions（不含重复 analysis）
4. 新 sources panel + system panel（从 index config 拆 global/chrome/monitor/auth）
5. Redirect 旧页；删除或 stub index/dashboard

### 7. login_gate 三条路径

采集调试 Tab 继续调用 `crawl_heimao`/`crawl_xhs` → `ensure_login_for_detail` / `wait_for_site_login` / `fetch_xhs_detail_via_modal`；**不修改** `login_gate.py` 语义，仅 UI 容器变更。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 单文件 app.js 过大 | 按 panel 分函数；可选后期拆 `static/panels/*.js` |
| **BREAKING** 脚本裸 POST config | 文档 + 登录；或 `admin.enabled=false` 过渡 |
| enabled=false 后旧任务仍含该源 | 运行时报错已有 spec；UI 改 enabled 时 confirm |
| 迁移遗漏 dashboard/index 行为 | tasks 含对照清单与手动验证 |
| Session 密钥未配置 | 启动警告；拒绝 login 直至配置 |

## Migration Plan

1. 部署新 static + app.html；redirect 旧 URL。
2. 配置 `ADMIN_PASSWORD` 环境变量；首次登录改密（可选后续）。
3. 更新 `代码说明.md`、`docs/API对接说明.md` 鉴权与源 API 章节。
4. **Rollback**：恢复 index/dashboard 路由；`admin.enabled=false`。

## Open Questions

- （已决）操作员可跑监测任务、不可改合作方 — **采用**：操作员可跑任务；合作方/任务 **CRUD 需管理员**（名单属配置类数据）。若需放宽可后续改 spec。
