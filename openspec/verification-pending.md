# OpenSpec 待验证清单

本文件为**唯一待办验证入口**：各已归档 change 中未勾选的「手动验证」项汇总于此。  
验证完成后在本文件勾选 `- [x]`，再运行同步脚本写回对应 archive 的 `tasks.md`。

```bash
# 查看进度
python scripts/sync_verification_tasks.py status

# 将本文件已勾选项同步到各 archive .../tasks.md
python scripts/sync_verification_tasks.py push

# 从 archive 重新扫描未验证项（保留本文件已勾选状态）
python scripts/sync_verification_tasks.py scan
```

---

## monitor-timeout-unify-xhs-pages

<!-- archive: openspec/changes/archive/2026-06-09-monitor-timeout-unify-xhs-pages/tasks.md -->

- [x] 4.1 将 `monitor.task_timeout_sec` 临时设为 60，创建 2 合作方 × 2 源任务，确认约 60s 后任务 `failed` 且 error 含「任务超时」
- [x] 4.2 单次 xhs 爬取 `max_pages=2`，确认日志为「2页」且出现「XHS第 1/2 页」「XHS第 2/2 页」，第 1 页前有滚动
- [x] 4.3 确认 heimao `max_pages=2` 行为与变更前一致（回归）
- [x] 4.4 确认 `reanalyze` 在大量 raw 数据下不因 60s 测试配置被误杀（使用正常 timeout 或单独测 reanalyze）

## partner-risk-intel

<!-- archive: openspec/changes/archive/2026-06-09-partner-risk-intel/tasks.md -->

- [x] 7.1 创建 2 个合作方（含别名），手动触发 heimao+xhs 监测任务，确认 raw_records 入库
- [x] 7.2 未登录 heimao/xhs 时：确认 login_gate 等待登录后续跑，任务不写入无效详情（沿用既有门禁）
- [x] 7.3 xhs 详情：确认弹窗路径抓取成功，无 App 墙误报为有效正文
- [x] 7.4 AI 分析完成后：看板默认展示 medium+，API 可按 source/partner 过滤
- [x] 7.5 导出 JSON/Excel，确认每条含 `source` 与 `schema_version`

## unified-console-source-admin

<!-- archive: openspec/changes/archive/2026-06-09-unified-console-source-admin/tasks.md -->

- [x] 7.1 访问 `/` 切换全部 Tab，功能与整合前等价（情报筛选、创建任务、手工爬取）
- [x] 7.2 `/dashboard` redirect 正常；监测任务 waiting_login 时任意 Tab 见横幅
- [x] 7.3 未登录：可 run 监测、不可 PATCH sources / POST partners
- [x] 7.4 管理员登录：可改源 enabled、xhs default_max_pages；保存后下次爬取生效
- [x] 7.5 采集调试 Tab：黑猫/XHS 手工爬 + 登录续跑 + 弹窗详情回归
- [x] 7.6 `admin.enabled=false` 本地模式写 API 仍可用（开发文档说明）

## intel-ux-normalize-prompts

<!-- archive: openspec/changes/archive/2026-06-10-intel-ux-normalize-prompts/tasks.md -->

- [x] 6.1 跑监测任务：看板三列时间正确；captured_at 早于 analyzed_at
- [x] 6.2 关闭 heimao `include_reply_in_body` 后重跑：body 变化可观测
- [x] 6.3 Prompt：新建版本→激活→重跑 AI→intel.prompt_version 为新 id
- [x] 6.4 全站抽样：数据源/系统/大模型字段均为中文（英文键）
- [x] 6.5 导出 Excel/JSON 含三时间列

## monitor-runs-schedule-incremental

<!-- archive: openspec/changes/archive/2026-06-10-monitor-runs-schedule-incremental/tasks.md -->

- [x] 9.1 同一 task 执行两次：第二次 raw 不变则 skip LLM；新 URL 仅分析新增
- [x] 9.2 模拟 payload 变化（如 heimao 回复增多）：raw updated_at 刷新且 intel 覆盖重写
- [x] 9.3 全量重分析：intel 清空后全部重写；run 记录 full_replace
- [x] 9.4 启用定时（短 cron 测试）：到点自动 run；运行中重叠 → skipped_overlap
- [x] 9.5 Run 详情：分源 crawl/analyze ms 与 token 与日志量级一致
- [x] 9.6 Schedule UI：选「工作日 09:00」保存重载后 cron 与预览正确

