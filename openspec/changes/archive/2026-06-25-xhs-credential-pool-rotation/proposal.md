## Why

小红书单账号长期承担全部 keyword 流水线，禁言周期已从一周升至一个月；现有「一 Worker 实例 = 一固定 cookies_file」无法按 keyword 分散账号风险，且添加新号依赖手工粘贴 Cookie 或离线脚本，运维成本高。

## What Changes

- **xhs 账号池**：`credentials/xhs/accounts.json` 索引多账号；每账号独立 `cookies_file` + `user_data_dir`（1:1 永久绑定，禁止同 profile 轮换多号）。
- **旧配置迁移**：首次启动将 `credentials/xhs_cookies.json` + `chrome_profiles/xhs_0` 自动复制为 `acc-default`。
- **主动轮换**：每个 keyword 子任务开始前 round-robin 选取下一可用账号；账号数少于 keyword 数时交替使用（最少 2 个启用账号，不足时横幅警告仍允许 Run）。
- **失败跳过**：本 keyword 内 diagnose/绑定失败则跳过该号尝试下一号；全部失败则该 keyword 标记 failed，Run 继续其他 keyword。
- **控制台登录导 Cookie**：数据源 · 小红书 Tab 内「添加账号 → 打开登录页」；独立 Chrome profile 扫码/登录后导出 Cookie 并自动诊断（纳入本次，非后续阶段）。
- **黑猫**：行为不变，仍走现有 Cookie 实例 / 单 cookies_file。

## Capabilities

### New Capabilities

- `xhs-credential-pool`：账号池文件模型、迁移、round-robin、冷却/禁用、控制台登录会话 API、keyword 绑定 `account_id`。

### Modified Capabilities

- `cookie-instance-admin`：xhs Worker 运行时从账号池 rebind，而非仅读 config 固定路径。
- `crawl-worker-pool`：xhs keyword 执行前换 profile + 重启 Chrome；与监测 busy 协调。
- `xhs-keyword-pipeline`：`stats_json` 记录 `account_id`；每 keyword 换号语义。
- `unified-web-console`：数据源 · xhs 账号池 UI（列表、添加、登录导 Cookie、禁用/冷却、诊断）。
- `admin-console-auth`：账号池写操作与登录会话 API 须管理员；路径仍限 `credentials/xhs/`。

## Impact

- **config.json**：可选 `monitor.xhs_credential_pool`（`min_accounts`、`login_cdp_port_base`）；`auth.xhs` 仍与 `acc-default` 对齐。
- **新增模块**：`intel/xhs_credentials.py`（池读写、pick、迁移、登录会话）
- **改动**：`intel/worker.py`、`intel/worker_pool.py`、`intel/keyword_pipeline.py`、`intel/cookie_instances.py`、`intel/api.py`、`auth_utils.py`、`crawler_web.py`（Chrome 启动辅助）
- **前端**：`static/app-sources.js`（xhs 账号区块）、可能 `panel-cookies.js` 只读提示跳转数据源
- **测试**：`scripts/test_xhs_credentials.py`；登录流程手动验证登记 `verification-pending.md`
