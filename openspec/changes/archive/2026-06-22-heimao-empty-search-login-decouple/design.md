## Context

当前 `heimao_wait_if_search_empty`（`login_gate.py`）逻辑：

```
有链接 → 继续
有 sid、无链接 → WARN，继续（可能无结果）
无 sid、无链接 → WAITING_LOGIN（打开微博扫码）
```

此外 `crawl_heimao` 在 `early_stop.protect_first_page` 下会对第 1 页空结果执行 `empty_page_retry`（默认 1 次，合计最多搜 3 次），同一合作方多关键词串行时用户感知为「反复搜同一企业」。

黑猫会话分两层：**微博 SUB** 与 **sid**。sid 常从搜索结果链接写入；关键词无投诉时 sid 可能从未出现，但 SUB 仍有效——旧逻辑误触发登录等待（task 100002 已复现）。

## Goals / Non-Goals

**Goals:**

- 空搜索时按 **明确鉴权信号** 决定是否 `WAITING_LOGIN`。
- 无 sid + SUB 有效 + 无登录墙 → **WARN 并跳过**，不打开扫码页。
- 有 sid + 无链接 → **确认无结果，立即跳过**。
- **任何空结果路径均不重试**（含 empty_page_retry、后缀再搜、轮末 deferred）；直接下一关键词/合作方。
- 可配置回滚至 `login_on_missing_sid=true` 旧登录判定。

**Non-Goals:**

- 修改小红书门禁逻辑。
- 跨 Run 持久化「曾跳过」关键词。
- 自动破解黑猫风控/Captcha。
- 后缀精简、deferred 队列、轮末重试（用户明确不要）。

## Decisions

### 1. 空搜索分类器 `heimao_classify_empty_search`

```
投诉链接 > 0     → has_results      → 继续爬取
有 sid、无链接   → no_results       → 日志 WARN，立即 skip
无 sid、鉴权 OK  → empty_uncertain  → 日志 WARN，立即 skip（不等登录）
无 SUB / 登录墙  → auth_required    → WAITING_LOGIN（仅此处可 redo_search）
HTML 过短/拦截   → blocked          → 同 auth_required
login_on_missing_sid=true 且无 sid → auth_required（兼容旧行为）
```

**skip** = `crawl_heimao` 返回空列表，adapter 循环进入下一 `kw` / 下一 `partner`。

### 2. `heimao_wait_if_search_empty` 行为

| 分类 | 行为 |
|------|------|
| `has_results` | 返回 True，继续 |
| `no_results` / `empty_uncertain` | WARN + 返回 True；**不** `wait_for_site_login`；**不** `redo_search` |
| `auth_required` / `blocked` | `wait_for_site_login`；成功后 **仅此处** 调用 `redo_search` |

RunMetrics：`heimao_skipped_empty` +1（含 no_results 与 empty_uncertain）。

### 3. 禁用黑猫空搜重试

| 机制 | 变更 |
|------|------|
| `early_stop.empty_page_retry` | 默认 `0`；第 1 页无新增链接即 `early_stop · empty_page`，**不** `_redo_heimao_search` |
| 后缀剥离再搜 | **移除**（不在本 change 实现） |
| deferred 轮末重试 | **移除** |
| `heimao_wait_if_search_empty` 后 `_redo_heimao_search` | 删除「空结果仍重搜一次」分支（`crawler_web.py` 约 452–455 行） |

**保留**：登录成功后 `redo_search`（auth 路径）；详情页 auth failure 后的 `wait_for_site_login`。

### 4. adapter 行为

`intel/sources/heimao.py` 保持 `for kw in keywords[:3]`，每个关键词调用 `crawl_heimao`：

- 返回 `[]` → 日志 `[heimao] 无结果，跳过: {kw}`，**立即**下一 kw。
- 不收集 deferred、不轮末重试。

### 5. 配置默认值

```json
"heimao": {
  "early_stop": {
    "empty_page_retry": 0
  },
  "empty_search": {
    "login_on_missing_sid": false
  }
}
```

### 6. 三条门禁路径

- **任务开始**：`fetch_detail=true` 仍走 `heimao_ready_for_detail_crawl`。
- **搜索空结果**：本变更；skip 不重试。
- **详情失败**：仍仅 `is_heimao_detail_auth_failure` → `wait_for_site_login`。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 真无结果 vs 加载失败难区分 | HTML 过短走 blocked/auth；运维可调大 `min_html_len` |
| 去掉重试后漏抓 | 企业全称无结果时接受跳过；别名由 `keywords[:3]` 覆盖 |
| 真登录失效无 wall 被 skip | 详情路径仍会触发 auth；可开 `login_on_missing_sid` |

## Migration Plan

1. 部署后 `empty_page_retry` 默认 0；旧 config 若显式设 `1` 仍尊重配置值。
2. 归档时 sync `heimao-login-gate` 与 `source-adapter` spec。

## Open Questions

（无）
