## ADDED Requirements

### Requirement: investigation 弹窗配额配置

系统 SHALL 在 `config.xhs.investigation_detail` 支持 `max_modal_per_run`（整数，0 表示不限制）；CrawlProfile API 白名单 MUST 包含该键。

#### Scenario: 默认与 profile 暴露

- **当** 未配置 `max_modal_per_run`
- **则** MUST 使用 `config.py` DEFAULT（建议 200 或 0=不限）
- **且** `GET /api/sources/xhs/profile` MUST 在 `investigation_detail` 对象中返回该键

#### Scenario: Worker 路径读取配额

- **当** xhs Worker 或 Orchestrator 执行 investigation
- **则** MUST 从 `config.xhs.investigation_detail.max_modal_per_run` 读取
- **且** 与现有 `dom_miss_skip`、`dom_miss_research_threshold` 等键共存

### Requirement: 配额与弹窗路径衔接

弹窗配额 MUST 在 `fetch_xhs_details_by_urls` / investigation Worker 路径生效；routine `crawl_xhs` MUST NOT 消耗配额。

#### Scenario: routine 不计入配额

- **当** xhs list_crawl routine 执行
- **则** MUST NOT 递增 `investigation_modal_done`

#### Scenario: 每条成功弹窗计 1

- **当** investigation 单 URL 弹窗提取成功
- **则** Run 级 `investigation_modal_done` MUST +1
- **且** 达到上限后后续 URL MUST skip（见 list-triage-investigation）

### Requirement: xhs Worker investigation 弹窗路径

系统 SHALL 在 investigation / `fetch_xhs_details_by_urls` 路径使用弹窗详情流程；禁止 goto explore 为主路径。investigation MUST 在 xhs Worker 进程内执行（Stage 3）。

#### Scenario: 勘察通过搜索页点击

- **当** xhs Worker 处理 investigation URL
- **则** MUST 在 search_result 页定位 note-item 并 `fetch_xhs_detail_via_modal`
- **且** MUST NOT goto explore 为主路径

#### Scenario: 单条 DOM 未找到跳过

- **当** dom_miss_skip 且定位失败
- **则** MUST skip 该 URL；queue 项 failed；**不计入** modal 配额成功计数

#### Scenario: 配额 skip 不弹窗

- **当** Run 级配额已用尽
- **则** MUST NOT 打开弹窗；直接 mark skipped
