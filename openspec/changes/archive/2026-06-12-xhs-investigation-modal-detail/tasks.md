## 1. xhs_detail 扩展

- [x] 1.1 实现 `find_note_item_for_url(page, url)`：解析 note_id、在 `note_item_selector` 内匹配链接
- [x] 1.2 实现 `scroll_search_for_note(page, note_id, max_rounds)`（可选滚动查找，供定位与重搜复用）
- [x] 1.3 单元测试：URL 解析 + mock DOM 文本匹配（`scripts/test_xhs_investigation_modal.py`）

## 2. 勘察弹窗重写（crawler_web + adapter）

- [x] 2.1 重写 `fetch_xhs_details_by_urls`：弹窗路径；移除 goto explore 主逻辑
- [x] 2.2 支持 keyword 分组；从 queue/raw 传入 `_search_keyword`
- [x] 2.3 单条 DOM miss → skip + failed(`dom_not_found`)；批量 miss ≥ 阈值 → 重搜后再试
- [x] 2.4 `intel/sources/xhs.py` 传递 keyword；`intel/investigation.py` 合并 payload 与 status 对齐
- [x] 2.5 复用 `login_gate` / `is_xhs_detail_auth_failure`；弹窗间隔 `investigation_detail.between_detail_*`

## 3. 配置与文档

- [x] 3.1 `config.py` / `config.json.example` 增加 `xhs.investigation_detail.*`
- [x] 3.2 `field_labels` / `source_profiles` 暴露相关键（若经 profile 编辑）
- [x] 3.3 更新 `代码说明.md`；`openspec/verification-pending.md` 登记 § xhs-investigation-modal-detail

## 4. 手动验证（§ xhs-investigation-modal-detail）

- [ ] 4.1 list_first 监测：xhs investigation 日志无 goto explore，出现弹窗提取成功
- [ ] 4.2 故意使用列表中不存在的 URL：单条 `dom_not_found` skip，任务继续
- [ ] 4.3 同 keyword 连续 3+ miss：触发重搜日志，重搜后部分 URL 可定位
- [ ] 4.4 未登录 xhs：investigation 触发登录等待后续跑弹窗详情
- [ ] 4.5 验证完成后 `python scripts/sync_verification_tasks.py push`
