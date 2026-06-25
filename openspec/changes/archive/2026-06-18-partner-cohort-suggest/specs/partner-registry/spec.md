## ADDED Requirements

### Requirement: 行业 cohort 推荐

系统 SHALL 提供 cohort 推荐 API，根据合作方名称（及可选别名）返回行业 cohort 候选列表；cohort 仍为开放标签，用户 MUST 手动点选确认后方可填入表单，创建合作方时 industry_cohort 允许为空。

#### Scenario: 请求 cohort 推荐

- **当** 调用 `POST /api/partners/suggest-cohort` 且 `name` 非空
- **则** 响应 MUST 含 `candidates` 数组（最多 `max_candidates` 条）
- **且** 每条 MUST 含 `cohort` 字符串与 `source`（`existing` 或 `llm`）
- **且** MUST 返回 `existing_cohorts`（当前 DB 去重非空 cohort 列表）

#### Scenario: 优先已有 cohort

- **当** DB 中存在非空 `industry_cohort` 值
- **则** LLM 推断 MUST 在 prompt 中注入该列表并要求优先 verbatim 选用
- **且** 后处理 MUST 将 LLM 输出映射到已有 cohort（若语义接近）
- **且** `source=existing` 的候选 MUST 排在 `source=llm` 且 `is_new=true` 之前

#### Scenario: 联网搜索辅助推断

- **当** `analysis.partner_cohort_suggest.web_search_enabled=true` 且网络可用
- **则** 系统 MAY 检索品牌公开行业信息并纳入 LLM 上下文
- **且** 搜索失败或超时时 MUST 降级为仅 LLM/已有 cohort，不得阻塞 API（返回部分候选或空 candidates + existing_cohorts）

#### Scenario: 用户点选确认

- **当** 用户在合作方表单点击某 cohort 候选
- **则** MUST 仅填入 cohort 输入框
- **且** MUST NOT 自动提交保存
- **且** 用户仍可将 cohort 清空后保存

#### Scenario: cohort 为空创建合作方

- **当** `POST /api/partners` 未提供 industry_cohort 或为空字符串
- **则** MUST 成功创建 partner
- **且** shared-crawl-pool MUST 仍对该 partner 使用 `partner:{id}` fallback 分组

#### Scenario: 推荐 API 禁用

- **当** `analysis.partner_cohort_suggest.enabled=false`
- **则** API MUST 返回 `ok=false` 或空 candidates 且文档说明功能关闭
- **且** UI MUST 隐藏或禁用「获取推荐」控件

## MODIFIED Requirements

### Requirement: 行业 cohort

系统 SHALL 为 Partner 支持 `industry_cohort` 字段，用于共享爬取的关键词合并与调度分组；该字段为**开放标签**（非受控枚举），MAY 为空；系统 SHOULD 在录入时提供 cohort 推荐辅助（见「行业 cohort 推荐」），但 MUST NOT 自动写入。

#### Scenario: 创建合作方含 cohort

- **当** 用户提交 industry_cohort（如「新能源整车」）
- **则** 系统必须持久化该字符串
- **且** shared-crawl-pool 必须按 cohort 精确匹配合并 keyword_batch

#### Scenario: 未设 cohort

- **当** industry_cohort 为空
- **则** 该 partner 单独成组（cohort fallback 为 `partner:{id}`）
- **且** 不得阻止创建或更新合作方
