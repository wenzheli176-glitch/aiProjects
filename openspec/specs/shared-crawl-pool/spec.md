# shared-crawl-pool Specification

## Purpose
TBD - created by archiving change crawl-scale-stage2. Update Purpose after archive.
## Requirements
### Requirement: 行业关键词批次共享爬取

系统 SHALL 在 `crawl_mode=list_first` 时，按 **数据源 × 行业关键词批次** 执行爬取，而非按合作方 × 数据源重复爬取。

#### Scenario: 同行业关键词合并

- **当** 监测任务包含多个 `industry_cohort` 相同的合作方
- **则** 系统必须合并其 name、aliases、monitor_keywords 为去重后的 keyword_batch
- **且** 每个 source 对每个 keyword_batch 仅调用一次 CrawlAdapter

#### Scenario: Raw 池不预绑定合作方

- **当** 共享爬取写入 raw_records
- **则** `partner_id` 可为 NULL
- **且** 必须写入 `crawl_phase=list`

#### Scenario: 同 task 内 URL 去重

- **当** 不同 keyword 命中相同 URL
- **则** 必须按现有 dedup_key UPSERT，不得重复 INSERT

### Requirement: 多方 PartnerMatcher

系统 SHALL 在归一化后对每条 list raw 执行 `match_all_partners`，允许一条 raw 关联多个合作方。

#### Scenario: 多别名命中

- **当** 列表 title/snippet 同时命中合作方 A、B 的别名
- **则** 必须记录两者均为 subject_hits
- **且** 后续 intel 写入必须为每个命中合作方各生成记录（或等价的多 partner 展开）

#### Scenario: 无匹配仍保留

- **当** 规则层无法匹配任何 partner
- **则** raw 仍必须保留在池中
- **且** 必须进入 list_triage 候选（高召回）

### Requirement: legacy 兼容模式

系统 SHALL 支持 `crawl_mode=legacy` 保留现有 partner × source 串行爬取行为。

#### Scenario: 旧任务默认 legacy

- **当** monitor_tasks 无 crawl_mode 字段或值为 legacy
- **则** MonitorRunner 必须按现有双重循环执行
- **且** 行为与变更前一致

