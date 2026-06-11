## 1. 字段标签注册表

- [x] 1.1 新增 `field_labels.py`：crawl/normalize/analysis/auth/server 等 group 的 label/group/type/help
- [x] 1.2 导出 `static/field-labels.json`（脚本或手写同步）与 `renderFieldLabel(key)` 工具
- [x] 1.3 数据源 Tab：CrawlProfile + Normalize 表单改用 registry 标签
- [x] 1.4 大模型 Tab + 系统设置：为 cfg-* / ai-* 字段挂 `data-field-key` 并批量应用标签
- [x] 1.5 监测看板/合作方/任务表单：共用 registry（含表头中文）

## 2. 采集时间与 API

- [x] 2.1 `intel/runner.py`：候选携带 `captured_at=raw.created_at`；`analyze.py` insert 透传
- [x] 2.2 `intel/db.py`：`serialize_intel_record` 增加 `analyzed_at`（= created_at）
- [x] 2.3 看板 `panel-intel.js`：三列时间（发布/采集/生成）
- [x] 2.4 `intel/export_intel.py`：Excel/JSON 列对齐
- [x] 2.5 文档：`captured_at` 语义 BREAKING 说明

## 3. Normalize 清洗配置

- [x] 3.1 `config.py` / `config.json` 默认 `heimao.normalize.*`、`xhs.normalize.*`
- [x] 3.2 扩展 `source_profiles.py`：NORMALIZE_PROFILE_KEYS + PATCH 白名单
- [x] 3.3 改造 `intel/normalizers/heimao.py`、`xhs.py` 读取 normalize 配置
- [x] 3.4 `intel/api.py` profile 响应分组 crawl/normalize；`app-sources.js` 双区块 UI
- [x] 3.5 默认值与现网行为一致（回归：reply/merchant 仍在 body）

## 4. Prompt SQLite 版本库

- [x] 4.1 `intel/db.py`：`prompt_templates` 表 + CRUD + activate + 种子 builtin
- [x] 4.2 `intel/prompts.py`（或 db 模块）：`load_active_prompt()`、`list_prompts()`
- [x] 4.3 `intel/analyze.py`：`get_system_prompt()` 改读 active 模板；`prompt_version`=模板 id
- [x] 4.4 `intel/api.py`：`/api/analysis/prompts*` 路由（写操作 require_admin）
- [x] 4.5 大模型 Tab UI：版本下拉、编辑器回显、新建/激活/删除（非 builtin）
- [x] 4.6 废弃/忽略 `config.analysis.system_prompt` 写入路径（兼容读取一次迁移）

## 5. 文档

- [x] 5.1 更新 `代码说明.md`：时间字段、normalize、prompt 表、field registry
- [x] 5.2 更新 `docs/API对接说明.md`：prompts API、analyzed_at、captured_at 语义

## 6. 手动验证

- [x] 6.1 跑监测任务：看板三列时间正确；captured_at 早于 analyzed_at
- [x] 6.2 关闭 heimao `include_reply_in_body` 后重跑：body 变化可观测
- [x] 6.3 Prompt：新建版本→激活→重跑 AI→intel.prompt_version 为新 id
- [x] 6.4 全站抽样：数据源/系统/大模型字段均为中文（英文键）
- [x] 6.5 导出 Excel/JSON 含三时间列
