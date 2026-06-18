## 1. 超时预算核心

- [x] 1.1 新增 `compute_monitor_deadlines()`（`intel/timeout_budget.py` 或 `runner` 内模块级函数），实现 design D1 公式
- [x] 1.2 `run_monitor_task` 改用该函数设置 `crawl_deadline` / `deadline` / `analysis_reserve`
- [x] 1.3 区分 `_timeout_message(phase, ...)`：crawl → `爬取阶段超时（crawl_budget_sec=N）`；analyze → `分析阶段超时` / `任务超时`
- [x] 1.4 失败时 `update_task_status` 写入 `progress.reason`（`crawl_timeout` / `timeout`）

## 2. 配置与文档

- [x] 2.1 `config.py` DEFAULT + `config.json.example`：新增 `monitor.min_crawl_timeout_sec`（默认 1800）；`analysis_timeout_sec` 改为 3600
- [x] 2.2 修正生产 `config.json` 中 `analysis_timeout_sec`（若仍为 7200 则改为 3600）
- [x] 2.3 配置加载或 runner 启动时对过大 `analysis_timeout_sec` 打 WARN 日志
- [x] 2.4 更新 `代码说明.md` monitor 超时章节；`field-labels.json` 如有 monitor 超时字段则补标签

## 3. 测试

- [x] 3.1 新增 `scripts/test_monitor_timeout_budget.py`：7200/7200、7200/3600、短 task 边界
- [x] 3.2 运行 `python scripts/test_monitor_timeout_budget.py` 通过

## 4. 手动验证

- [x] 4.1 双源 Worker 任务（heimao + xhs）：routine 爬取应能超过 5 分钟并进入 list_triage / investigation（若 triage 有入队则见 xhs 弹窗）
- [x] 4.2 故意将 `min_crawl_timeout_sec` 设为 60 且 `task_timeout_sec=120`，验证失败 reason 为 `crawl_timeout` 且 error_message 含 crawl_budget（单元测试覆盖 budget + message + progress.reason）
