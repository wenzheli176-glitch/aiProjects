## Context

`crawler_web.crawl_heimao` / `crawl_xhs` 按 `max_pages=M` 循环采集。黑猫在第 2 页起若本页 `seen` 去重后零新增会 `break`（硬编码）；小红书无早停，每轮 scroll 后解析 DOM，跑满 M 轮。监测 `list_first` 与调试 API 均调用同一函数，故早停改爬虫层即可全覆盖。

用户确认：「无最新」= **分页见底**；XHS 页底有 `- THE END -`；第 1 页零条需防加载失败；早停可关、按源配置；主痛点为**日常调试白跑页数**。

## Goals / Non-Goals

**Goals:**

- 各源可配置 `early_stop.enabled` 与策略参数，默认开启。
- 黑猫：连续空页（无新链接）停止；第 1 页空页重试后再判定。
- 小红书：检测 `- THE END -`（主）；滚动饱和（辅）；第 1 轮保护。
- 早停日志：`early_stop: <source> · reason=<code> · stopped_at=i/M`。
- `max_pages` 文档与 spec 明确为**上限**，实际 `page` 可为 1..i（i≤M）。

**Non-Goals:**

- DB 增量 / `insert_raw unchanged` 驱动的早停。
- 修改 MonitorTask API、runner 分页控制、investigation 流程。
- 自动识别 XHS end DOM class（以文案为主，selector 可选扩展）。

## Decisions

### 1. 早停逻辑放在 `crawler_web.py`

**选择**：在 `crawl_heimao` / `crawl_xhs` 循环内实现，读取 `config.heimao.early_stop` / `config.xhs.early_stop`。

**理由**：CrawlAdapter 仅薄封装；login_gate 已有首屏等待，不重复造轮。

**替代**：runner 分页回调 — 需重构 API，超出范围。

### 2. 黑猫策略：连续空页 + 第 1 页保护

| 参数 | 默认 | 含义 |
|------|------|------|
| `enabled` | `true` | 总开关 |
| `min_pages` | `1` | 至少采集页数（早停不得早于 i < min_pages） |
| `empty_pages_threshold` | `1` | 连续几页 `new_count==0` 触发停止 |
| `protect_first_page` | `true` | 第 1 页零新增不计入连续空页 |
| `empty_page_retry` | `1` | 第 1 页零新增时重做搜索/等待次数 |

实现要点：

- 每页结束统计 `new_count`（现有逻辑）。
- `protect_first_page` 且 `p==1` 且 `new_count==0`：调用既有 `_redo_heimao_search` 或等待，最多 `empty_page_retry` 次；仍 0 则 **停止**（视为无结果关键词），**不**继续翻第 2 页空跑。
- `p >= 2`：空页计数 +=1，达阈值且 `p >= min_pages` → `break`，`reason=empty_page`。

**替代**：仅保留现有 `p>1 && new==0` — 不足：第 1 页空仍翻页、不可配置。

### 3. 小红书策略：end 标志 + 滚动饱和

| 参数 | 默认 | 含义 |
|------|------|------|
| `enabled` | `true` | 总开关 |
| `min_pages` | `1` | 至少完成轮数 |
| `protect_first_page` | `true` | 第 1 轮不因 end/饱和单独早停（须已有 note-item 或已过 login_gate） |
| `end_texts` | `["- THE END -", "THE END"]` | body 或 locator 可见文案 |
| `end_selectors` | `[]` | 可选 CSS，与文案 OR |
| `saturation_rounds` | `2` | 连续饱和轮数 |

每轮「第 i/M 页」流程：

1. scroll 预热（现有 `scroll_*`）。
2. **`_xhs_has_end_marker(page)`**：`page.locator('text=- THE END -').is_visible()` 或 `end_texts` 任一匹配；若 true 且 `i >= min_pages` 且非「第 1 轮保护误触」→ stop `reason=end_marker`。
3. 解析 note-item，统计 `new_count`、记录 `item_count`。
4. 若 `new_count==0` 且 `item_count` 未较上轮增加 → 饱和计数 +1；否则归零。
5. 饱和计数 ≥ `saturation_rounds` 且 `i >= min_pages` → stop `reason=scroll_saturated`。

新增小函数 `_xhs_has_end_marker(page, cfg)` 于 `crawler_web.py` 或 `login_gate.py`（只读 DOM，不改 login 流程）。

### 4. `enabled: false` 行为

关闭时与**变更前**一致：黑猫保留现有硬编码 `p>1 && new==0` 还是完全跑满 M？

**决定**：`enabled: false` 时 **完全跑满 M**（黑猫也去掉硬编码 break），便于 A/B 对比；文档说明。若担心回归，可在 tasks 中保留「false 时等同旧 heimao 行为」—— proposal 说默认 true，false 为显式调试模式。

实际上 user might want false = old behavior. Safer: `enabled: false` → no early stop at all (heimao runs all M pages even if empty on page 2). That's a behavior change for heimao when disabled vs current. Document in migration.

**Revised**: `enabled: false` → 禁用一切早停（含现有 heimao `p>1` break），跑满 M；`enabled: true` → 新策略。Migration note in tasks.

### 5. 配置与 UI

- `config.py` `DEFAULT_CONFIG` 增加 `heimao.early_stop`、`xhs.early_stop` 默认值。
- `config.json.example` 同步。
- `field_labels.py` / `field-labels.json` 增加字段说明。
- `source_profiles.py`：profile 白名单增加顶层 `early_stop` 对象键 **或** 扁平化子键 — **选择**：profile PATCH 接受 `early_stop` 嵌套对象（merge 进 `config.heimao.early_stop`），与 normalize 块一致；GET profile 返回当前 early_stop。

### 6. RawRecord `page` 字段

早停于第 i 页时，已写入记录的 `page` 仍为 1..i，允许 i < M。MODIFIED spec 中 `page` 为「实际采集页码」，上限 M。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| XHS `- THE END -` 文案或 DOM 变更 | `end_texts` 可配置；`saturation_rounds` 兜底 |
| 第 1 页加载慢误判为空 | `empty_page_retry` + 复用 `heimao_wait_if_search_empty` / `_xhs_wait_note_items` |
| `enabled: false` 与旧 heimao 早停行为不一致 | 文档说明；验证项对比 |
| 黑猫「页面过短 continue」不计空页 | 过短页不计入连续空页计数，避免网络抖动误停 |

## Migration Plan

1. 部署后 `config.json` 无 `early_stop` 时使用 DEFAULT（enabled true）。
2. 需跑满 M 页时设 `heimao.early_stop.enabled=false` 与 `xhs.early_stop.enabled=false`。
3. 无 DB 迁移。

## Open Questions

- （已关闭）XHS end 文案 → `- THE END -`
- profile UI 是否在本变更做表单，或仅 config.json + field_labels — **建议 tasks 先做 config/API，UI 可选简化（JSON 或后续 console 变更）**
