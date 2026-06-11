## Context

当前 `app.html` + `static/app.css` 为深色主题；合作方/监测任务用 `.split` + 右侧 `form-box`；监测看板用 `.grid` 左栏筛选；Run 详情用 `#runDetailPanel` 占右栏。`list_raw_records()` 存在于 `intel/db.py` 但无 REST。情报已有 `GET /api/intel/records` 与 export。

用户已锁定决策：

| 项 | 决定 |
|----|------|
| 默认 Tab | home 首页看板 |
| 看板钻取 | 点击区域 → 情报列表（带 filter query） |
| 情报/raw 详情 | **独立详情页**（query：`intel_id` / `raw_id`） |
| Run 详情 | **Drawer** |
| 表单 | Modal |
| 导出 | **当前筛选条件全量**（非当前页） |
| 主题 | 一次性全站浅色 |

## Goals / Non-Goals

**Goals:**

- 统一交互：List（摘要）→ Detail Page（intel/raw）或 Drawer（Run）或 Modal（表单）
- 浅色科技感视觉：CSS variables、卡片阴影、accent 蓝青
- 自适应：Nav 折叠、表格横向 scroll、Modal 全屏小屏
- 首页 summary + 钻取；raw Tab + API + 导出
- 替换主要 `alert()`/`confirm()` 为 UI 组件

**Non-Goals:**

- Dark/light 主题切换
- 引入 React/Vue 或前端路由框架
- 图表库（首页先用数字卡片 + 简单表格）
- 修改爬取/login_gate/xhs 弹窗详情逻辑
- raw/intel 详情页打印/PDF

## Decisions

### D1 路由与 Tab 状态（query 驱动）

沿用 `App.switchAppTab(tab)` + `URLSearchParams`：

| Tab | 列表 | 详情 |
|-----|------|------|
| home | `?tab=home` | — |
| intel | `?tab=intel&task_id=&source=&relevance_min=` | `?tab=intel&intel_id=123`（隐藏列表，显示详情视图） |
| raw | `?tab=raw&…filters` | `?tab=raw&raw_id=456` |
| tasks | `?tab=tasks` | `?run_id=789` 打开 Run Drawer（可选深链） |

**返回列表**：详情页「返回」移除 `intel_id`/`raw_id`，保留其余 filter query（或 `sessionStorage` backup）。

`/dashboard` redirect → `/?tab=home`。

### D2 UI 组件层（`static/ui-shell.js`）

```javascript
UiModal.open({ title, bodyHtml, footerButtons, onConfirm })
UiDrawer.open({ title, bodyHtml, width: '480px'|'720px', onClose })
UiToast.show(msg, type)
UiConfirm.ask(message) → Promise<boolean>
```

- Modal：合作方/任务 创建编辑；危险操作确认
- Drawer：Run 详情（宽 720px）；可选 AI 日志批次详情
-  backdrop + ESC 关闭 + focus trap（MVP：ESC + 点击遮罩）

### D3 浅色 Design Tokens

```css
:root {
  --bg: #f1f5f9;
  --surface: #ffffff;
  --surface-muted: #f8fafc;
  --border: #e2e8f0;
  --text: #0f172a;
  --text-muted: #64748b;
  --accent: #0284c7;
  --accent-hover: #0369a1;
  --accent-soft: #e0f2fe;
  --success: #059669;
  --warning: #d97706;
  --danger: #dc2626;
  --shadow-sm: 0 1px 2px rgba(15,23,42,.06);
  --shadow-md: 0 4px 12px rgba(15,23,42,.08);
  --radius: 10px;
}
```

Header：浅渐变 + 细 border；`.card` 白底 + shadow-sm；表格 sticky header；tag 色系适配浅底。

**迁移策略**：先 token 化 `app.css`，再逐 Tab 删 inline `style="color:#cbd5e1"`。

### D4 首页看板

`GET /api/dashboard/summary` 返回：

