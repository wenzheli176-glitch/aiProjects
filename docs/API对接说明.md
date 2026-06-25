# 情报 API 对接说明

面向内网业务系统对接 **IntelRecord**。读接口（GET）内网开放；**写接口**（配置、合作方、任务 CRUD、源 PATCH）需先 `POST /api/admin/login`（`config.admin.enabled=true` 时）。开发模式可设 `admin.enabled=false`。

## 管理员鉴权

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/login` | `{password}`，成功 Set-Cookie |
| POST | `/admin/logout` | 清除 Session |
| GET | `/admin/session` | `{logged_in, role, auth_enabled}` |

环境变量：`ADMIN_PASSWORD`（默认读取名见 `config.admin.password_env`）

## 数据源

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sources?detail=1` | 含 enabled/registered/profile_keys；`notice` 说明不可 UI 加源 |
| PATCH | `/sources/{id}` | 管理员：`{enabled, label}` |
| GET/PATCH | `/sources/{id}/profile` | CrawlProfile 白名单字段；PATCH 需管理员 |
| GET/PATCH | `/monitor/defaults` | 默认源/页数/超时 |

## 基础 URL

默认：`http://<host>:5000/api`

## 核心概念

- **source**：数据来源 ID（`heimao` | `xhs` | …），业务系统据此设置权重
- **relevance**：AI 相关度 `high` | `medium` | `low` | `noise`（高召回策略，存疑多为 `medium`）
- **export_tier**：`include` | `review` | `exclude`
- **schema_version**：IntelRecord 导出 schema，当前 `1.1`（含情感分数字段）

本 API **不包含** `weighted_score`、`final_risk` 等决策字段。

## 合作方

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/partners` | 名单列表，`?enabled_only=1` 仅启用；每条含 `stats`（`intel_medium_plus`、`intel_total`、`raw_total`、`default_task_id`） |
| POST | `/partners` | 创建（**需管理员**） |
| PUT | `/partners/{id}` | 更新（**需管理员**） |
| DELETE | `/partners/{id}` | 删除（**需管理员**） |
| GET | `/partners/priority` | 各合作方 P0/P1/P2 定级与来源 |
| PATCH | `/partners/{id}/priority` | 业务指定 `{tier, reason?}` → `priority_source=business` |
| POST | `/partners/bulk-priority` | 批量 `{items:[{partner_id,tier,reason?}]}` |

合作方字段扩展：`industry_cohort`（行业 cohort）、`priority_tier`（P0/P1/P2）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/partners/suggest-cohort` | 根据名称推荐 cohort 候选 `{name, aliases?, exclude_partner_id?}`；返回 `candidates[]`（含 `source`/`partner_count`/`is_new`）、`existing_cohorts`；只读推荐，不写入 |

## 监测任务（手动 / 定时）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/monitor/tasks` | 任务列表（含 `schedule`、`last_run`、`next_run_at`） |
| POST | `/monitor/tasks` | 创建（**需管理员**）`{name, partner_ids[], sources[], max_pages, crawl_mode?, fetch_detail?, schedule?, business_spec?}`；`business_spec.ignore_before` 为 YYYY-MM-DD |
| GET | `/monitor/tasks/{id}` | 任务详情与状态 |
| PUT | `/monitor/tasks/{id}` | 更新（**需管理员**），可含 `schedule`、`business_spec` |
| DELETE | `/monitor/tasks/{id}` | 删除（**需管理员**） |
| GET | `/monitor/tasks/{id}/runs` | Run 历史（分页） |
| GET | `/monitor/runs/{run_id}` | Run 详情（分源 timing/token） |
| POST | `/monitor/run` | 执行 `{task_id, analyze_mode?, business_spec?}`；`business_spec` 可含 `force_investigation_partner_ids[]`、`min_triage_relevance`、`ignore_before`（YYYY-MM-DD，分析跳过更早内容） |
| POST | `/monitor/reanalyze` | 重跑 AI `{task_id, analyze_mode: incremental\|full_replace}`（`replace` 仍映射 full_replace） |

`schedule` 对象：`{enabled, cron, timezone, preset_id, skip_if_running}`。Cron 由 Web UI 生成，不建议手改。

任务状态：`queued` → `crawling` → `analyzing` → `done` | `failed`（含超时：`error_message` 含「任务超时」，上限 `monitor.task_timeout_sec`，默认 7200 秒）

