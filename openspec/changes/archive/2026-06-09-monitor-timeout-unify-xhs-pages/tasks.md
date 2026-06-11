## 1. MonitorRunner 任务超时

- [x] 1.1 在 `intel/runner.py` 的 `run_monitor_task` 入口读取 `monitor.task_timeout_sec`，记录 `deadline = time.monotonic() + timeout_sec`
- [x] 1.2 实现 `_check_timeout(task_id, log_fn)`：超时时设 `S.running=False`、写 `failed` 状态与 `error_message`（含秒数）、`progress.reason=timeout`
- [x] 1.3 在 partner×source 爬取循环每步开始前调用超时检查；超时则 `return` 并走 `finally` 释放锁
- [x] 1.4 在 `_run_analysis_phase` 每批 `analyze_candidates` 前调用超时检查；超时则中断分析
- [x] 1.5 确认 `reanalyze_monitor_task` 不应用上述超时逻辑

## 2. 小红书 max_pages 语义统一

- [x] 2.1 修改 `crawler_web.py` 的 `crawl_xhs`：起始日志改为「开始爬取小红书: %s %d页」（与黑猫一致）
- [x] 2.2 每页（含第 1 页）在采集前执行 `scroll_times_per_page` 滚动；移除「仅 p>1 滚动」分支
- [x] 2.3 保持循环日志「XHS第 %d/%d 页」；确认 raw 记录 `page` 字段为 1..max_pages
- [x] 2.4 确认 `intel/sources/xhs.py` 传递的 `max_pages` 无额外换算或「滚动次数」注释

## 3. 文档与 UI

- [x] 3.1 更新根目录 `代码说明.md`：移除「task_timeout_sec 未 enforcement」与「xhs max_pages 为滚动次数」已知限制；补充超时与页数语义说明
- [x] 3.2 看板 `templates/dashboard.html`：任务表单「页数」字段增加 tooltip/placeholder 说明对黑猫/小红书均为采集页数
- [x] 3.3 更新 `docs/API对接说明.md` 中 `max_pages` 字段说明（如已有）

## 4. 手动验证

- [x] 4.1 将 `monitor.task_timeout_sec` 临时设为 60，创建 2 合作方 × 2 源任务，确认约 60s 后任务 `failed` 且 error 含「任务超时」
- [x] 4.2 单次 xhs 爬取 `max_pages=2`，确认日志为「2页」且出现「XHS第 1/2 页」「XHS第 2/2 页」，第 1 页前有滚动
- [x] 4.3 确认 heimao `max_pages=2` 行为与变更前一致（回归）
- [x] 4.4 确认 `reanalyze` 在大量 raw 数据下不因 60s 测试配置被误杀（使用正常 timeout 或单独测 reanalyze）
