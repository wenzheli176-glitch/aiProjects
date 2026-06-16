## Why

源数据 `published_at` 多为原始文本、未规范为日期，且 AI 分析未接收发布时间，无法结合时效调整相关度；情报列表缺少情感维度筛选。运营需要按内容发布远近与模型自报置信度综合判断风险，并在看板按情感 label/score 过滤。

## What Changes

- 采集与 Normalize：将 `time` 规范为 `YYYY-MM-DD`（日期精度即可）；XHS 相对时间以 `captured_at` 反推；详情时间优先覆盖列表时间
- AI 分析：LLM 输入增加 `published_at`、`captured_at`；输出增加 `confidence`（0~1 自报）
- 后处理降档：在 LLM `relevance` 基础上按发布距今天数确定性降档（阈值 30/90 天）；无 `published_at` 时**仍允许 high**，不因缺日期强制降档
- 存储：`intel_records` 新增 `confidence`；可选保留 LLM 原始档位于 `extra`
- 配置：`config.analysis.recency`（降档阈值、是否启用后处理）
- 情报 API/UI：新增 `sentiment_label`、`sentiment_score_min`、`sentiment_score_max` 筛选；监测任务继续用现有 `fTask`/`task_id`
- 导出：透传情感筛选参数

## Capabilities

### New Capabilities

（无独立新 capability；行为归入既有 intel/source 规范）

### Modified Capabilities

- `source-adapter`: Normalize 输出 `published_at` 必须为日期级 ISO（`YYYY-MM-DD`）或空；相对时间解析规则
- `intel-pipeline`: Analyze 输入/输出扩展 `confidence`；recency 后处理降档 relevance；`published_at` 传入 LLM
- `risk-dashboard-export-api`: 情报列表 API 支持情感 label + score 区间筛选；导出透传

## Impact

| 区域 | 文件/模块 |
|------|-----------|
| 日期解析 | 新 `intel/date_parse.py` 或 `normalize_utils`；`reports.py`；`intel/normalizers/*` |
| 分析 | `intel/analyze.py`；`intel/prompts` / 默认 system prompt；`config.py` `analysis.recency` |
| DB | `intel/db.py` migration `confidence` 列 |
| API | `intel/api.py`；`intel/db.py` `list_intel_records` |
| UI | `templates/app.html`；`static/panel-intel.js`；`field_labels.py` |
| 导出 | `intel/export_intel.py` |
| 配置示例 | `config.json.example` |

**config 变更：**

- `analysis.recency.enabled`（默认 true）
- `analysis.recency.downgrade_days_high_to_medium`（默认 30）
- `analysis.recency.downgrade_days_medium_to_low`（默认 90）
- `analysis.recency.confidence_downgrade_threshold`（默认 0.4，低于则 relevance 降一档）