## 情报记录

### GET `/intel/records`

Query 参数：

| 参数 | 说明 |
|------|------|
| task_id | 监测任务 ID |
| partner_id | 合作方 ID |
| source | 数据源 |
| relevance_min | 最低相关度（如 `medium` 表示 medium+） |
| since | ISO 时间，采集时间不早于此 |
| risk_type | 风险类型子串匹配 |
| page / page_size | 分页，默认 50，最大 500 |

响应：

```json
{
  "ok": true,
  "total": 120,
  "page": 1,
  "page_size": 50,
  "records": [
    {
      "id": 1,
      "task_id": 3,
      "partner_id": 1,
      "partner_name": "示例合作方",
      "source": "heimao",
      "url": "https://...",
      "title": "...",
      "body": "...",
      "published_at": "...",
      "captured_at": "...",
      "analyzed_at": "...",
      "relevance": "medium",
      "risk_types": ["投诉维权"],
      "summary": "...",
      "schema_version": "1.0",
      "prompt_version": "v1-high-recall",
      "model": "gpt-4o-mini"
    }
  ]
}
```

### GET `/intel/export`

- `format=json|xlsx|csv`
- 支持与 `/intel/records` 相同的过滤参数
- JSON 含顶层 `schema_version` 与 `records[]`（含 `published_at`、`captured_at`、`analyzed_at`）

### Prompt 模板（SQLite）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/analysis/prompts` | 列表 |
| GET | `/analysis/prompts/{id}` | 详情含 body |
| POST | `/analysis/prompts` | 新建（管理员） |
| PUT | `/analysis/prompts/{id}` | 更新（管理员） |
| POST | `/analysis/prompts/{id}/activate` | 设为当前（管理员） |
| DELETE | `/analysis/prompts/{id}` | 删除非 builtin（管理员） |

### 时间字段语义（BREAKING 文档）

- `captured_at`：原始数据入库时间（`raw_records.created_at`），**非** AI 分析时刻
- `analyzed_at`：情报生成时间（等同 `created_at`）
- `published_at`：舆情内容发布时间（尽力解析）

## 数据源列表

### GET `/sources`

返回已注册且 `config.sources.*.enabled=true` 的源。

## 权重外置

对接方示例逻辑（伪代码）：

```
score = relevance_to_number(record.relevance) * business_weight[record.source]
```

`relevance` 枚举建议映射：`high=3, medium=2, low=1, noise=0`（由业务方定义，非本系统字段）。

## 云模型与复现

每条记录含 `prompt_version`、`model`。同一批数据 + 同一 prompt 版本应可复现（受模型供应商更新影响）。

### 配置方式

| 方式 | 说明 |
|------|------|
| 看板 → **大模型配置** | 可视化编辑，保存至 `config.json` 的 `analysis.*` |
| 爬虫控制台 → **系统配置 → 大模型** | 同上 |
| `GET/POST /api/analysis/config` | 程序化读写（GET 不返回明文 api_key） |
| 环境变量 | `analysis.api_key_env` 指定变量名（默认 `MINIMAX_API_KEY`） |

可配置项：`endpoint`、`model`、`api_key` / `api_key_env`、`prompt_version`、`batch_size`、`max_body_chars`、`max_retries`、`retry_delay_sec`、`temperature`、`timeout_sec`、`mock_without_key`、`mock_default_relevance`、`system_prompt`（支持 `{partner_name}` `{aliases}` 占位符）。

未配置 API Key 且 `mock_without_key=true` 时，系统使用 mock 打标，便于联调。

---

## Cookie 实例（Worker）

面向多进程 Crawl Worker 的 Cookie 运维；读接口开放，写接口需管理员 Session。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/cookie-instances` | 列出 `monitor.workers.*.instances`：source、instance_id、cdp_port、cookies_file、条数、最近 diagnose |
| POST | `/cookie-instances/{source_id}/{instance_id}/upload` | `{cookies: "<JSON 数组或导出文本>"}` 写入实例 cookies_file（**需管理员**） |
| POST | `/cookie-instances/{source_id}/{instance_id}/diagnose` | 手动登录诊断（**需管理员**）；结果缓存于 `credentials/.cookie_diagnose_cache.json` |

## 管理员数据清理

**需管理员 Session**（`config.admin.enabled=true` 时）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/purge/raw` | 按任务删除源数据 |
| POST | `/admin/purge/intel` | 按任务删除情报（保留 raw） |

