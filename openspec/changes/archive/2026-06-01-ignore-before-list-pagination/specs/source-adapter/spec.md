## MODIFIED Requirements

### Requirement: max_pages 跨源统一语义

系统 SHALL 将 MonitorTask 与 CrawlAdapter 的 `max_pages` 参数定义为 **结果采集页数上限 M**：对 heimao 与 xhs 均为最多 M 次滚动采集轮次；两源 MUST 使用一致的「第 i/M 页」日志与 RawRecord `page` 字段（`page` 为实际采集轮次，1≤page≤i≤M）。当 `early_stop.enabled=true` 且检测到列表见底时，实际轮次 i MAY 小于 M。

#### Scenario: 黑猫 end 标志早停

- **WHEN** `config.heimao.early_stop.enabled=true`
- **且** 滚动后页面出现 `end_texts` 中任一条（默认 MUST 含 `暂无更多`）或匹配 `end_selectors`
- **且** 当前轮次 i ≥ `min_pages`
- **THEN** 必须停止后续滚动轮次
- **且** 日志必须包含 `early_stop: heimao · reason=end_marker · stopped_at=i/M`
