## Why

黑猫搜索「无投诉链接 + 读不到 sid」时，`heimao_wait_if_search_empty` 会直接进入 `WAITING_LOGIN` 并打开微博扫码页。监测任务里同一合作方连续空搜后切换下一企业时，用户常看到「需要重新登录」，但浏览器 SUB 仍有效——实为 **空结果与 sid 未建立** 被误判为 **会话失效**。这阻塞 Worker 队列、诱发不必要的人工扫码，且与「关键词确无投诉」的正常业务场景无法区分。

## What Changes

- **解耦判定**：搜索空结果时，仅当存在 **明确登录失效信号**（无微博 SUB、页面登录墙/失败文案、详情探测失败等）才进入 `WAITING_LOGIN`；**不得**仅因「无 sid + 无链接」触发登录等待。
- **空结果直接跳过**：一旦判定为无投诉链接（含「有 sid 确认无结果」与「无 sid 但 SUB 仍有效」两类），**立即结束当前关键词**，不阻塞、不重试，继续下一关键词或下一合作方。
- **黑猫不重试**：取消/禁用与本变更相关的各类空搜重试——含 `early_stop.empty_page_retry` 默认改为 0、不做后缀精简再搜、不做 deferred 轮末重试、空结果不调用 `_redo_heimao_search`（**仅**登录成功后的 `redo_search` 保留）。
- **配置化**：`config.heimao.empty_search.login_on_missing_sid` 保留以便回滚旧登录判定；`heimao.early_stop.empty_page_retry` 默认改为 `0`。
- **BREAKING**：默认关闭「无 sid 即等登录」；黑猫空搜不再重试，直接跳过。

## Capabilities

### New Capabilities

（无新增 capability 目录；行为归入既有 heimao 门禁与源适配。）

### Modified Capabilities

- `heimao-login-gate`：重写「搜索无结果时触发登录等待」；新增「空结果直接跳过、不重试」。
- `source-adapter`：heimao routine crawl 空结果立即进入下一关键词/合作方；调整 early_stop 空页重试默认值。

## Impact

- **站点**：heimao（`login_gate.py`、`heimao_session.py`、`crawler_web.crawl_heimao`）；xhs 不受影响。
- **配置**：
  - 新增 `heimao.empty_search.login_on_missing_sid`（默认 `false`）
  - 修改 `heimao.early_stop.empty_page_retry` 默认 `1` → `0`
- **编排**：`intel/sources/heimao.py`、Worker routine 路径；RunMetrics 增加 `heimao_skipped_empty` 计数（替代 deferred 计数）。
- **文档**：`代码说明.md`、字段标签；手动验证项。
