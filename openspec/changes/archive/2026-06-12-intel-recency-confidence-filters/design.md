## Context

- `published_at` 已从 raw `time` 映射，但多为非 ISO 文本；XHS 列表常为相对时间
- `intel/analyze.py` 的 LLM 批次仅含 id/source/title/body，不含发布时间
- 输出含 relevance/sentiment，无 confidence；无 recency 后处理
- `list_intel_records` 支持 task_id/partner/source/relevance_min，**无** sentiment 筛选
- UI 已有 `fTask`、情感列展示，缺情感筛选项

## Goals / Non-Goals

**Goals:**

- 统一 `published_at` 为 `YYYY-MM-DD` 或空；详情时间覆盖列表时间
- LLM 自报 `confidence`（0~1），输入含 `published_at`/`captured_at`
- 后处理按 age 降档 relevance：>30 天 high→medium，>90 天 medium→low；confidence<0.4 再降一档
- **无 published_at 时不因缺日期降档**，仍允许 LLM 标 high
- API/UI 支持 `sentiment_label` + `sentiment_score_min/max`；task 筛选用现有 fTask

**Non-Goals:**

- 时分秒精度、时区转换
- 新增 composite weighted_score 字段（业务外置原则不变）
- 修改 fTask UI 结构
- 对历史 intel 批量重算（可选手动 reanalyze）

## Decisions

### 1. 日期解析模块 `intel/date_parse.py`

**选择**：独立 `parse_published_date(text, anchor_date) -> (YYYY-MM-DD|'', quality)`。

- 绝对日期：regex + `datetime.strptime` 取日
- 相对中文：`N天前`、`昨天`、`今天`、`N小时前`（按 anchor 反推到日）
- 失败返回 `''`，quality=`missing|relative|absolute`

Normalizers 与 `reports.py` 共用；detail payload 的 `time` 优先于 list。

### 2. LLM 扩展

**输入**（每条）：

```json
{"id", "source", "title", "body", "published_at", "captured_at"}
```

**输出**（每条）：

```json
{"id", "relevance", "confidence", "risk_types", "summary", "subject_hits", "sentiment", "sentiment_score"}
```

Prompt 说明：confidence 综合主体命中、信息完整度、时效匹配；旧文风险需结合 published_at 判断。

**存储**：`intel_records.confidence REAL`；`extra.relevance_llm` 保留 LLM 原始档位（后处理前）。

### 3. Recency 后处理 `apply_recency_relevance(raw_rel, confidence, published_at, captured_at, cfg)`

顺序（可配置 `analysis.recency.enabled`）：

1. 从 `published_at` 算 `age_days`（相对 `captured_at` 或 UTC today）；无日期 → **跳过 age 降档**
2. `age_days > 30` 且 `relevance=high` → `medium`
3. `age_days > 90` 且 `relevance=medium` → `low`
4. `confidence < 0.4` 且 `relevance != noise` → 降一档（high→medium→low→low）

最终写入 `relevance`；`confidence` 存 LLM 原值（clamp 0~1）。

### 4. 情感筛选 API

| 参数 | 行为 |
|------|------|
| `sentiment_label` | 精确匹配 positive/neutral/negative |
| `sentiment_score_min` | `sentiment_score >= min` |
| `sentiment_score_max` | `sentiment_score <= max` |
| 组合 | AND |

### 5. 配置 `analysis.recency`

```json
"recency": {
  "enabled": true,
  "downgrade_days_high_to_medium": 30,
  "downgrade_days_medium_to_low": 90,
  "confidence_downgrade_threshold": 0.4
}
```

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| XHS 相对时间解析偏差 | anchor 用 captured_at；quality 写入 extra |
| LLM confidence 不稳定 | 后处理降档兜底；保留 relevance_llm |
| 降档后 high 变少 | 阈值可配置；文档说明 reanalyze 刷新 |
| 历史 intel 无 confidence | 列 nullable；旧记录筛选时 score 可能为 null |

## Migration Plan

1. 部署 DB migration 添加 `confidence` 列
2. 新分析自动写入；旧记录不变
3. 需刷新时用户对 task 执行 reanalyze

## Open Questions

- （已关闭）降档阈值 30/90；无日期允许 high
- （已关闭）单 change 全做