请求体 JSON：

| 字段 | 必填 | 说明 |
|------|------|------|
| task_id | 是 | 监测任务 ID |
| partner_id | 否 | 限定合作方 |
| published_before | 否 | 删除 `published_at` 早于该日期的记录（空 published_at 不匹配） |
| dry_run | 否 | `true` 时仅返回 `matched_count`，不删除 |

响应：`{ok, matched_count, deleted_count, dry_run}`。任务状态为 `crawling`/`analyzing` 时返回 400。

响应字段 `has_diagnose_failures=true` 时，Web 顶栏展示 Cookie 异常横幅。

路径安全：仅允许项目内 `credentials/` 下文件；拒绝 `..` 与越界路径。

`config.auth.{site}.cookies_file` 在更新 **该源首个 instance** Cookie 时自动同步。

## 小红书账号池（keyword 轮换）

索引文件：`credentials/xhs/accounts.json`；旧 `credentials/xhs_cookies.json` 首次访问时自动迁移为 `acc-default`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/xhs/accounts` | 账号列表、enabled 数、是否低于 `min_accounts` |
| POST | `/xhs/accounts` | 创建账号 `{label}`（**需管理员**） |
| PATCH | `/xhs/accounts/{id}` | 更新 `label` / `enabled` / `cooldown_until` / `ban_note` |
| DELETE | `/xhs/accounts/{id}` | 删除账号元数据（**需管理员**，不可删 acc-default） |
| POST | `/xhs/accounts/{id}/cookies` | 粘贴 Cookie；可选 `diagnose: true` |
| POST | `/xhs/accounts/{id}/diagnose` | 诊断该账号 Cookie |
| POST | `/xhs/accounts/{id}/login/start` | 打开独立 Chrome 登录页（monitor busy 时 409） |
| GET | `/xhs/accounts/{id}/login/status` | `waiting` / `logged_in` / `timeout` |
| POST | `/xhs/accounts/{id}/login/finish` | 导出 Cookie 并诊断 |
| POST | `/xhs/accounts/{id}/login/cancel` | 关闭登录 Chrome |

监测 Run 执行 xhs keyword 时按 round-robin 轮换账号（每 keyword 换 profile）；诊断失败跳过该号。

---

## Run 状态与 stats（run_state）

### 并发与停止

- 是否允许新 Run / reanalyze：查 `monitor_task_runs` 是否存在 `status` 为 running/crawling/analyzing 的记录（**非**仅内存 `S.running`）。
- `POST /api/stop`：对 active run 设 `stop_requested=1`；Orchestrator / Worker 轮询后中止。
- `GET /api/status` 额外返回：
  - `worker_states`：各 Worker 实例状态（含 `login_wait`）
  - `login_wait`：单 Worker 为对象；多 Worker 为 `{workers: [...]}`

Run 详情 `GET /monitor/runs/{run_id}` 的 `stats_json` 常见扩展字段：

| 字段 | 说明 |
|------|------|
| `cookie_diagnose_failed` | Cookie 诊断失败源数 |
| `sources_degraded` | partial diagnose 后仍继续的降级源数 |
| `worker_instances` | `[{source_id, instance_id, status, diagnose_ok, ...}]` |
| `investigation_modal_done` | xhs 弹窗成功次数（Run 级） |
| `investigation_skipped_quota` | 超 `max_modal_per_run` 跳过条数 |

中文标签见 `GET /api/field-labels` 或 `static/field-labels.json`（group=`monitor_run`）。

### crawl_mode 说明（任务 API）

`POST /monitor/tasks` 仍接受 `crawl_mode`，但 **混合源或含 xhs** 的任务以 `config.sources.{id}.crawl_mode` 为准：

- **xhs**：强制 `list_first`（routine 无弹窗）
- **heimao**：默认 `legacy`

仅 **单源 heimao** 且未开 Worker 时，task 级 `crawl_mode` 仍作 fallback。UI 已隐藏/说明任务级策略降级。

---

## 分析并行

`config.analysis.parallel_batches`（默认 **5**）控制 `intel/analyze.py` 内 ThreadPoolExecutor 并发批数；与 `batch_size` 独立。单批 LLM 失败跳过该批，不 fail 整个 Run。
