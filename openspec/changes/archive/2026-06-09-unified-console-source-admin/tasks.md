## 1. 静态资源与 Web 壳

- [x] 1.1 创建 `static/app.css`：合并 index/dashboard 共用变量、header、nav、card、btn、table、tag、form
- [x] 1.2 创建 `static/app.js`：共用 `api()`、Tab 路由（`?tab=`）、status 轮询、toast（实现为 `app-core.js` + panel 脚本）
- [x] 1.3 创建 `templates/app.html`：header + 侧栏/顶栏 Tab + 各 panel 容器 + 全局 status 条 + login_wait 横幅 + 日志区
- [x] 1.4 `crawler_web.py`：配置 Flask `static_folder`；`GET /` 返回 app.html；`/dashboard` redirect 到 `/?tab=intel`

## 2. 管理员鉴权

- [x] 2.1 新增 `admin_auth.py`（或 `intel/admin_auth.py`）：口令校验、Session 签发/验证、`require_admin` 装饰器
- [x] 2.2 `config.py` / `config.json` 增加 `admin.*` 默认值；文档说明 `ADMIN_PASSWORD`、`ADMIN_SESSION_SECRET` 环境变量
- [x] 2.3 实现 `POST /api/admin/login`、`POST /api/admin/logout`、`GET /api/admin/session`
- [x] 2.4 为写 API 加 `@require_admin`：`POST /api/config`、analysis/config、partners CRUD、monitor tasks CRUD、auth/save、sources PATCH、monitor/defaults PATCH
- [x] 2.5 保持操作员可：`POST /api/monitor/run|stop|reanalyze`、crawl_heimao/xhs、auth/open_login|export|diagnose、GET 全系

## 3. 数据源 API 与 Profile 白名单

- [x] 3.1 定义 heimao/xhs profile 字段白名单（tier A+B）常量
- [x] 3.2 扩展 `GET /api/sources`：registered、enabled、supports_fetch_detail、notice 文案
- [x] 3.3 实现 `PATCH /api/sources/<id>`（enabled、label）
- [x] 3.4 实现 `GET/PATCH /api/sources/<id>/profile`（白名单 merge 至 config.{id}.*）
- [x] 3.5 实现 `GET/PATCH /api/monitor/defaults`（default_sources、default_max_pages、task_timeout_sec）

## 4. Panel 迁移

- [x] 4.1 迁移 dashboard：情报看板、合作方、监测任务、大模型+AI 日志 → app panel + app.js 函数
- [x] 4.2 迁移 index：采集调试（手工爬、结果、停止）、auth 按钮 → crawl panel
- [x] 4.3 新建 sources panel：源列表、enabled 开关、label、profile 表单（管理员可编辑）
- [x] 4.4 新建 system panel：Chrome/全局/monitor 默认/auth（从 index config 拆出）；JSON 高级仅管理员
- [x] 4.5 移除 dashboard/index 中重复 analysis 表单；大模型 Tab 为唯一入口
- [x] 4.6 修正 xhs 配置文案：「默认滚动次数」→「默认采集页数」

## 5. 前端权限 UX

- [x] 5.1 header 管理员登录/登出 UI；`GET /api/admin/session` 驱动 readonly 模式
- [x] 5.2 非管理员：隐藏/禁用保存按钮；403 时提示登录
- [x] 5.3 数据源 Tab 顶部展示「新源需代码注册」说明

## 6. 文档

- [x] 6.1 更新根目录 `代码说明.md`：统一入口、Tab 结构、admin、sources API
- [x] 6.2 更新 `docs/API对接说明.md`：鉴权、PATCH sources、BREAKING 写接口
- [x] 6.3 stub 或 redirect 旧 `templates/index.html`、`templates/dashboard.html`（可选保留最小 redirect 页）

## 7. 手动验证

- [x] 7.1 访问 `/` 切换全部 Tab，功能与整合前等价（情报筛选、创建任务、手工爬取）
- [x] 7.2 `/dashboard` redirect 正常；监测任务 waiting_login 时任意 Tab 见横幅
- [x] 7.3 未登录：可 run 监测、不可 PATCH sources / POST partners
- [x] 7.4 管理员登录：可改源 enabled、xhs default_max_pages；保存后下次爬取生效
- [x] 7.5 采集调试 Tab：黑猫/XHS 手工爬 + 登录续跑 + 弹窗详情回归
- [x] 7.6 `admin.enabled=false` 本地模式写 API 仍可用（开发文档说明）
