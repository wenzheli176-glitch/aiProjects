## 1. 配置与默认值

- [x] 1.1 新增 `heimao.empty_search.login_on_missing_sid`（默认 `false`）；`config.py` / `config.json.example` / 内置 default
- [x] 1.2 将 `heimao.early_stop.empty_page_retry` 默认改为 `0`（`crawl_early_stop.py` HEIMAO_EARLY_STOP_DEFAULT）
- [x] 1.3 `field_labels.json` 补充 `empty_search.login_on_missing_sid` 标签

## 2. 空搜索分类器（login_gate / heimao_session）

- [x] 2.1 实现 `heimao_classify_empty_search(ctx, page, html)` → `has_results` / `no_results` / `empty_uncertain` / `auth_required` / `blocked`
- [x] 2.2 重构 `heimao_wait_if_search_empty`：skip 路径不调用 `wait_for_site_login`；仅 auth 路径保留 `redo_search`
- [x] 2.3 单元测试 `scripts/test_heimao_empty_search_classify.py`：SUB 有效无 sid → skip；无 SUB → auth；`login_on_missing_sid` 回滚

## 3. crawl_heimao 集成（不重试）

- [x] 3.1 删除空结果后的 `_redo_heimao_search` 兜底（`first_html` 无链接时不重搜）
- [x] 3.2 `empty_page_retry=0` 时第 1 页无链接直接 early_stop，不进入 parse_attempts 重试循环
- [x] 3.3 日志区分「跳过无结果」「需登录」；RunMetrics `heimao_skipped_empty`
- [x] 3.4 更新 `scripts/test_early_stop.py`：默认 empty_page_retry=0、空 uncertain 不 login_wait

## 4. 编排

- [x] 4.1 `intel/sources/heimao.py`：传递 `run_metrics`；空 batch 由 `crawl_heimao` 内日志「无结果，跳过」
- [x] 4.2 Worker routine 路径确认无 deferred/轮末重试逻辑

## 5. 文档

- [x] 5.1 更新 `代码说明.md`：黑猫空搜 skip 不重试、登录解耦、`empty_page_retry` 默认 0

## 6. 手动验证

- [ ] 6.1 监测：连续空搜多个关键词/企业，**不**弹「无 sid → 等待登录」（SUB 有效）
- [ ] 6.2 空搜关键词：日志为「跳过」，**无**「重试搜索」/「deferred 重试」
- [ ] 6.3 故意退出微博登录：仍进入 WAITING_LOGIN 并可扫码续跑
- [ ] 6.4 验证完成后 `python scripts/sync_verification_tasks.py push`