```json
{
  "intel_total": 0,
  "intel_medium_plus": 0,
  "intel_today": 0,
  "by_source": { "heimao": 0, "xhs": 0 },
  "by_relevance": { "high": 0, "medium": 0, "low": 0 },
  "tasks_running": 0,
  "tasks_failed_recent": 0,
  "recent_runs": [ /* 最近 5 条摘要 */ ]
}
```

卡片点击示例：

- medium+ 计数 → `/?tab=intel&relevance_min=medium`
- heimao 计数 → `/?tab=intel&source=heimao`
- 最近 Run → `/?tab=tasks&run_id=`

### D5 情报看板布局

```
┌─────────────────────────────────────────────┐
│ FilterBar: 任务 | 合作方 | 来源 | 相关度 | 刷新 | 导出 │
├─────────────────────────────────────────────┤
│ IntelTable（摘要列）→ 行点击 / 详情 → intel_id   │
└─────────────────────────────────────────────┘
```

详情页：元数据 + 正文 + 链接 + 「查看源数据 raw_id」跳转。

### D6 源数据 Tab + API

**列表列**（无 payload 全文）：id、任务、合作方、来源、keyword、标题摘要、created_at、updated_at、分析状态、操作。

**详情页**：dedup_key、content_hash、结构化 payload（复用 `structure_heimao_record` / xhs 格式化）。

**API：**

- `GET /api/raw/records?task_id&partner_id&source&since&page&page_size`
- `GET /api/raw/records/{id}`
- `GET /api/raw/export?format=json|csv|xlsx&…同列表 filter…` — **忽略 page，导出全部匹配行**

`intel/db.py` 新增 `list_raw_records_paged()`；export 模块 `export_raw_records()`。

### D7 Run 历史 Drawer

- 移除 `#runDetailPanel` / 任务 split 右栏详情
- 点击 Run 摘要行 → `UiDrawer` 填充现有 Run 详情块
- stats 网格：**数字 + label + 一行 help 常显**（registry `monitor_run`）
- `?run_id=` 深链：进入 tasks Tab 后自动 open Drawer

### D8 Modal 表单

合作方、监测任务：

- 列表页 toolbar：「添加」「刷新」
- 编辑/添加 → Modal 内嵌原表单字段
- 保存成功 → close Modal + refresh 列表

SchedulePicker 在 Modal 内正常工作。

### D9 数据源 Tab 切换

`panel-sources`：顶栏 Tab `heimao` | `xhs`（+ 未来源）；仅渲染当前源 card 字段；保存仍 `PATCH /api/sources/{id}`。

### D10 导出语义（全站一致）

列表与 export 共用 filter 参数；export **不得**仅导出 `page` 内 rows。UI 按钮文案：「导出当前筛选结果」。

## Implementation Phases

| Phase | 内容 |
|-------|------|
| P0 | `ui-shell.js` + 浅色 tokens + 全局样式迁移基础 |
| P1 | home Tab + summary API + 钻取 |
| P2 | intel FilterBar 上移 + 详情页 + export 文案/语义确认 |
| P3 | raw API + Tab + 列表/详情/导出 |
| P4 | partners/tasks Modal + 全宽列表 |
| P5 | Run Drawer + 移除 runDetailPanel + stats inline |
| P6 | sources Tab + 全站 alert 排查 + responsive 回归 |

## Risks / Trade-offs

- **[Risk] 大 CSS diff 回归** → 分 Phase 合并；每 Phase 手动验证主要 Tab
- **[Risk] query 状态与浏览器后退** → 统一 `App.readQuery()` / `pushState` 可选 MVP 仅 location.search
- **[Risk] raw 全量 export 大数据** → 与 intel 相同，内网场景可接受；文档注明大 task 可能慢
- **[Trade-off] 详情页非独立 URL path** → 用 query 深链，足够内网分享

## Migration Plan

1. 部署静态 + API；Flask 重启
2. 用户 Ctrl+F5；旧书签 `/dashboard` 仍可用（redirect home）
3. 回滚：恢复 app.html/app.css/panel 文件

## Open Questions

（无 — 用户已确认详情页、全量导出、Drawer/Modal/浅色/default home）
