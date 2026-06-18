## ADDED Requirements

### Requirement: xhs investigation 弹窗配额（Run 级）

系统 SHALL 支持 `xhs.investigation_detail.max_modal_per_run`；单次 Run 内所有 xhs Worker 实例 **共享**同一配额计数器。

#### Scenario: 配额内正常勘察

- **当** 弹窗成功且 Run 级 `investigation_modal_done < max_modal_per_run`
- **则** MUST 递增 Run 级计数并继续（Orchestrator 或 DB 原子更新）

#### Scenario: 配额超限 skip

- **当** Run 级计数已达上限且队列仍有 pending xhs 项
- **则** MUST skip 剩余项，reason `modal_quota_exceeded`
- **且** MUST 写入 `investigation_skipped_quota`
- **且** MUST NOT 将整个 Run 标记为 failed

#### Scenario: 多 xhs 实例不倍增配额

- **当** 配置 2 个 xhs Worker 实例且 `max_modal_per_run=200`
- **则** 全 Run 弹窗总数 MUST NOT 超过 200（非每实例 200）

### Requirement: list_triage 作用范围

list_triage MUST 仅处理 list_first 源的 list-phase raw。

#### Scenario: 仅 triage xhs list raw

- **当** Run 含 heimao legacy 与 xhs list
- **则** `run_list_triage` MUST 仅传入 `crawl_phase=list` 的 raw
- **且** heimao `crawl_phase=legacy` raw MUST NOT 进入 list_triage

### Requirement: heimao legacy 免重复 investigation

系统 SHALL 避免 heimao routine 已 fetch_detail 的 raw 再次进入 investigation。

#### Scenario: heimao fetch_detail 已抓详情

- **当** heimao legacy routine 且 task.fetch_detail=true
- **且** raw payload 已含有效详情 body
- **则** `build_investigation_queue` MUST NOT 将该 raw 入队

#### Scenario: heimao 无 triage 不入队

- **当** raw 无 `list_triage.triage_relevance`
- **则** MUST NOT 进入 investigation_queue

## MODIFIED Requirements

### Requirement: 勘察队列与增量重点详情

系统 SHALL 将满足阈值且为增量的条目加入 investigation 队列，并仅对队列 URL 执行 `fetch_detail=true` 补爬。

#### Scenario: 进入勘察队列条件

- **当** `needs_investigation=true`
- **且** `triage_relevance` 为 medium 或 high（或 P0 合作方规则强制）
- **且** raw 尚无 detail-phase payload 或 content_hash 已变更
- **且** 非 heimao legacy 已 fetch_detail 情形
- **则** 必须加入 investigation_queue

#### Scenario: 勘察补详情

- **当** 执行 investigation_crawl（经 Worker queue）
- **则** CrawlAdapter 必须仅对队列 URL 抓详情
- **且** 必须更新同 dedup_key raw，设置 `crawl_phase=detail`
- **且** 黑猫走 login_gate + new_page；小红书走搜索页弹窗（禁止 goto explore）
- **且** xhs 弹窗 MUST 受 Run 级 `max_modal_per_run` 约束

#### Scenario: 勘察后深分析

- **当** investigation_crawl 成功更新 raw
- **则** 必须送入完整 AnalyzePipeline

#### Scenario: 勘察失败状态

- **当** xhs 弹窗失败
- **则** queue 项为 `failed`；统计 `investigation_failed`；Run 仍可 analyze

#### Scenario: 配额 skip 后 analyze

- **当** xhs 项因 quota skip
- **则** raw MUST 仍可按 list_triage 结果进入 analyze（partial body）
- **且** Run MUST NOT failed

#### Scenario: 配额 skip 状态

- **当** xhs 弹窗因 `modal_quota_exceeded` 被 skip
- **则** investigation_queue 对应项 MUST 为 `skipped`
- **且** MUST 计入 `investigation_skipped_quota`
