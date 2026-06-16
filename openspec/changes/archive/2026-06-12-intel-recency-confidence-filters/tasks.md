## 1. 发布时间解析（基础）

- [x] 1.1 实现 `intel/date_parse.py`：`parse_published_date(text, anchor_date)`（绝对日期 + 相对中文）
- [x] 1.2 单元测试 `scripts/test_date_parse.py`（绝对/相对/空/边界）

## 2. Normalize 与 reports

- [x] 2.1 `reports.py`：`structure_heimao_record` / `structure_xhs_record` 接入 date_parse；详情 time 优先
- [x] 2.2 `intel/normalizers/heimao.py`、`xhs.py`：输出 `YYYY-MM-DD` 或空；extra 可选 `date_parse_quality`
- [x] 2.3 确认 list/detail crawl payload 的 `time` 字段在 investigation 后能被 normalize 覆盖

## 3. 配置

- [x] 3.1 `config.py` / `config.json.example` 增加 `analysis.recency.*`（30/90/0.4/enabled）
- [x] 3.2 `field_labels.py` 暴露 recency 与 confidence 相关键（若经 UI 编辑）

## 4. DB 与 intel schema

- [x] 4.1 `intel/db.py` migration：`intel_records.confidence REAL`；读写 `_row_intel` / `insert_intel_record`
- [x] 4.2 API 响应与 export 列增加 `confidence`；`extra.relevance_llm` 写入策略

## 5. AnalyzePipeline（LLM + 后处理）

- [x] 5.1 `intel/analyze.py`：批次输入含 `published_at`、`captured_at`；输出解析 `confidence`
- [x] 5.2 更新默认 system prompt / active prompt 模板：confidence 语义 + 时效指引
- [x] 5.3 实现 `apply_recency_relevance()`：30/90 天降档 + confidence 降档；无日期跳过 age 规则
- [x] 5.4 `_mock_analyze` 同步 confidence；写入前 clamp 0~1

## 6. 情报 API 情感筛选

- [x] 6.1 `list_intel_records` 支持 `sentiment_label`、`sentiment_score_min`、`sentiment_score_max`（AND）
- [x] 6.2 `intel/api.py` GET records + export 透传上述参数

## 7. 前端筛选 UI

- [x] 7.1 `templates/app.html` + `static/panel-intel.js`：情感 label 下拉 + score min/max 输入
- [x] 7.2 `intelFilterParams` / 深链 query / 导出调用对齐新参数；fTask 行为回归

## 8. 文档

- [x] 8.1 更新 `代码说明.md`（date_parse、recency、confidence、情感筛选）
- [x] 8.2 `openspec/verification-pending.md` 登记 § intel-recency-confidence-filters

## 9. 手动验证（§ intel-recency-confidence-filters）

- [ ] 9.1 黑猫/xhs raw：源数据页可见规范 `YYYY-MM-DD` 或空（非乱码相对时间直出）
- [ ] 9.2 跑监测或 reanalyze：intel 含 `confidence`；`published_at` 传入后旧文 high 可被降为 medium/low
- [ ] 9.3 无 `published_at` 条目：仍可 high，不因缺日期 alone 降档
- [ ] 9.4 情报列表：sentiment_label=negative 与 score 区间组合筛选正确；导出与列表一致
- [ ] 9.5 验证完成后 `python scripts/sync_verification_tasks.py push`
