## Context

- `industry_cohort` 为开放字符串，精确匹配合并（`intel/keyword_batch.py`）。
- 合作方表单：`pCohort` 纯 input（`panel-intel.js`），POST/PUT 允许空字符串。
- 已有 LLM 基础设施：`intel/analyze.py`、list_triage 同类调用模式。
- 用户决策：**开放标签**、**LLM+联网推断候选**、**优先已有 cohort**、**用户点选确认**、**新建允许 cohort 为空**。

## Goals / Non-Goals

**Goals:**

- 录入/编辑合作方时，根据 name（+ aliases）生成 3–5 个 cohort 候选。
- 候选排序：已有 DB cohort 优先 → LLM 归一化到已有 cohort → 新开放标签（标注「新建」）。
- UI 仅点选填入，不自动保存；cohort 空仍可 POST 创建 partner。
- API 可被 UI 与业务系统批量导入前置调用。

**Non-Goals:**

- cohort 受控枚举或审批流。
- 自动写入 cohort（无用户点选）。
- 顺带推荐 aliases/monitor_keywords（可后续扩展）。
- 修改 keyword_batch 合并规则。

## Decisions

### D1：API 形态

```
POST /api/partners/suggest-cohort
Body: { "name": "蔚来汽车", "aliases": ["NIO"], "exclude_partner_id": 3 }
Response: {
  "ok": true,
  "candidates": [
    { "cohort": "新能源汽车", "source": "existing", "partner_count": 2, "confidence": 0.95 },
    { "cohort": "新能源整车", "source": "llm", "confidence": 0.7, "is_new": true }
  ],
  "existing_cohorts": ["新能源汽车", "传统乘用车"]
}
```

- `exclude_partner_id`：编辑时排除自身，避免「已有 1 个」计数误导。
- 无 admin 要求（读推荐）；与 partners 列表同级只读。

### D2：已有 cohort 优先（归一化）

1. `list_distinct_cohorts()`：`SELECT industry_cohort, COUNT(*) FROM partners WHERE cohort != '' GROUP BY cohort`
2. LLM system prompt 注入已有 cohort 列表；要求 **优先 verbatim 选用已有值**；若推断行业接近已有 cohort，必须输出已有字符串而非新造近义词。
3. 后处理：对 LLM 输出做 fuzzy match（包含关系 / 编辑距离阈值）映射到已有 cohort；无法映射则标记 `is_new: true`。

### D3：LLM + 联网搜索

配置 `analysis.partner_cohort_suggest.web_search_enabled`（默认 true 若实现可行）。

**实现选项（tasks 阶段择一）：**

| 选项 | 做法 |
|------|------|
| A | 调用可联网的 LLM（若 provider 支持 web/search tool） |
| B | 先 DuckDuckGo/Bing 搜 `{name} 行业`，摘要拼入 user prompt |
| C | 仅 LLM 内部知识（无联网），`web_search_enabled=false` fallback |

Design 倾向 **B + C fallback**：不绑定单一 vendor；无网络时降级为 LLM-only。

Prompt 输出 JSON：

```json
{ "candidates": ["新能源汽车", "汽车"], "reason": "..." }
```

### D4：UI 交互

```
┌─ 行业 cohort ─────────────────────────────┐
│ [________________________]  (开放输入)     │
│ [🔍 获取推荐]                              │
│ 推荐（点击填入）：                           │
│  · 新能源汽车  ✓已有·2家                     │
│  · 新能源整车  新建                          │
└──────────────────────────────────────────┘
```

- 点击 chip → 写入 input，**不**自动提交表单。
- 已手填 cohort 时仍可点「获取推荐」展示，但不覆盖 input 除非用户再点 chip。
- 新建/编辑均可用；cohort 留空保存 → 合法。

### D5：配置

```json
"analysis": {
  "partner_cohort_suggest": {
    "enabled": true,
    "model": "",
    "max_candidates": 5,
    "web_search_enabled": true,
    "web_search_max_results": 3,
    "mock_without_key": true
  }
}
```

- `model` 空则 fallback `analysis.model`。
- `mock_without_key` 与 analyze 一致，便于离线测试。

## Risks / Trade-offs

- **[Risk] LLM 幻觉行业** → 用户必须点选确认；展示 reason 可选。
- **[Risk] 联网搜索不稳定** → fallback LLM-only；超时返回仅 existing_cohorts。
- **[Risk] cohort 同义仍分裂** → 归一化 + prompt 强调 verbatim；长期可加「合并 cohort」管理页（非本 change）。

## Migration Plan

1. 部署 API + UI；默认 enabled。
2. 无 DB 迁移；空库时 candidates 仅 LLM + is_new。
3. 回滚：配置 `enabled=false` 隐藏 UI 按钮。

## Open Questions

- 联网搜索具体 provider（Bing API key vs 免费 HTML 抓取）在实现 tasks 中选定。
- 是否在 chip 上显示 LLM `reason` tooltip（可选 P2）。
