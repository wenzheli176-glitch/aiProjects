## 上下文

舆情爬虫通过 Chrome CDP + Playwright 控制小红书搜索与详情抓取。详情页在未登录时不可访问，但当前实现仅在任务开始时做一次宽松检测（`require_login` 默认 false），且检测通过时往往直接视为已登录。用户已选择：**方案 C（暂停等待登录后自动续跑）**；**不勾选详情时允许只抓列表**。

## 目标 / 非目标

**目标：**

- `fetch_detail=true` 时，任何时刻判定未登录则进入 `WAITING_LOGIN`，阻塞详情相关步骤直至登录成功或超时。
- 等待期间保持 Chrome 与 CDP 连接，用户可在同一浏览器窗口完成扫码/短信登录。
- 登录通过后自动从暂停点继续，无需重新提交爬取参数。
- `fetch_detail=false` 时不强制登录，列表抓取照常进行。
- 状态与日志对 Web UI 可见（等待中 / 已恢复 / 超时失败）。

**非目标：**

- 全自动短信/验证码登录（仍为人机完成登录）。
- 多账号轮换、代理池、反爬对抗策略升级。
- 黑猫与小红书共用 `login_gate.py` 等待续跑；两站 `fetch_detail` / `require_login` 语义一致。

## 决策

### 1. 任务状态机

在全局状态 `S` 上扩展：

```
RUNNING ──(xhs + 未登录 + fetch_detail)──▶ WAITING_LOGIN
WAITING_LOGIN ──(检测通过)──▶ RUNNING (续跑)
WAITING_LOGIN ──(超时)──▶ idle + 错误日志
```

- `running_type` 保持 `xhs`；新增 `login_wait` 或 `phase` 字段供 API 返回。
- 轮询在爬取线程内同步进行（与现有 `threading` 模型一致），间隔可配置（默认 3s），总超时可配置（默认 300s）。

**备选：** 独立登录守护线程 — 复杂度高，暂不采用。

### 2. 何时检测登录

| 时机 | fetch_detail=false | fetch_detail=true |
|------|-------------------|-------------------|
| 任务开始前 | 可选轻量检测，不阻塞 | **必须**检测，未通过 → WAITING_LOGIN |
| 每条详情打开前 | 跳过 | **必须**检测，未通过 → WAITING_LOGIN |
| 详情 JS 结果为空且页面含登录文案 | 跳过 | 视为未登录，进入 WAITING_LOGIN |

列表滚动阶段不强制登录。

### 3. 登录判定规则（小红书）

满足以下 **任一** 即视为已登录：

1. Context Cookie 中存在非空的 `web_session` 与 `webId`（名称可配置）。
2. 当前页无配置的 `login_fail_texts`（如「登录后查看」）。
3. （详情探针）在 explore 详情 URL 上，正文选择器能取到超过 N 字符的内容。

**备选：** 仅 Cookie — 可能漏检页面层登录墙；采用组合判定。

### 4. 等待登录时的用户动作

- 日志提示：「请在 Chrome 中完成小红书登录，完成后将自动继续」。
- 可选自动调用已有 `api/auth/open_login`（site=xhs）若当前页非登录页。
- **不** 在等待期间 `close_cdp(shutdown_browser=True)`，避免关闭已登录浏览器。
- 登录成功后可选自动 `export_cookies` 写入 `credentials/xhs_cookies.json`（可配置，默认 true）。

### 5. API / 前端

`/api/status` 增加字段示例：

```json
{
  "running": true,
  "running_type": "xhs",
  "phase": "waiting_login",
  "login_wait": {
    "site": "xhs",
    "elapsed_sec": 42,
    "timeout_sec": 300,
    "message": "等待小红书登录..."
  }
}
```

前端：状态栏橙色提示 + 禁用「开始」或显示「等待登录中」；保留「打开登录页」「登录诊断」按钮。

### 6. 与 `require_login` 配置的关系

- `fetch_detail=true` 时 **隐式强制** 登录等待，不依赖用户勾选 `require_login`。
- `require_login` 保留：当 `fetch_detail=false` 时若用户仍希望列表也登录后再抓，可设为 true（可选，默认 false）。

## 风险与权衡

| 风险 | 缓解 |
|------|------|
| 轮询阻塞爬取线程过久 | 可配置超时；用户可点「停止」 |
| 误判已登录导致详情仍空 | 详情探针 + 空结果二次检测 |
| 误判未登录长时间等待 | 组合判定；诊断 API 输出 Cookie 状态 |
| 用户关闭 Chrome | 检测 CDP 断开，失败并提示重启 Chrome |
| 登录后 Cookie 在 Profile 未导出 | 等待成功后自动 export；或 `use_profile_only` |

## 迁移计划

1. 合并代码后更新 `config.json` 默认：`auth.xhs.wait_timeout_sec`、`poll_interval_sec`、`required_cookie_names`。
2. 文档更新小红书等待登录步骤。
3. 无数据库迁移；向后兼容旧 API 字段（新增可选字段）。

## 待决问题

- 等待超时后：整任务失败 vs 降级为仅列表（当前倾向：**失败并明确日志**，与用户「详情必须登录」一致）。
- 是否在等待期间允许用户点击「导出 Cookie」而不中断等待循环（倾向：**允许**，与黑猫流程一致）。
