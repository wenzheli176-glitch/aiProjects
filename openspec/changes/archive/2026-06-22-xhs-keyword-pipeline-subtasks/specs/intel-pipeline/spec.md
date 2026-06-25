## ADDED Requirements

### Requirement: 合作方 legacy 爬取超时

黑猫 legacy_crawl（合作方×源）SHALL 应用 `resolve_source_timeout_sec('heimao', [], partner=partner)` 作为单合作方爬取 wall-clock 上限。

#### Scenario: legacy 超时停止

- **当** 单合作方 heimao crawl 超过合作方或全局 heimao 超时
- **则** `timeout_check` MUST 返回 true 并停止该合作方 crawl

### Requirement: xhs 跳过批量 post-list investigation

`_run_post_list_crawl_phases` SHALL 仅对 **未** 经 keyword 流水线处理的 list_first 源（当前为除 xhs 外）执行批量 triage + investigation。

#### Scenario: xhs 已 pipeline 化

- **当** 任务 sources 含 xhs 且 xhs 使用 keyword_pipeline
- **则** post 阶段 MUST 跳过 xhs，不得再 build_investigation_queue 后批量重搜 xhs
