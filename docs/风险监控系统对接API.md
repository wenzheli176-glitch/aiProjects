# 风险监控系统对接 API

面向外部**风险监控系统**的 REST 接口说明。仅包含：接入鉴权、合作方管理、监测任务管理、情报查询。

> 基础 URL 示例：`http://<舆情爬虫主机>:5000/api`  
> 完整能力说明见 [`API对接说明.md`](API对接说明.md)。

---

## 1. 通用约定

### 1.1 请求格式

| 项目 | 说明 |
|------|------|
| 协议 | HTTP/HTTPS |
| 编码 | UTF-8 |
| Content-Type | `application/json`（POST / PUT / PATCH 请求体） |
| 鉴权 | 见第 2 节 |

### 1.2 响应格式

所有 JSON 接口统一包含 `ok` 字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ok` | boolean | `true` 成功；`false` 失败 |
| `msg` | string | 失败时的中文说明（成功时通常省略） |
| 其他 | — | 业务数据字段 |

**HTTP 状态码与 `ok` 的关系：**

| HTTP | 含义 | 典型场景 |
|------|------|----------|
| 200 | 请求已处理 | `ok: true` 成功；部分业务错误也返回 200 + `ok: false` |
| 400 | 参数不合法 | 字段校验失败、互斥参数冲突 |
| 401 | 未鉴权 | 缺少或无效 API Key |
| 403 | 无写权限 | 写操作未携带有效 API Key / 管理员 Session |
| 404 | 资源不存在 | 合作方 / 任务 / 情报 ID 不存在 |

### 1.3 时间格式

ISO 8601 字符串，UTC 或带时区，例如：`2026-06-01T08:30:00` 或 `2026-06-01T08:30:00+08:00`。

---

## 2. 接入与鉴权

### 2.1 启用条件

`config.json` 中 `api_auth.enabled=true`（默认开启）时，本文档所列接口均须鉴权。

### 2.2 传递 API Key

任选一种（推荐 Header）：

```http
Authorization: Bearer <your-api-key>
```

或

```http
X-API-Key: <your-api-key>
```

GET 请求亦支持 Query（不推荐）：`?api_key=<your-api-key>`

Key 配置来源：环境变量 `INTEL_API_KEY` / `INTEL_API_KEYS`，或 `config.json` → `api_auth.keys[]`。

### 2.3 写操作权限

合作方 / 任务的**创建、修改、删除**受 `@require_admin` 保护，须满足以下之一：

- 有效 **API Key**（业务系统推荐）
- Web 控制台**管理员 Session**（人工运维）

读操作、执行任务、查情报：仅需 API Key。

### 2.4 探活

**GET** `/api/integration/auth/status`

**请求示例**

```http
GET /api/integration/auth/status
Authorization: Bearer sk-xxxx
```

**成功（200）**

```json
{
  "ok": true,
  "api_auth_enabled": true,
  "authenticated": true,
  "via": "api_key",
  "keys_configured": 1
}
```

**失败 — 未带 Key（401）**

```json
{
  "ok": false,
  "msg": "需要有效的 API Key（Header: Authorization: Bearer <key> 或 X-API-Key）"
}
```

| `via` 取值 | 说明 |
|------------|------|
| `api_key` | 通过 API Key 鉴权 |
| `admin_session` | 通过管理员 Cookie |
| `none` | 未鉴权 |

---

## 3. 合作方管理

### 3.1 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | int | — | 合作方 ID（只读） |
| `name` | string | 创建时必填 | 主名称 |
| `aliases` | string[] | 否 | 别名列表，用于匹配 |
| `exclude_words` | string[] | 否 | 排除词 |
| `monitor_keywords` | string[] | 否 | 监测关键词（如小红书搜索词） |
| `industry_cohort` | string | 否 | 行业 cohort |
| `priority_tier` | string | 否 | `P0` / `P1` / `P2`，默认 `P1` |
| `enabled` | boolean | 否 | 是否启用，默认 `true` |
| `notes` | string | 否 | 备注 |
| `stats` | object | — | 列表接口附加统计（只读） |

`stats` 结构：

| 字段 | 说明 |
|------|------|
| `default_task_id` | 最近关联的监测任务 ID |
| `intel_total` | 该合作方情报总数 |
| `intel_medium_plus` | medium + high 情报数 |
| `raw_total` | 默认任务下源数据条数 |

---

### 3.2 列表合作方

**GET** `/api/partners`

**Query 参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `enabled_only` | `1` | 可选，仅返回 `enabled=true` |

**成功（200）**

```json
{
  "ok": true,
  "partners": [
    {
      "id": 1,
      "name": "示例消金",
      "aliases": ["示例金融"],
      "exclude_words": ["招聘"],
      "monitor_keywords": ["示例消金 投诉"],
      "industry_cohort": "消金",
      "priority_tier": "P1",
      "priority_source": "auto",
      "priority_updated_at": "",
      "priority_reason": "",
      "source_timeouts": {},
      "enabled": true,
      "notes": "",
      "created_at": "2026-06-01T02:00:00",
      "updated_at": "2026-06-01T02:00:00",
      "stats": {
        "default_task_id": 100156,
        "intel_total": 320,
        "intel_medium_plus": 85,
        "raw_total": 6573
      }
    }
  ]
}
```

**失败 — 未鉴权（401）**：同 2.4。

---

### 3.3 获取单个合作方

**GET** `/api/partners/{partner_id}`

**成功（200）**

```json
{
  "ok": true,
  "partner": {
    "id": 1,
    "name": "示例消金",
    "aliases": ["示例金融"],
    "exclude_words": [],
    "monitor_keywords": ["示例消金"],
    "industry_cohort": "消金",
    "priority_tier": "P1",
    "enabled": true,
    "notes": "",
    "created_at": "2026-06-01T02:00:00",
    "updated_at": "2026-06-01T02:00:00"
  }
}
```

**失败 — 不存在（404）**

```json
{
  "ok": false,
  "msg": "不存在"
}
```

---

### 3.4 创建合作方

**POST** `/api/partners`  
**权限**：需管理员 Session 或 API Key

**请求体**

```json
{
  "name": "新合作方",
  "aliases": ["别名A"],
  "exclude_words": ["广告"],
  "monitor_keywords": ["新合作方 投诉", "新合作方 维权"],
  "industry_cohort": "消金",
  "priority_tier": "P1",
  "enabled": true,
  "notes": "由风险监控系统同步创建"
}
```

**成功（200）**

```json
{
  "ok": true,
  "partner": {
    "id": 42,
    "name": "新合作方",
    "aliases": ["别名A"],
    "exclude_words": ["广告"],
    "monitor_keywords": ["新合作方 投诉", "新合作方 维权"],
    "industry_cohort": "消金",
    "priority_tier": "P1",
    "priority_source": "auto",
    "enabled": true,
    "notes": "由风险监控系统同步创建",
    "created_at": "2026-06-01T10:00:00",
    "updated_at": "2026-06-01T10:00:00"
  }
}
```

**失败 — 缺少 name（200）**

```json
{
  "ok": false,
  "msg": "name 必填"
}
```

**失败 — 无写权限（403）**

```json
{
  "ok": false,
  "msg": "需要管理员登录"
}
```

---

### 3.5 更新合作方

**PUT** `/api/partners/{partner_id}`  
**权限**：需管理员 Session 或 API Key

**请求体**（部分字段即可，未传字段保持原值）

```json
{
  "name": "新合作方（更名）",
  "aliases": ["别名A", "别名B"],
  "enabled": false
}
```

**成功（200）**

```json
{
  "ok": true,
  "partner": {
    "id": 42,
    "name": "新合作方（更名）",
    "enabled": false
  }
}
```

**失败 — 不存在（404）**

```json
{
  "ok": false,
  "msg": "不存在"
}
```

---

### 3.6 删除合作方

**DELETE** `/api/partners/{partner_id}`  
**权限**：需管理员 Session 或 API Key

**成功（200）**

```json
{
  "ok": true
}
```

**失败 — 不存在（200，`ok: false`）**

```json
{
  "ok": false
}
```

---

### 3.7 更新合作方优先级（可选）

**PATCH** `/api/partners/{partner_id}/priority`  
**权限**：仅需 API Key（无需管理员）

**请求体**

```json
{
  "tier": "P0",
  "reason": "风险监控系统上调"
}
```

**成功（200）**

```json
{
  "ok": true,
  "partner": {
    "id": 42,
    "priority_tier": "P0",
    "priority_source": "business",
    "priority_reason": "风险监控系统上调"
  }
}
```

**失败 — 缺少 tier（200）**

```json
{
  "ok": false,
  "msg": "tier 必填"
}
```

---

## 4. 监测任务管理

### 4.1 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 任务 ID |
| `name` | string | 任务名称 |
| `status` | string | 见 4.2 状态枚举 |
| `partner_ids` | int[] | 关联合作方 ID 列表 |
| `sources` | string[] | 数据源：`heimao`、`xhs` |
| `max_pages` | int | 每个 keyword 最大列表页数 |
| `fetch_detail` | boolean | 是否抓详情（黑猫 legacy 模式） |
| `crawl_mode` | string | `legacy` / `list_first` |
| `crawl_only` | boolean | 仅爬取，Run 结束跳过最终 AI |
| `business_spec` | object | 业务规则，如 `{"ignore_before": "2024-01-01"}` |
| `schedule` | object | 定时配置，见下表 |
| `progress` | object | 运行进度（只读） |
| `raw_count` | int | 源数据条数（列表/详情接口 enrich） |
| `intel_count` | int | 情报条数 |
| `can_run` | boolean | 是否可立即执行 |
| `can_reanalyze` | boolean | 是否可增量 AI |
| `error_message` | string | 失败原因 |

`schedule` 结构：

| 字段 | 说明 |
|------|------|
| `enabled` | 是否启用定时 |
| `cron` | Cron 表达式 |
| `timezone` | 时区，如 `Asia/Shanghai` |
| `skip_if_running` | 上一 Run 未结束时跳过 |

### 4.2 任务状态枚举

| status | 说明 |
|--------|------|
| `queued` | 已创建，未运行 |
| `crawling` | 爬取中 |
| `analyzing` | AI 分析中（含 list 初筛阶段） |
| `done` | 完成 |
| `failed` | 失败 |
| `paused` | 已暂停（可继续） |
| `stopped` | 已终止 |

---

### 4.3 列表任务

**GET** `/api/monitor/tasks`

**成功（200）**

```json
{
  "ok": true,
  "tasks": [
    {
      "id": 100156,
      "name": "每日舆情监测",
      "status": "crawling",
      "partner_ids": [1, 2],
      "sources": ["heimao", "xhs"],
      "max_pages": 2,
      "fetch_detail": true,
      "crawl_mode": "list_first",
      "crawl_only": false,
      "business_spec": { "ignore_before": "2024-01-01" },
      "schedule": { "enabled": false, "cron": "", "timezone": "Asia/Shanghai" },
      "progress": { "phase": "list_crawl", "run_id": 214 },
      "raw_count": 6573,
      "intel_count": 120,
      "can_run": false,
      "can_reanalyze": true,
      "can_pause": true,
      "can_stop": true,
      "run_block_reason": "任务正在运行中",
      "next_run_at": null,
      "last_run": {
        "id": 214,
        "status": "running",
        "trigger": "manual",
        "analyze_mode": "incremental",
        "crawl_only": true,
        "started_at": "2026-06-01T08:00:00"
      },
      "created_at": "2026-05-28T00:00:00",
      "updated_at": "2026-06-01T08:00:00"
    }
  ]
}
```

---

### 4.4 获取任务详情

**GET** `/api/monitor/tasks/{task_id}`

**成功（200）**：结构同列表中单条 `task`，字段更完整。

**失败 — 不存在（404）**

```json
{
  "ok": false,
  "msg": "不存在"
}
```

---

### 4.5 创建任务

**POST** `/api/monitor/tasks`  
**权限**：需管理员 Session 或 API Key

**请求体**

```json
{
  "name": "风险监控-每日任务",
  "partner_ids": [1, 2],
  "sources": ["heimao", "xhs"],
  "max_pages": 2,
  "fetch_detail": true,
  "crawl_mode": "list_first",
  "crawl_only": false,
  "business_spec": {
    "ignore_before": "2024-01-01"
  },
  "schedule": {
    "enabled": true,
    "cron": "0 8 * * *",
    "timezone": "Asia/Shanghai",
    "skip_if_running": true
  }
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `partner_ids` | **是** | 至少一个合作方 ID |
| `name` | 否 | 缺省自动生成 |
| `sources` | 否 | 缺省读 `monitor.default_sources` |

**成功（200）**

```json
{
  "ok": true,
  "task": {
    "id": 100200,
    "name": "风险监控-每日任务",
    "status": "queued",
    "partner_ids": [1, 2],
    "sources": ["heimao", "xhs"],
    "max_pages": 2,
    "fetch_detail": true,
    "crawl_only": false,
    "raw_count": 0,
    "intel_count": 0,
    "can_run": true
  }
}
```

**失败 — partner_ids 为空（200）**

```json
{
  "ok": false,
  "msg": "partner_ids 必填"
}
```

---

### 4.6 更新任务

**PUT** `/api/monitor/tasks/{task_id}`  
**权限**：需管理员 Session 或 API Key

**请求体**（示例）

```json
{
  "name": "风险监控-每日任务（修订）",
  "partner_ids": [1, 2, 3],
  "max_pages": 3,
  "crawl_only": true,
  "business_spec": { "ignore_before": "2025-01-01" }
}
```

**成功（200）**

```json
{
  "ok": true,
  "task": {
    "id": 100200,
    "name": "风险监控-每日任务（修订）",
    "status": "queued",
    "max_pages": 3,
    "crawl_only": true
  }
}
```

**失败 — 任务运行中（200）**

```json
{
  "ok": false,
  "msg": "运行中的任务不可编辑"
}
```

**失败 — partner_ids 为空（200）**

```json
{
  "ok": false,
  "msg": "partner_ids 不能为空"
}
```

---

### 4.7 删除任务

**DELETE** `/api/monitor/tasks/{task_id}`  
**权限**：需管理员 Session 或 API Key

**成功（200）**

```json
{
  "ok": true
}
```

**失败 — 运行中（404）**

```json
{
  "ok": false,
  "msg": "运行中的任务不可删除"
}
```

---

### 4.8 执行任务

**POST** `/api/monitor/run`  
**权限**：仅需 API Key

**请求体**

```json
{
  "task_id": 100200,
  "analyze_mode": "incremental",
  "crawl_only": false,
  "business_spec": {
    "ignore_before": "2024-01-01"
  }
}
```

| 字段 | 说明 |
|------|------|
| `task_id` | **必填** |
| `analyze_mode` | `incremental`（默认）或 `full_replace` |
| `crawl_only` | 不传则继承任务配置 / 全局默认 |
| `business_spec` | 可选，覆盖本次 Run 的业务规则 |

**成功（200）** — 异步启动，立即返回

```json
{
  "ok": true,
  "task_id": 100200,
  "analyze_mode": "incremental",
  "crawl_only": false
}
```

**失败 — 系统繁忙（200）**

```json
{
  "ok": false,
  "msg": "已有任务进行中"
}
```

**失败 — 任务不存在（404）**

```json
{
  "ok": false,
  "msg": "任务不存在"
}
```

**失败 — 参数冲突（400）**

```json
{
  "ok": false,
  "msg": "crawl_only 与 full_replace 不能同时使用"
}
```

> 执行进度通过 **GET** `/api/monitor/tasks/{task_id}` 轮询 `status`、`progress` 字段。

---

### 4.9 增量 / 全量 AI 分析

**POST** `/api/monitor/reanalyze`  
**权限**：仅需 API Key

**请求体**

```json
{
  "task_id": 100200,
  "analyze_mode": "incremental"
}
```

| analyze_mode | 说明 |
|--------------|------|
| `incremental` | 仅分析新增/更新的源数据 |
| `full_replace` | 清除旧情报后全量重分析 |

**成功（200）** — 异步

```json
{
  "ok": true,
  "task_id": 100200,
  "analyze_mode": "incremental"
}
```

**失败 — 任务运行中禁止全量（200）**

```json
{
  "ok": false,
  "msg": "任务运行中不可全量重分析"
}
```

**失败 — 无源数据（200）**

```json
{
  "ok": false,
  "msg": "无原始数据，请先执行完整监测"
}
```

> 任务 `crawling` / `analyzing` 期间允许 **incremental**（对已勘察 detail 数据做 AI，不中断爬取）。

---

### 4.10 暂停 / 终止任务

**POST** `/api/monitor/tasks/{task_id}/pause`  
**POST** `/api/monitor/tasks/{task_id}/stop`

**请求体（可选）**

```json
{
  "source": "all"
}
```

| source | 说明 |
|--------|------|
| `all` | 整任务（默认） |
| `heimao` / `xhs` | 仅暂停/终止指定数据源 |

**成功 — 暂停（200）**

```json
{
  "ok": true,
  "task_id": 100200,
  "action": "pause",
  "source": "all"
}
```

**失败 — 任务未运行（200）**

```json
{
  "ok": false,
  "msg": "任务未在运行中"
}
```

---

### 4.11 查询 Run 历史与详情

**GET** `/api/monitor/tasks/{task_id}/runs?page=1&limit=20`

**成功（200）**

```json
{
  "ok": true,
  "total": 5,
  "page": 1,
  "limit": 20,
  "runs": [
    {
      "id": 214,
      "task_id": 100156,
      "trigger": "manual",
      "analyze_mode": "incremental",
      "status": "running",
      "crawl_only": true,
      "started_at": "2026-06-01T08:00:00",
      "finished_at": null,
      "crawl_duration_ms": 3600000,
      "analyze_duration_ms": 0,
      "stats": {
        "raw_new": 1200,
        "intel_written": 0,
        "analyze_deferred": true,
        "pending_analyze_raw_count": 4500
      },
      "error_message": ""
    }
  ]
}
```

**GET** `/api/monitor/runs/{run_id}?log_limit=100`

**成功（200）**

```json
{
  "ok": true,
  "run": {
    "id": 214,
    "task_id": 100156,
    "status": "done",
    "crawl_only": false,
    "timing_by_source": {
      "heimao": { "crawl_ms": 120000, "intel_analyze_ms": 30000 },
      "xhs": { "list_crawl_ms": 900000, "investigation_ms": 600000 }
    },
    "token_usage": {
      "total": { "prompt_tokens": 50000, "completion_tokens": 8000, "total_tokens": 58000 }
    }
  },
  "logs": [
    { "level": "INFO", "message": "[monitor] 监测任务完成，情报 320 条", "created_at": "2026-06-01T10:00:00" }
  ]
}
```

---

## 5. 情报查询

### 5.1 情报字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 情报 ID |
| `task_id` | int | 所属监测任务 |
| `partner_id` | int | 合作方 ID |
| `partner_name` | string | 合作方名称 |
| `source` | string | `heimao` / `xhs` |
| `url` | string | 原文链接 |
| `title` | string | 标题 |
| `body` | string | 正文摘要 |
| `published_at` | string | 内容发布时间 |
| `captured_at` | string | 源数据入库时间 |
| `analyzed_at` | string | AI 分析时间 |
| `relevance` | string | `high` / `medium` / `low` / `noise` |
| `risk_types` | string[] | 风险类型标签 |
| `summary` | string | AI 摘要 |
| `sentiment_label` | string | `negative` / `neutral` / `positive` |
| `sentiment_score` | float | 情感分 -1.0 ~ 1.0 |
| `confidence` | float | 模型置信度 |
| `export_tier` | string | `include` / `review` / `exclude` |
| `schema_version` | string | 当前 `1.1` |

> 本 API **不提供** `weighted_score`、`final_risk` 等决策字段，权重与最终风险等级由风险监控系统自行计算。

---

### 5.2 分页查询情报

**GET** `/api/intel/records`

**Query 参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | int | 监测任务 ID |
| `partner_id` | int | 合作方 ID |
| `source` | string | 数据源 |
| `relevance_min` | string | 最低相关度，如 `medium` 表示 medium+ |
| `since` | string | 采集时间不早于此（ISO） |
| `risk_type` | string | 风险类型子串 |
| `export_tier` | string | `include` / `review` / `exclude` |
| `sentiment_label` | string | `negative` / `neutral` / `positive`（支持中文） |
| `sentiment_score_min` | float | 情感分下限 |
| `sentiment_score_max` | float | 情感分上限 |
| `page` | int | 页码，默认 1 |
| `page_size` | int | 每页条数，默认 20，最大 200 |

**请求示例**

```http
GET /api/intel/records?partner_id=1&relevance_min=medium&since=2026-06-01T00:00:00&page=1&page_size=50
Authorization: Bearer sk-xxxx
```

**成功（200）**

```json
{
  "ok": true,
  "applied_filters": {
    "partner_id": 1,
    "relevance_min": "medium",
    "since": "2026-06-01T00:00:00"
  },
  "total": 85,
  "page": 1,
  "page_size": 50,
  "records": [
    {
      "id": 9001,
      "task_id": 100156,
      "partner_id": 1,
      "partner_name": "示例消金",
      "source": "heimao",
      "url": "https://tousu.sina.com.cn/complaint/view/173xxxx",
      "title": "用户投诉示例消金暴力催收",
      "body": "本人于2026年5月…",
      "published_at": "2026-05-28",
      "captured_at": "2026-06-01T08:15:00",
      "analyzed_at": "2026-06-01T08:20:00",
      "relevance": "high",
      "risk_types": ["暴力催收", "投诉维权"],
      "subject_hits": ["示例消金"],
      "summary": "用户投诉暴力催收，情绪强烈。",
      "sentiment_label": "negative",
      "sentiment_score": -0.82,
      "confidence": 0.91,
      "export_tier": "include",
      "dedup_key": "heimao:abc123",
      "is_duplicate": false,
      "schema_version": "1.1",
      "prompt_version": "v1-high-recall",
      "model": "MiniMax-Text-01",
      "raw_record_id": 55001,
      "extra": {}
    }
  ]
}
```

**成功 — 无匹配（200）**

```json
{
  "ok": true,
  "applied_filters": { "partner_id": 999 },
  "total": 0,
  "page": 1,
  "page_size": 50,
  "records": []
}
```

---

### 5.3 获取单条情报

**GET** `/api/intel/records/{record_id}`

**成功（200）**

```json
{
  "ok": true,
  "record": {
    "id": 9001,
    "task_id": 100156,
    "partner_id": 1,
    "partner_name": "示例消金",
    "source": "heimao",
    "relevance": "high",
    "title": "用户投诉示例消金暴力催收"
  }
}
```

**失败 — 不存在（404）**

```json
{
  "ok": false,
  "msg": "不存在"
}
```

---

### 5.4 导出情报

**GET** `/api/intel/export`

**Query 参数**：与 5.2 相同，另加：

| 参数 | 说明 |
|------|------|
| `format` | `json`（默认）/ `csv` / `xlsx` |
| `task_id` | 可选，限定任务 |

**请求示例**

```http
GET /api/intel/export?partner_id=1&relevance_min=medium&format=json
Authorization: Bearer sk-xxxx
```

**成功（200）**：返回文件下载（`Content-Disposition: attachment`）。

JSON 格式顶层结构：

```json
{
  "schema_version": "1.1",
  "exported_at": "2026-06-01T10:30:00",
  "records": [ ]
}
```

**失败 — 未鉴权（401）**：同 2.4。

---

### 5.5 看板汇总（可选）

**GET** `/api/dashboard/summary`

**成功（200）**

```json
{
  "ok": true,
  "partners_total": 12,
  "partners_enabled": 10,
  "tasks_total": 8,
  "tasks_running": 1,
  "intel_total": 5200,
  "intel_medium_plus": 1800,
  "recent_runs": []
}
```

---

## 6. 典型对接流程

```
1. GET  /api/integration/auth/status     → 验证 Key
2. POST /api/partners                    → 同步合作方（或 GET 已有 ID）
3. POST /api/monitor/tasks               → 创建监测任务
4. POST /api/monitor/run                 → 触发执行
5. GET  /api/monitor/tasks/{id}         → 轮询 status 直至 done / failed
6. GET  /api/intel/records?partner_id=   → 拉取 medium+ 情报
7. PUT  /api/partners/{id}               → 按需更新别名/关键词
8. POST /api/monitor/reanalyze           → 仅爬取后可补跑 AI
```

---

## 7. 错误码速查

| HTTP | ok | msg 示例 | 处理建议 |
|------|-----|----------|----------|
| 401 | false | 需要有效的 API Key… | 检查 Header / Key 配置 |
| 403 | false | 需要管理员登录 | 写操作补 API Key |
| 404 | false | 不存在 / 任务不存在 | 检查 ID |
| 400 | false | crawl_only 与 full_replace… | 修正请求参数 |
| 200 | false | 已有任务进行中 | 等待当前 Run 结束或先 stop |
| 200 | false | 运行中的任务不可编辑 | 等任务结束后再 PUT |
| 200 | false | partner_ids 必填 | 创建任务时传合作方 |
| 200 | false | name 必填 | 创建合作方时传 name |

---

## 8. 相关度与权重（业务侧）

建议映射（非本系统字段，由风险监控系统定义）：

```
relevance_to_number: high=3, medium=2, low=1, noise=0
score = relevance_to_number(record.relevance) * weight[record.source]
```

---

*文档版本：2026-06-01 · 与舆情爬虫-pkg 代码同步*
