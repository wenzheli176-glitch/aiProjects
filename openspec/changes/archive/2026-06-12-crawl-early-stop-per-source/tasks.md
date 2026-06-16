## 1. 配置与默认值

- [x] 1.1 在 `config.py` DEFAULT 增加 `heimao.early_stop`、`xhs.early_stop`（含 `- THE END -` 默认文案）
- [x] 1.2 同步 `config.json.example` 与 `field_labels.py` / `static/field-labels.json`
- [x] 1.3 `source_profiles.py` 白名单支持 profile GET/PATCH `early_stop` 嵌套对象

## 2. 黑猫早停（crawler_web.py）

- [x] 2.1 抽取读取 `early_stop` 配置的小 helper（或内联），`enabled=false` 时不早停、跑满 M
- [x] 2.2 实现连续空页计数（`empty_pages_threshold`），替换硬编码 `p>1 && new==0`
- [x] 2.3 第 1 页零新增：`empty_page_retry` + 复用 `_redo_heimao_search` / 既有等待；仍空则停止
- [x] 2.4 页面过短 `continue` 不计入连续空页；早停日志 `early_stop: heimao · reason=empty_page · stopped_at=i/M`

## 3. 小红书早停（crawler_web.py）

- [x] 3.1 实现 `_xhs_has_end_marker(page, early_stop_cfg)`（`- THE END -` + 可配置 texts/selectors）
- [x] 3.2 每轮 scroll 后检测 end 标志；`i >= min_pages` 时触发 `reason=end_marker`
- [x] 3.3 实现滚动饱和：跟踪 `item_count` 与 `new_count`，连续 `saturation_rounds` 轮触发 `reason=scroll_saturated`
- [x] 3.4 第 1 轮 `protect_first_page`：无 note-item 时走既有 `xhs_wait_if_search_blocked`，不因 end/饱和误停

## 4. 测试与文档

- [x] 4.1 添加 `scripts/test_early_stop.py`（或扩展现有测试）：mock/轻量断言 heimao 空页计数与 xhs end 文案匹配逻辑
- [x] 4.2 更新 `代码说明.md`：`max_pages` 为上限、early_stop 配置说明
- [x] 4.3 `openspec/verification-pending.md` 登记 § crawl-early-stop-per-source 手动验证项

## 5. 手动验证（§ crawl-early-stop-per-source）

- [ ] 5.1 黑猫调试爬取：关键词结果不足 M 页时，日志出现 `early_stop · empty_page` 且实际页数 < M
- [ ] 5.2 黑猫：`early_stop.enabled=false` 时行为为跑满 M（或第 2 页起仍继续，与 spec 一致）
- [ ] 5.3 小红书调试爬取：滚至 `- THE END -` 后出现 `early_stop · end_marker`
- [ ] 5.4 小红书：短关键词在 end 未出现前，饱和兜底可停止（可选对照 `saturation_rounds=1`）
- [ ] 5.5 验证完成后执行 `python scripts/sync_verification_tasks.py push`
