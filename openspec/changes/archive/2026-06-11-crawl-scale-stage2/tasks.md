## 1. Schema 与配置

- [x] 1.1 `intel/db.py`：partners 增加 `industry_cohort`、`priority_tier`、`priority_source`、`priority_updated_at`；raw_records 增加 `crawl_phase`、`list_triage_json`；monitor_tasks 增加 `crawl_mode`、`business_spec_json`
- [x] 1.2 新建 `investigation_queue` 表（task_id、raw_id、url、priority_score、status）
- [x] 1.3 `config.py` / `config.json.example`：`monitor.crawl_mode`、`industry_batch_max_keywords`、`priority_quota`；`analysis.list_triage.*`
- [x] 1.4 DB migration 与 legacy 任务 crawl_mode 默认 `legacy`

## 2. 共享爬取池

- [x] 2.1 `intel/keyword_batch.py`：按 industry_cohort 合并 keywords，支持 max_keywords 分批
- [x] 2.2 `intel/matcher.py`：`match_all_partners()` 多命中；保留 `match_best_partner` 兼容
- [x] 2.3 `intel/sources/heimao.py`、`xhs.py`：实现 `crawl_list_batch()`（fetch_detail=false）
- [x] 2.4 `intel/runner.py`：`crawl_mode=list_first` 分支 — source × keyword_batch 循环，raw partner_id=NULL、crawl_phase=list
- [x] 2.5 分析阶段：多 partner 命中时按 partner 展开 intel 写入

## 3. 列表初筛与勘察

- [x] 3.1 `intel/triage.py`：List Triage LLM 批处理，写 `list_triage_json`
- [x] 3.2 `intel/investigation.py`：队列构建、P0 强制规则、优先级排序
- [x] 3.3 `intel/sources/*`：实现 `crawl_investigation(urls[])`，更新 raw crawl_phase=detail
- [x] 3.4 `intel/runner.py`：串联 list_triage → investigation_crawl → analyze 阶段与 progress/stats
- [x] 3.5 `intel/normalizers/*`：list-phase 允许 body 为空；detail 合并逻辑

## 4. 动态定级与业务 API

- [x] 4.1 `intel/priority.py`：auto 升降 P0/P1/P2 规则
- [x] 4.2 `intel/api.py`：`PATCH /api/partners/:id/priority`、`POST bulk-priority`、`GET priority`
- [x] 4.3 run 请求支持 `business_spec_json`（force_investigation、min_triage_relevance）
- [x] 4.4 runner 调度：按 P0/P1/P2 quota 排序 keyword_batch

## 5. UI 与 Run 指标

- [x] 5.1 合作方表单：industry_cohort、priority_tier 字段
- [x] 5.2 监测任务：crawl_mode 选择（list_first / legacy）与说明文案
- [x] 5.3 Run Drawer：展示 list_triage / investigation 统计与 timing_by_source 扩展
- [x] 5.4 `intel/run_metrics.py`：triage_ms、investigation 计数

## 6. 文档与验证

- [x] 6.1 更新 `代码说明.md`：Stage2 流水线、业务 API、config 新字段
- [x] 6.2 更新 `docs/API对接说明.md`：priority API、business_spec、新 intel 可选字段
- [x] 6.3 单元测试：keyword_batch 合并、match_all_partners、triage 阈值、P0 强制勘察
- [x] 6.4 手动验证：list_first run 无详情请求；investigation 触发 heimao/xhs 登录门禁与弹窗详情
- [x] 6.5 手动验证：business API 指定 P0 后下一 run 优先执行
- [x] 6.6 `openspec/verification-pending.md` 登记 § crawl-scale-stage2 验证项
