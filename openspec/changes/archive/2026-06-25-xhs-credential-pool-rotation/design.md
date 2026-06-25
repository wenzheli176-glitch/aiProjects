## Context

当前 xhs 凭证通过 `monitor.workers.xhs.instances[].cookies_file` 与 `config.auth.xhs.cookies_file` 单轨配置；Cookie 实例 Tab 支持粘贴 JSON 与手动 diagnose。keyword 流水线在单 Chrome profile 上顺序执行全部 keyword，风控压力集中。用户已确认：仅防 xhs 封禁、最少 2 账号、账号远少于 keyword 数、主动每 keyword 轮换、失败跳过该号、文件存储、profile 与账号 1:1，且**本次包含控制台打开登录页导 Cookie**。

## Goals / Non-Goals

**Goals**

- xhs 账号池 CRUD（文件 + API）与 `acc-default` 自动迁移
- 数据源 Tab · xhs：账号列表、禁用/冷却、粘贴 Cookie、**打开登录页 → 登录完成 → 导出 Cookie**
- 每个 keyword 开始前 round-robin + rebind（shutdown Chrome → 换 `user_data_dir` + `cookies_file` → diagnose → pipeline）
- keyword `stats_json.account_id` 与 Run 日志可追踪
- 本 keyword 内账号失败跳过；enabled 账号 < 2 时 UI 警告

**Non-Goals**

- 黑猫多账号或轮换
- 同一 profile 绑定多个账号
- 自动识别禁言文案并长期冷却（可手动设 `cooldown_until`）
- 多 xhs Worker 并行（仍可为单槽位 `xhs-0`；轮换在槽位内换绑）

## Decisions

### 1. 账号池文件模型

```
credentials/xhs/
  accounts.json
  acc_default_cookies.json      # 迁移自 xhs_cookies.json
  acc_02_cookies.json
chrome_profiles/xhs/
  acc_default/                  # 迁移自 xhs_0
  acc_02/
```

`accounts.json` 字段：`id`, `label`, `cookies_file`, `user_data_dir`, `enabled`, `cooldown_until`, `ban_note`, `created_at`, `last_used_at`。轮换配置：`policy=round_robin_per_keyword`，`min_accounts=2`，`cursor` 持久化于 JSON 或内存+每次 pick 写回。

**迁移**：`ensure_xhs_accounts_migrated()` 在首次 `load_accounts()` 时：若 `accounts.json` 不存在且存在 `credentials/xhs_cookies.json`，复制 cookie 与 profile 目录为 `acc-default`，不删除旧文件。

### 2. Round-robin 与失败跳过

`pick_account_for_keyword(run_id, keyword_run_id)`：

1. 从 cursor 起遍历 enabled 且 `cooldown_until` 未到的账号（循环）
2. 对每个候选：`rebind_worker(account)` → `diagnose` → 成功则返回并推进 cursor
3. 失败：记 WARN，**不**永久禁用，尝试下一候选
4. 无候选：返回 None → keyword `failed`（`no_available_account`）

相邻 keyword 尽量不同号；2 账号 × N keyword 呈 A-B-A-B 交替。

### 3. Worker rebind（profile 1:1）

在 `intel/worker.py` / `worker_pool` keyword_pipeline claim 前：

- `terminate` 当前 xhs Chrome（若 profile 变化）
- 更新 instance 运行时上下文：`cookies_file`, `user_data_dir`（来自账号记录）
- Orchestrator 按新 `user_data_dir` 启动 Chrome（独立 CDP，仍用 instance 的 `cdp_port` 或账号专属端口——**决策：单槽位复用 config cdp_port，仅换 profile 目录**）
- `apply_cookies_from_file` + `diagnose_login` 通过后再跑 `run_xhs_keyword_pipeline`

与 `validate_worker_instances` 不冲突：运行时绑定变化，非 config 多 instance 共用文件。

### 4. 控制台登录导 Cookie（本次纳入）

独立**登录会话**，避免与监测 Run 争用 Chrome：

| API | 作用 |
|-----|------|
| `POST /api/xhs/accounts` | 创建账号记录 + 空 profile 目录 + cookies 路径 |
| `POST /api/xhs/accounts/{id}/login/start` | 管理员；若 `is_monitor_busy()` 返回 409；启动该账号 profile 的 Chrome（`login_cdp_port_base + hash` 或专用 `9250+`），打开 `auth.xhs.login_url` |
| `GET /api/xhs/accounts/{id}/login/status` | 轮询：`waiting` / `logged_in` / `timeout` / `error`（`has_xhs_session` 或 diagnose） |
| `POST /api/xhs/accounts/{id}/login/finish` | `export_cookies_from_context` → 写入账号 `cookies_file` → diagnose → 关闭登录 Chrome |
| `POST /api/xhs/accounts/{id}/login/cancel` | 关闭 Chrome，不保存 |

实现复用 `prepare_browser_for_crawl` / `connect_cdp` 模式，但使用**账号 profile + 临时 CDP 端口**登记在 `intel/xhs_credentials._login_sessions`（内存 dict，单进程；文档注明重启丢失进行中会话）。

UI：数据源 xhs → 账号行「登录获取」→ 弹层说明扫码 → 每 2s 轮询 status → 登录成功后「完成并保存」调用 finish。

**备选已弃用**：仅粘贴 Cookie 不提供登录——用户明确要求纳入本次。

### 5. UI 入口

主入口：**数据源 Tab · 小红书** 底部「登录账号池」表格。Cookie 实例 Tab 对 xhs 显示链接「多账号请在数据源 · 小红书管理」。

### 6. config 字段

```json
"monitor": {
  "xhs_credential_pool": {
    "min_accounts": 2,
    "login_cdp_port_base": 9250,
    "login_wait_timeout_sec": 600
  }
}
```

`auth.xhs.cookies_file` 继续指向 `acc-default` 的 cookies（兼容手工 crawl Tab）。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 每 keyword 重启 Chrome 增加耗时 | 相对 triage/analyze 可接受；日志标注 rebind 耗时 |
| 登录会话与 Run 端口冲突 | busy 检查 + 独立 login 端口段 |
| 仅 2 账号仍多次复用 | UI 提示单号承担次数；鼓励继续加号 |
| 登录会话进程内内存 | cancel/finish 必须关 Chrome；服务重启提示重新登录 |

## Migration Plan

1. 部署后首次读池 → 自动 `acc-default` 迁移
2. 管理员在数据源 xhs 添加第二账号（登录导 Cookie 或粘贴）
3. 启用轮换；旧单号监测任务无需改配置
4. 回滚：保留 `accounts.json`，设 `enabled=false`  on 新号，仅留 `acc-default`

## Open Questions

- 登录 Chrome 是否与 Worker 共用 `cdp_port`：**否**，使用 `login_cdp_port_base` 偏移。
- 粘贴 Cookie 添加账号：**保留**为添加账号后的备选操作（与登录并列）。
