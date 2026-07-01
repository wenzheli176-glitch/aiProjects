## Why

监测任务配置 `max_pages=1000` 时，黑猫实际只采集约 60 条且无可见翻页。根因包括：（1）`intel/sources/heimao.py` 硬编码 `keywords[:3]` 限制每合作方仅 3 个关键词；（2）实现误用 URL 分页 / 点击「下一页」，而黑猫搜索页实际为**下拉滚动加载**更多结果；（3）错误的分页导致第 2 轮 DOM 与第 1 轮重复，触发早停。

## What Changes

- **黑猫列表加载**：`crawl_heimao` 改为与 xhs 一致的滚动采集轮次；新增 `heimao_scroll.py`，每轮滚动 `scroll_times_per_page` 次后解析 DOM 链接。
- **配置**：`config.heimao` 新增 `scroll_times_per_page`、`scroll_pixels`、`scroll_wait_seconds`、`scroll_to_bottom`、`scroll_container_selector`；`early_stop` 增加 `saturation_rounds`，移除对 URL 分页的 `empty_pages_threshold` 依赖。
- **早停**：第 1 轮零新增 → `empty_page`；连续多轮滚动饱和（无新链接且 DOM 链接数不增）→ `scroll_saturated`。
- **关键词上限**：移除 `keywords[:3]`；新增 `max_keywords_per_partner`（0=不限）。
- **删除** `heimao_pagination.py`（翻页方案）。

## Capabilities

### Modified Capabilities

- `source-adapter`：heimao `max_pages` 语义与 xhs 对齐为滚动采集轮次；CrawlProfile 暴露 scroll 参数；heimao early_stop 键更新。

## Impact

| 区域 | 影响 |
|------|------|
| `crawler_web.crawl_heimao` | 滚动加载替代 URL 翻页 |
| `heimao_scroll.py` | 新增 |
| `intel/sources/heimao.py` | 全量关键词 + 日志 |
| `crawl_early_stop.py` | heimao 饱和早停 |
| `config.py` / `config.json.example` | scroll 与 early_stop 默认值 |
| `source_profiles.py` | heimao profile 白名单 |

**非目标**：黑猫 API 签名分页；监测 UI 黑猫 scroll 表单项（可经 profile API 配置）。
