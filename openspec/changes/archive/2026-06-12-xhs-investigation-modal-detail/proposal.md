## Why

Stage2 `list_first` 监测任务的 xhs 勘察阶段当前通过 `fetch_xhs_details_by_urls` 对队列 URL 执行 `page.goto(/explore/...)`，与 `xhs-detail-modal` / `source-adapter` spec 要求的弹窗路径不一致，导致 App 墙拦截、无有效正文、易触发风控。手工 `crawl_xhs` 已正确使用弹窗，勘察路径需对齐并补齐「仅有 URL、无 DOM item」时的定位与重试策略。

## What Changes

- 重写 `fetch_xhs_details_by_urls`（及 `XhsCrawlAdapter.crawl_investigation`）：**禁止 goto 笔记 URL**，改为在 `search_result` 页定位 `.note-item` 后调用 `fetch_xhs_detail_via_modal`。
- 新增 URL→DOM 定位：`find_note_item_for_url`；按 raw 的 `_search_keyword` / 队列 keyword 分组打开搜索页。
- **单条 DOM 找不到**：跳过该 URL，标记 investigation 队列项 `failed`（原因 `dom_not_found`），不阻塞整批。
- **批量 DOM 找不到**：同一 keyword 批次内连续/累计未找到达阈值时，**重新搜索**（`goto search_result` + 滚动加载）后再试一轮；仍失败则按单条跳过。
- 勘察与手工爬取共用 `xhs_detail.py` 弹窗提取、关闭、App 墙检测与 `login_gate` 门禁。
- 新增 `config.xhs.investigation_detail.*` 配置（重搜阈值、滚动次数、批次间隔等）。

## Capabilities

### New Capabilities

- （无）本变更落实既有 spec，不新增顶层 capability。

### Modified Capabilities

- `xhs-detail-modal`：勘察阶段也必须走弹窗；URL 定位与重搜行为。
- `source-adapter`：xhs `crawl_investigation` 实现与 spec 对齐（移除 goto 主路径）。
- `list-triage-investigation`：勘察失败语义（单条 skip、批量重搜、investigation 状态）。

## Impact

**站点与模块**

| 区域 | 影响 |
|------|------|
| xhs | `xhs_detail.py` 扩展 URL 定位；`crawler_web.fetch_xhs_details_by_urls` 重写 |
| heimao | 无变更（勘察仍 new_page 详情） |
| login_gate | 复用 xhs 登录门禁，无新门禁路径 |
| intel | `intel/sources/xhs.py`、`intel/investigation.py` 错误原因与 metrics |

**config.json 字段**

| 字段 | 变更 |
|------|------|
| `xhs.investigation_detail.dom_miss_skip` | 新增，单条找不到 DOM 是否跳过（默认 true） |
| `xhs.investigation_detail.dom_miss_research_threshold` | 新增，触发重搜的连续/累计未找到次数（默认 3） |
| `xhs.investigation_detail.research_max_scroll_rounds` | 新增，重搜后额外滚动轮数 |
| `xhs.investigation_detail.between_detail_min/max` | 新增，勘察弹窗间隔（秒，可复用 detail_wait 默认） |

**API / UI**

- 无 REST 结构变更；Run stats 可含 `investigation_dom_miss`、`investigation_research` 计数（可选）

**非目标**

- 不改变 list_crawl / list_triage 逻辑
- 不引入 goto explore 作为 fallback 主路径
- 不改黑猫 investigation
