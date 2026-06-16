## Why

日常调试爬取（`/api/crawl_heimao`、`/api/crawl_xhs`）及监测列表阶段在配置 `max_pages=M` 时，站点往往在第 2～3 页已无新结果，但爬虫仍跑满 M 页/轮，浪费 Chrome 时间与等待间隔。黑猫仅有部分早停（第 2 页起零新增），小红书无早停；用户期望在**分页见底**时及时停止，且第 1 页零结果需防加载失败误判。

## What Changes

- 为 **heimao**、**xhs** 分别新增可配置的 `early_stop` 策略块（含 `enabled` 总开关）。
- **黑猫**：连续 N 页无新链接（URL 分页见底）时提前结束；第 1 页零结果时先重试/等待，不因单次加载失败早停。
- **小红书**：滚动后检测页底 `- THE END -` 文案（主信号）；辅以滚动饱和（连续多轮零新增且 note-item 总数不增）兜底；仍使用「XHS第 i/M 页」日志语义。
- 早停时输出结构化日志（`early_stop: <source> · reason=… · stopped_at=i/M`）；`max_pages` 明确为**上限**，实际页数可小于 M。
- 配置暴露至 `config.json.example`、`field_labels` 与数据源 CrawlProfile（白名单键）；默认 `enabled: true`（调试友好，可关回跑满 M 页）。
- **不**改变 MonitorRunner 增量逻辑、不引入 DB 水位早停。

## Capabilities

### New Capabilities

- （无）本变更扩展现有爬虫与源适配行为，不新增顶层 capability。

### Modified Capabilities

- `source-adapter`：`max_pages` 补充为采集上限；各源 `early_stop` 配置与见底早停行为；xhs 滚动饱和与 `- THE END -` 检测要求。

## Impact

**站点与模块**

| 区域 | 影响 |
|------|------|
| heimao | `crawl_heimao` 分页循环早停与第 1 页保护 |
| xhs | `crawl_xhs` 滚动循环：end 标志 + 饱和检测 + 第 1 页保护 |
| login_gate | 无变更（复用既有 `heimao_wait_if_search_empty` / `xhs_wait_if_search_blocked` 防误判） |
| 共用 | `crawler_web.py`、`config.py`；legacy 与 `list_first` 的 `crawl_list_batch` 均受益 |

**config.json 字段**

| 字段 | 变更 |
|------|------|
| `heimao.early_stop.*` | 新增：`enabled`、`min_pages`、`empty_pages_threshold`、`protect_first_page`、`empty_page_retry` |
| `xhs.early_stop.*` | 新增：`enabled`、`min_pages`、`protect_first_page`、`end_texts`（含 `- THE END -`）、`end_selectors`、`saturation_rounds` |

**API / UI**

- 无 REST 行为变更；数据源 profile PATCH 白名单增加 `early_stop` 子键（若经 profile 暴露）

**非目标**

- 监测任务相对 DB 的「增量无新变化」早停（二期）
- 修改 `max_pages` 字段名或 per-source 独立页数
- 改变 investigation / 详情爬取策略