## monitor-run-history-ui

<!-- archive: openspec/changes/archive/2026-06-01-monitor-run-history-ui/tasks.md -->

- [x] 6.1 创建或选用已有监测任务，执行至少 2 次 manual run，点击「历史」展开：默认显示 ≤5 条，摘要列完整
- [x] 6.2 当 total>5 时点击「加载更多」，较旧 Run 追加显示且不丢失已加载行
- [x] 6.3 点击某 Run 行：右侧切换详情，分源 timing/token 与 stats 与 API JSON 一致；「返回编辑」恢复任务表单
- [x] 6.4 失败 Run：`error_message` 可见；`skipped_overlap` run 状态展示正确
- [x] 6.5 确认全程无 `alert()` 展示 Run 历史；Ctrl+F5 后行为正常

## console-ux-overhaul

<!-- archive: openspec/changes/archive/2026-06-11-console-ux-overhaul/tasks.md -->

- [x] 7.1 访问 `/` 默认 home；看板 KPI 点击跳转 intel 且 filter 正确
- [x] 7.2 情报：筛选在上、详情页 `intel_id` 深链、返回保留筛选；导出当前筛选全量
- [x] 7.3 源数据：列表无 payload 全文；详情页全文；导出 json/xlsx；跳转 intel
- [x] 7.4 合作方/任务 Modal 创建编辑；任务页全宽无右栏表单
- [x] 7.5 Run Drawer：展开历史、点击 Run、stats 含义可见；`run_id` 深链
- [x] 7.6 数据源 heimao/xhs Tab 切换保存生效
- [x] 7.7 窄屏（≤900px）主要 Tab 可用；全站浅色无深色残留块
- [x] 7.8 `/dashboard` → home；login_wait 横幅各 Tab 仍可见

## crawl-scale-stage2

<!-- archive: openspec/changes/archive/2026-06-11-crawl-scale-stage2/tasks.md -->

- [x] 6.4 手动验证：list_first 任务 routine 阶段无逐条详情；investigation 触发 heimao/xhs 登录门禁
- [x] 6.5 手动验证：`PATCH /api/partners/{id}/priority` 指定 P0 后下一 run 优先执行 cohort batch

## crawl-early-stop-per-source

<!-- archive: openspec/changes/crawl-early-stop-per-source/tasks.md -->

- [x] 5.1 黑猫调试爬取：关键词结果不足 M 页时，日志出现 `early_stop · empty_page` 且实际页数 < M
- [x] 5.2 黑猫：`early_stop.enabled=false` 时跑满 M 页（不因见底提前结束）
- [x] 5.3 小红书调试爬取：滚至 `- THE END -` 后出现 `early_stop · end_marker`
- [x] 5.4 小红书：短关键词在 end 未出现前，饱和兜底可停止（可选 `saturation_rounds=1`）
- [x] 5.5 验证完成后执行 `python scripts/sync_verification_tasks.py push`

## xhs-investigation-modal-detail

<!-- change: openspec/changes/xhs-investigation-modal-detail/tasks.md -->

- [x] 4.1 list_first 监测：xhs investigation 日志无 goto explore，出现弹窗提取成功
- [x] 4.2 故意使用列表中不存在的 URL：单条 `dom_not_found` skip，任务继续
- [x] 4.3 同 keyword 连续 3+ miss：触发重搜日志，重搜后部分 URL 可定位
- [x] 4.4 未登录 xhs：investigation 触发登录等待后续跑弹窗详情
- [x] 4.5 验证完成后 `python scripts/sync_verification_tasks.py push`

## intel-recency-confidence-filters

<!-- change: openspec/changes/intel-recency-confidence-filters/tasks.md -->

- [x] 9.1 黑猫/xhs raw：源数据页可见规范 `YYYY-MM-DD` 或空（非乱码相对时间直出）
- [x] 9.2 跑监测或 reanalyze：intel 含 `confidence`；`published_at` 传入后旧文 high 可被降为 medium/low
- [x] 9.3 无 `published_at` 条目：仍可 high，不因缺日期 alone 降档
- [x] 9.4 情报列表：sentiment_label=negative 与 score 区间组合筛选正确；导出与列表一致
- [x] 9.5 验证完成后 `python scripts/sync_verification_tasks.py push`

## parallel-crawl-workers-selective-xhs

