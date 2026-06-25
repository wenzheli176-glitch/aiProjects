## 1. 账号池核心与迁移

- [x] 1.1 新增 `intel/xhs_credentials.py`：`load/save accounts.json`、`ensure_migrated_acc_default`、路径校验
- [x] 1.2 实现 `pick_account_for_keyword`（round-robin、跳过 disabled/cooldown、cursor 持久化）
- [x] 1.3 实现账号 CRUD 辅助：`create_account`、`update_account`、`delete_account`（软删或 enabled=false）
- [x] 1.4 `config.py` / `config.json` 增加 `monitor.xhs_credential_pool` 默认值
- [x] 1.5 `scripts/test_xhs_credentials.py`：迁移、pick 交替、冷却跳过、失败跳过逻辑

## 2. API

- [x] 2.1 `GET/POST /api/xhs/accounts`、`PATCH/DELETE /api/xhs/accounts/{id}`
- [x] 2.2 `POST /api/xhs/accounts/{id}/cookies` 粘贴 Cookie + 可选 diagnose
- [x] 2.3 登录会话：`login/start`、`login/status`、`login/finish`、`login/cancel`（busy 409、独立 CDP 端口）
- [x] 2.4 所有写路由 `@require_admin`；更新 `docs/API对接说明.md`

## 3. Worker 轮换与 rebind

- [x] 3.1 keyword claim 前调用 pick + rebind（`intel/worker.py` / `worker_pool` / `keyword_pipeline` 接入点）
- [x] 3.2 profile 变化时 shutdown/restart xhs Chrome；diagnose 失败尝试下一账号
- [x] 3.3 `stats_json.account_id`（及 label）写入；日志含账号信息
- [x] 3.4 单进程 crawl 路径（workers disabled）同样 rebind，避免行为分叉
- [x] 3.5 扩展 `test_task_control` 或新测试：mock pick 顺序

## 4. 控制台 UI（数据源 · xhs）

- [x] 4.1 `static/app-sources.js`：xhs Tab 账号池表格（列表、警告 <2 账号）
- [x] 4.2 「添加账号」+「登录获取」流程 UI（轮询 status、完成/取消）
- [x] 4.3 禁用、冷却日期、粘贴 Cookie、诊断按钮
- [x] 4.4 `panel-cookies.js`：xhs 引导文案指向数据源 Tab
- [x] 4.5 `templates/app.html` / CSS 必要样式

## 5. 集成与文档

- [x] 5.1 `auth.xhs.cookies_file` 与 `acc-default` 同步；`cookie_instances` xhs 列表可读池状态
- [x] 5.2 更新根目录 `代码说明.md`（账号池、API、轮换语义）
- [x] 5.3 `openspec/verification-pending.md` 登记手动项：登录导 Cookie、2 账号轮换 Run、禁言冷却跳过

## 6. 手动验证（Chrome）

- [x] 6.1 升级后确认 `acc-default` 自动迁移，旧监测仍可跑
- [x] 6.2 数据源 xhs：添加第二账号 → 打开登录页 → 扫码 → 完成保存 → diagnose 通过
- [x] 6.3 监测任务多 keyword Run：日志/子任务可见 account_id 交替；单号 diagnose 失败时自动换号
- [ ] 6.4 监测 Run 进行中 login/start 返回 409
