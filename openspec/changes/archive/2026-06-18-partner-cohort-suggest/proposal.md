## Why

录入合作方时 `industry_cohort` 为开放文本且无引导，易出现同一行业多种写法或留空，导致小红书 `list_first` 无法合并 keyword_batch（fallback 为 `partner:{id}` 逐品牌搜索）。用户希望录入时通过 LLM 结合联网检索推断候选 cohort，优先对齐已有 cohort，由用户点选确认；cohort 仍可为空。

## What Changes

- 新增 `POST /api/partners/suggest-cohort`（或 GET with query）：输入 `name`、可选 `aliases`，返回 cohort 候选列表（含来源、置信度、是否已有 cohort）。
- 后端：汇总 DB 已有 `industry_cohort`；LLM prompt 要求优先从已有 cohort 中选择或规范化到最近已有值；可选联网搜索补充品牌行业信息（配置开关）。
- UI：合作方表单增加「推荐 cohort」区域；用户点击候选项填入 `pCohort`；不自动覆盖已手填内容；保存时 cohort 仍可为空。
- 配置：`analysis.partner_cohort_suggest.*`（enabled、model、web_search_enabled、max_candidates）。
- 单元测试：已有 cohort 优先、空 name 拒绝、mock LLM 响应解析。

## Capabilities

### New Capabilities

（无独立新 capability；能力归入 partner-registry）

### Modified Capabilities

- `partner-registry`：新增 cohort 推荐 API 与 UI 交互；明确 cohort 开放标签、可为空、用户确认后写入。

## Impact

- **代码**：`intel/api.py`、新建 `intel/partner_cohort_suggest.py`（或 `intel/cohort_suggest.py`）、`static/panel-intel.js`、`templates/app.html`
- **配置**：`config.py` / `config.json.example` → `analysis.partner_cohort_suggest`
- **站点**：无 heimao/xhs 爬取变更；间接影响 shared-crawl-pool 合并质量
- **依赖**：现有 MiniMax（或 analysis provider）；联网搜索需可配置（如 search API 或 LLM 内置 browsing，实现阶段在 design 定稿）