<!-- archive: openspec/changes/archive/2026-06-17-parallel-crawl-workers-selective-xhs/tasks.md -->

- [x] 5.4 xhs 弹窗在 xhs Worker Chrome；heimao 详情在 heimao Worker（`monitor.workers.enabled=true`）— **需 Chrome 手动**
- [x] 6.3 Cookie 实例 API/路径校验（`scripts/test_cookie_instances.py`）；完整 diagnose→Run **需 Chrome 手动**
- [x] 8.3 analyze 并行逻辑（`scripts/test_analyze_parallel.py`）；生产 wall-clock **需真实 LLM Run 对比**
- [x] 9.6 partial diagnose 降级 + max_modal skip stats（`test_source_diagnose` / `test_modal_quota` / `test_mixed_source_routing`）；混合源 wall-clock **需 Worker+Chrome 手动**
- [x] 验证完成后 `python scripts/sync_verification_tasks.py push`

## xhs-keyword-pipeline-subtasks

<!-- archive: openspec/changes/archive/2026-06-22-xhs-keyword-pipeline-subtasks/tasks.md -->

- [x] 5.2 执行含 xhs 任务，Run 详情见 keyword 子任务表；失败 keyword 可重跑 — **需 Chrome 手动**
- [x] 5.3 合作方设置 xhs/黑猫超时后，子任务 `timeout_sec` 与重跑行为符合预期 — **需 Chrome 手动**
- [x] 验证完成后 `python scripts/sync_verification_tasks.py push`

## task-detail-subtask-control

<!-- archive: openspec/changes/archive/2026-06-23-task-detail-subtask-control/tasks.md -->

- [x] 6.1 运行含 xhs+heimao 任务：子任务 Tab 见分源状态与三阶段用时；暂停 xhs 后 heimao 仍跑 — **需 Chrome 手动**
- [x] 6.2 终止任务后 Run 为 stopped、无「继续」；暂停后可继续 — **需 Chrome 手动**
- [x] 6.3 详情源数据/情报 Tab 运行中刷新无闪屏 — **需 UI 手动**
- [x] 6.4 验证完成后 `python scripts/sync_verification_tasks.py push`

## xhs-credential-pool-rotation

<!-- change: openspec/changes/xhs-credential-pool-rotation/tasks.md -->

- [x] 6.1 升级后确认 `acc-default` 自动迁移，旧监测仍可跑
- [x] 6.2 数据源 xhs：添加第二账号 → 打开登录页 → 扫码 → 完成保存 → diagnose 通过
- [x] 6.3 多 keyword Run：子任务 Tab 见账号列交替；单号 diagnose 失败自动换号
- [x] 6.4 监测 Run 进行中 `login/start` 返回 409
- [ ] 验证完成后 `python scripts/sync_verification_tasks.py push`

## monitor-crawl-only-run

<!-- archive: openspec/changes/archive/2026-06-26-monitor-crawl-only-run/tasks.md -->

- [x] 6.1 勾选「仅爬取」执行混合源任务：Run 在 crawl 后结束，无 analyzing 阶段，Chrome 已释放
- [x] 6.2 对同一任务点「增量 AI」：intel 正常写入，与 crawl_only Run 解耦
- [x] 6.3 crawl_only + 有限 task_timeout：爬取可用时间大于非 crawl_only 同配置
- [x] 验证完成后 `python scripts/sync_verification_tasks.py push`

## heimao-scroll-load

<!-- archive: openspec/changes/archive/2026-06-26-heimao-scroll-load/tasks.md -->

- [x] 4.1 监测任务黑猫下拉加载：日志见「黑猫下拉加载」与「本轮: +N」，采集量显著高于 60 条
- [x] 验证完成后 `python scripts/sync_verification_tasks.py push`

## pipeline-analyze-during-crawl

<!-- change: openspec/changes/pipeline-analyze-during-crawl/tasks.md -->

- [ ] 7.4 Run 内 investigation 与 analyze wall-clock 重叠：日志见 `[analyze_drain] batch`，progress 有 `analyze_drain.done` 增长
- [ ] 7.4 定时兜底：长时间无新勘察 batch 时见 `[analyze_drain] timer`
- [ ] 7.4 crawling 态手动「增量 AI」可用，「全量 AI」禁用并 tooltip 说明
- [ ] 7.4 Run 收尾无 remaining detail 时日志「during-crawl drain 已完成，跳过收尾 AI 分析」
