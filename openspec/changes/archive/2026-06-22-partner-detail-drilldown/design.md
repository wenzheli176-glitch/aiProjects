## Context

统一 Web 壳已有模式：

| Tab | 列表视图 | 详情视图 | Query |
|-----|---------|---------|-------|
| 情报 | `intelListView` | `intelDetailView` | `intel_id` |
| 源数据 | `rawListView` | `rawDetailView` | `raw_id` |
| 合作方 | 仅列表 | **无** | — |

`App.navigateIntel` / `App.navigateRaw` 已支持 `partner_id` 筛选，但用户明确要求：**两个独立按钮** + **源数据必须带 task_id** + **详情页内子 Tab**，而非仅跳主 Tab。

合作方与任务多对多：`monitor_task_partners`。源数据 `raw_records` 强依赖 `task_id`；同一合作方可出现在多个监测任务中。

## Goals / Non-Goals

**Goals:**

- 列表行「查看情报」「查看源数据」一键进入合作方详情页对应子 Tab。
- 源数据子 Tab 默认选中**最近更新的关联监测任务**（见决策 1）。
- 详情页内嵌情报/源数据列表（复用 API，不重复业务逻辑）。
- URL 可分享、刷新不丢上下文；返回列表保留 `partner_id` 清除。

**Non-Goals:**

- 不在合作方详情内编辑 CRUD（仍用 Modal）。
- 不新建独立 `/partners/{id}` 页面路由。
- 不在此 change 做 Run 历史/统计图表（可后续扩展「概览」Tab）。

## Decisions

### 1. 默认 task_id 解析

```sql
SELECT t.id, t.name, t.updated_at
FROM monitor_tasks t
INNER JOIN monitor_task_partners mtp ON mtp.task_id = t.id
WHERE mtp.partner_id = ?
ORDER BY t.updated_at DESC, t.id DESC
```

- 取第一条作为 `default_task_id`。
- 若无关联任务：`default_task_id=null`，源数据 Tab 显示空态 + 链接到监测任务 Tab。
- 详情内提供 **任务下拉**（仅列出含该 partner 的任务），切换时更新 query `task_id` 并刷新 raw 列表。

### 2. 详情页结构

```
panel-partners
├── partnerListView（现有表格 + 新按钮）
└── partnerDetailView
    ├── 顶栏：← 返回 | 合作方名称 | cohort/tier tag
    ├── 子 Tab：[情报] [源数据]
    ├── partnerIntelPane  → GET /api/intel/records?partner_id=&relevance_min=medium
    └── partnerRawPane    → GET /api/raw/records?partner_id=&task_id=
```

点击列表「查看情报」→ `partner_tab=intel`；「查看源数据」→ `partner_tab=raw` + `task_id=default`。

### 3. 导航 API（前端）

```javascript
App.navigatePartnerDetail(partnerId, { partner_tab: 'intel'|'raw', task_id?: number })
// sets ?tab=partners&partner_id=&partner_tab=&task_id=
```

列表按钮：

```javascript
onclick="navigatePartnerIntel(7)"
onclick="navigatePartnerRaw(7)"  // 先 GET context 取 default_task_id，或 inline 从 partners 缓存
```

实现时可在 `loadPartners` 后批量 lazy-fetch context，或按钮点击时 fetch `/api/partners/{id}/context`。

### 4. 后端 `GET /api/partners/{id}/context`

响应示例：

```json
{
  "ok": true,
  "partner_id": 7,
  "default_task_id": 100001,
  "tasks": [{"id": 100001, "name": "...", "updated_at": "..."}],
  "counts": {"intel_total": 12, "intel_medium_plus": 5, "raw_total": 340}
}
```

`counts` 按 `default_task_id` 统计 raw；intel 按 partner_id 全任务合计（或分 task——首版按 partner 全量 intel，raw 按所选 task）。

**首版约定：**

- `intel` 计数 / 列表：`partner_id` 全库（与情报中心「选合作方不选任务」一致）。
- `raw` 计数 / 列表：**必须** `partner_id` + `task_id`（当前选中任务）。

### 5. 与全局情报/源数据 Tab 的关系

详情内列表行点击「详情」时：

- intel 行 → `?tab=intel&intel_id=`（现有）
- raw 行 → `?tab=raw&raw_id=`（现有）

从 intel/raw 详情返回时，若 query 含 `from=partner&partner_id=` 可选回跳合作方详情（**Non-Goal 首版**；tasks 仅留 hook）。

### 6. 样式

复用 `intelListView` / `rawListView` 表格与 filter-bar 类；子 Tab 用现有 `.tab-bar` 或新增 `.partner-subtabs`。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 多任务选错 default | 详情内任务下拉 + 显示 task 名称 |
| shared_pool raw 的 partner_id 为空 | 空列表 + 说明「list 阶段可能未绑定 partner」 |
| 操作列过宽 | `col-actions` + 按钮 `btn-sm`，必要时缩短为「情报」「源数据」 |

## Migration Plan

纯增量 UI/API，无 DB migration。部署后合作方 Tab 即可用。

## Open Questions

（无——用户已确认：两按钮、源数据带 task_id、详情子 Tab。）
