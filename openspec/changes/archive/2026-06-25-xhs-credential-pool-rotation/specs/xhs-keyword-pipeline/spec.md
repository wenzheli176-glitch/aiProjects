## MODIFIED Requirements

### Requirement: 单 keyword 流水线

系统 SHALL 对每个 xhs keyword 依次执行：列表爬取 → list_triage → 同页 investigation，再进入下一 keyword；不得等全部 keyword list 完成后再批量 investigation 重搜。每个 keyword 开始前 MUST 完成账号池 pick 与 Worker profile rebind。

#### Scenario: Worker keyword_pipeline phase

- **当** 监测任务含 xhs 且 crawl_mode 为 list_first
- **则** `crawl_work_queue` MUST 为每个 keyword 入队 phase=`keyword_pipeline`
- **且** 执行 `run_xhs_keyword_pipeline` 在同页 DOM 完成需勘察条目的弹窗详情

#### Scenario: 跳过批量 xhs investigation

- **当** xhs 已全部经 keyword 流水线处理
- **则** `_run_post_list_crawl_phases` MUST NOT 对 xhs 再 enqueue 批量 investigation

#### Scenario: keyword 绑定账号后执行

- **WHEN** Worker claim keyword_pipeline 项
- **THEN** MUST 先 `pick_account_for_keyword` 并 rebind
- **AND** MUST 将 `account_id` 写入 keyword run stats_json 再进入 list 阶段

## ADDED Requirements

### Requirement: Keyword 子任务账号追踪

系统 SHALL 在 `monitor_keyword_runs.stats_json` 持久化 `account_id`（及可选 `account_label`），供子任务 Tab 与排障使用。

#### Scenario: 子任务 Tab 展示账号

- **WHEN** 用户查看 xhs keyword 子任务行
- **THEN** MAY 显示执行该 keyword 的账号 label（若 API 提供）
