## Why

监测任务 `ignore_before` 原先仅在 AI 分析阶段生效，列表仍会入库大量历史 raw，详情勘察也会消耗 CDP 配额。源数据/情报中心 Tab 固定请求 `page=1&page_size=100` 且按 id 倒序，用户看到「共 8989 条」却只显示最新 100 条，无法翻页。黑猫滚动采集缺少「暂无更多」见底标志，仅靠饱和早停可能多跑无效轮次。

## What Changes

- **ignore_before 全链路**：新增 `intel/ignore_before.py`；列表 `insert_raw_records` 入库前过滤；`build_investigation_queue` / `row_needs_investigation` 跳过；分析阶段沿用既有逻辑；`resolve_ignore_before` 合并 task 与 business_spec；run metrics 增加 `raw_skipped_ignore_before`。
- **控制台列表分页**：源数据 Tab、情报中心 Tab 增加分页控件（默认 20 条/页，可选 50/100/200）；API 默认 `page_size=20`、上限 200；URL query 持久化 `raw_page` / `intel_page`。
- **黑猫见底早停**：`config.heimao.early_stop.end_texts` 默认含 `暂无更多`；滚动后检测 end_marker 早停（与 xhs `- THE END -` 对称）。

## Capabilities

### Modified Capabilities

- `intel-pipeline`：ignore_before 扩展至列表入库与详情勘察；更新「不得跳过 insert raw」表述。
- `unified-web-console`：源数据/情报中心列表分页与计数展示。
- `source-adapter`：黑猫 end_marker 默认 `暂无更多`（配置与早停检测）。

## Impact

| 区域 | 影响 |
|------|------|
| `intel/ignore_before.py` | 新增共用过滤模块 |
| `intel/db.py` | `insert_raw_records(..., ignore_before=)` |
| `intel/investigation.py` | 勘察队列过滤 |
| `intel/runner.py` / `worker.py` / `keyword_pipeline.py` | 传入 ignore_before |
| `static/list-pagination.js` | 共用分页 UI |
| `panel-raw.js` / `panel-intel.js` | 分页状态与 API 参数 |
| `intel/api.py` | raw/intel 列表 page_size 默认与上限 |
| `config.py` / `crawl_early_stop.py` | heimao end_texts |
| `scripts/test_ignore_before_filter.py` | 单元测试 |

**非目标**：Run 详情 UI 展示 `raw_skipped_ignore_before`；任务详情内 raw/intel 子 Tab 仍最多 100 条（后续变更）。
