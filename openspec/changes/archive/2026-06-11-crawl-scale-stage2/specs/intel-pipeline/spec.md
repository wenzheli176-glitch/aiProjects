## ADDED Requirements

### Requirement: 部分字段 NormalizedRecord

系统 SHALL 允许 NormalizedRecord 在 list-phase 缺少 body、published_at 等字段仍进入管道。

#### Scenario: 列表档归一化

- **当** raw 的 crawl_phase=list 且 payload 仅有 title 与 link
- **则** NormalizeAdapter 必须产出有效 NormalizedRecord
- **且** 不得因 body 为空丢弃 raw

#### Scenario: 勘察后补全

- **当** investigation 更新 payload
- **则** 归一化 MUST 合并 list 与 detail 字段
- **且** content_hash 变更必须触发增量重分析

### Requirement: 分级 AnalyzePipeline

系统 SHALL 区分 List Triage（轻量）、Routine Analyze（可选）、Investigation Analyze（完整）三档 LLM 调用。

#### Scenario: Routine 跳过完整 LLM

- **当** raw 仅 list-phase 且 triage_relevance=noise
- **则** 不得调用完整 AnalyzePipeline
- **且** 可仅持久化 triage 结果或写轻量 intel 行（可配置）

#### Scenario: Investigation 必须完整分析

- **当** raw crawl_phase=detail 且来自 investigation 队列
- **则** 必须调用完整 AnalyzePipeline
- **且** 必须写入标准 intel_records

## MODIFIED Requirements

### Requirement: PartnerMatcher 源无关匹配

系统 SHALL 在归一化之后、AI 分析之前，用 PartnerMatcher 将候选记录关联到 `partner_id`，匹配依据为主名称、别名与可选监测词。

#### Scenario: 别名命中

- **当** NormalizedRecord 的 title 或 body 包含某合作方别名
- **则** 必须设置 `partner_id` 与 `subject_hits` 包含该别名
- **且** 在 shared-crawl-pool 模式下 MUST 支持一条 raw 匹配多个 partner 并分别展开 intel

#### Scenario: 无匹配仍保留

- **当** 规则层无法匹配任何 partner
- **则** 记录仍必须进入 triage/分析候选池
- **且** 高召回策略下不得因未匹配而丢弃 raw 数据
