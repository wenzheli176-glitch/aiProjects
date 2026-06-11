## Context

情报管道：`CrawlAdapter` → `raw_records` → `NormalizeAdapter` → `AnalyzePipeline` → `intel_records`。当前 `intel_records.captured_at` 在 AI 写入时默认 `now()`，与「采集时间」语义不符；看板单列「时间」混用 `published_at`。数据源 Tab 仅暴露 CrawlProfile 英文键；清洗逻辑硬编码于 `intel/normalizers/*.py`。Prompt 存 `config.analysis.system_prompt` 单字符串，空值时 UI 不回显 `DEFAULT_SYSTEM_PROMPT`。

用户决策（已锁定）：
- 采集时间 = `raw_records.created_at`
- 清洗 = heimao/xhs 各若干关键开关/参数（第一期）
- Prompt = SQLite 多版本 + 活跃切换
- 中文标签 = 全站统一元数据

## Goals / Non-Goals

**Goals:**
- 看板/API/导出区分发布时间、采集时间、生成时间
- `runner.py` 归一化候选携带 `captured_at`（来自 raw），`insert_intel_record` 写入
- `config.{heimao,xhs}.normalize.*` 可配置 + 数据源 Tab 可视化 + profile API 白名单
- `field_labels.py` + `static/field-labels.js` 驱动全站 label
- `prompt_templates` SQLite 表 + CRUD API + 大模型 Tab 版本管理
- `get_system_prompt()` 从活跃模板读取；内置默认种子一条

**Non-Goals:**
- 可视化 pipeline 拖拽编辑器
- 修改 config.json 键名为中文
- 历史 intel 回填 captured_at（可选一次性脚本，非 MVP）
- Prompt diff/AB 实验框架

## Decisions

### D1 采集时间透传

在 `intel/runner.py` `_build_candidates` 中，从 `row['created_at']`（raw_records）写入候选 `captured_at`；`insert_intel_record` 优先使用传入值，禁止 AI 阶段覆盖为 `now()`。

生成时间：API 与 UI 暴露 `analyzed_at` 字段，值为 `intel_records.created_at`（不新增 DB 列）。

### D2 Normalize 配置块

新增 `NORMALIZE_PROFILE_KEYS`（`source_profiles.py` 旁或同文件）：

**heimao.normalize**（默认与现行为一致）：
| 键 | 类型 | 默认 | 作用 |
|----|------|------|------|
| `include_reply_in_body` | bool | true | body 含 reply |
| `include_merchant_in_body` | bool | true | body 含 merchant |
| `include_problem_in_body` | bool | true | body 含 problem |
| `body_max_chars` | int | 0 | 0=不截断 |
| `strip_whitespace` | bool | true | 合并空行 |

**xhs.normalize**：
| 键 | 类型 | 默认 | 作用 |
|----|------|------|------|
| `body_max_chars` | int | 0 | 正文截断 |
| `fallback_title_from_body` | bool | true | 无 title 用 body 前缀 |
| `include_likes_in_extra` | bool | true | extra.likes |
| `strip_whitespace` | bool | true | 去多余空白 |

`HeimaoNormalizeAdapter` / `XhsNormalizeAdapter` 构造时读 `cfg(source_id, 'normalize')`。

`GET/PATCH /api/sources/{id}/profile` 返回 `profile_keys_crawl` + `profile_keys_normalize`（或合并分组 metadata）。

### D3 字段标签注册表

`field_labels.py`：`FIELD_LABELS: dict[str, FieldMeta]`，键为 config 路径或 flat key（如 `page_timeout_ms`、`include_reply_in_body`）。

格式：`label = "页面超时 (page_timeout_ms)"`，含 `group`、`type`、`help`。

前端 `static/field-labels.js` 由构建脚本从 Python 导出 JSON（或手写同步），`renderFieldLabel(key)` 供 sources/system/analysis/crawl 共用。

系统设置 `cfg-*` 表单项：逐步为现有 input 加 `data-field-key`，由 JS 批量替换 label 文本（MVP 覆盖 sources + analysis + system 主要区块）。

### D4 Prompt SQLite 表

```sql
CREATE TABLE prompt_templates (
  id TEXT PRIMARY KEY,           -- slug, e.g. high-recall-v1
  name TEXT NOT NULL,            -- 显示名
  body TEXT NOT NULL,            -- system prompt 模板
  is_builtin INTEGER DEFAULT 0,
  is_active INTEGER DEFAULT 0,   -- 至多一条 active
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

- 迁移：启动时若表空，插入 builtin `default-high-recall`（`DEFAULT_SYSTEM_PROMPT` 文本）并设 active
- `config.analysis.active_prompt_id` 与 DB `is_active` 双写；以 DB 为准，config 作缓存/兼容
- API（`intel/api.py`，写操作 `@require_admin`）：
  - `GET /api/analysis/prompts` — 列表
  - `GET /api/analysis/prompts/{id}` — 详情
  - `POST /api/analysis/prompts` — 新建
  - `PUT /api/analysis/prompts/{id}` — 更新 body/name
  - `POST /api/analysis/prompts/{id}/activate` — 设活跃
  - `DELETE /api/analysis/prompts/{id}` — 非 builtin 可删
- `get_system_prompt(partner)`：`load_active_prompt()` → format 占位符
- 分析写入 `prompt_version` = 活跃模板 `id`
- 大模型 Tab：版本下拉 + 编辑器 + 「另存为新版本」「设为当前」；加载时回显 active 模板全文

### D5 API 响应扩展

`GET /api/intel/records` 每条增加 `analyzed_at`（= created_at），文档说明 `captured_at` 语义变更。

## Risks / Trade-offs

- **[Risk] 旧 intel captured_at 不准** → 文档说明；可选 migration 脚本从 raw_records 回填，非阻塞 MVP
- **[Risk] 字段标签维护成本** → 集中 registry；未知键 fallback 为 `key (key)`
- **[Risk] Prompt 表与 config.system_prompt 分叉** → 保存时停用 config 字段；GET analysis/config 返回 active 模板摘要
- **[Risk] normalize 误配导致 body 为空** → 保存前校验 body 非空样例；默认与现行为一致

## Migration Plan

1. DB migration 添加 `prompt_templates`；种子 builtin
2. 部署 backend + normalize 默认值
3. 部署前端 field-labels + UI
4. 文档更新 captured_at 语义（**BREAKING 文档级**：对接方若依赖旧 captured_at=分析时刻需改读 analyzed_at）

## Open Questions

- 是否在 MVP 提供一次性 `scripts/backfill_captured_at.py`（用户未要求，可放 tasks 可选）
- 系统设置全部 cfg 字段是否一期全部贴 label（proposal 要求全站统一 → tasks 列全量清单）
