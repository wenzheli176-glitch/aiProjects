## 1. ignore_before 扩展

- [x] 1.1 新增 `intel/ignore_before.py`（should_skip / resolve / filter_raw / log parts）
- [x] 1.2 `insert_raw_records` 列表入库前过滤 + `raw_skipped_ignore_before` 统计
- [x] 1.3 `investigation.py` 勘察队列与 row 判定跳过
- [x] 1.4 runner / worker / keyword_pipeline 传入 `resolve_ignore_before`
- [x] 1.5 `scripts/test_ignore_before_filter.py`

## 2. 控制台列表分页

- [x] 2.1 `static/list-pagination.js` + `app.css` 样式
- [x] 2.2 `panel-raw.js` / `panel-intel.js` 集成分页与 URL query
- [x] 2.3 `templates/app.html` 挂载 `#rawListPagination` / `#intelListPagination`
- [x] 2.4 `intel/api.py` 默认 page_size=20、上限 200

## 3. 黑猫见底早停

- [x] 3.1 `config.py` / `config.json.example`：`heimao.early_stop.end_texts` 含 `暂无更多`
- [x] 3.2 `crawl_early_stop.py` heimao 默认与 body 检测
- [x] 3.3 `scripts/test_heimao_scroll.py` 断言 end_texts

## 4. 验证

- [x] 4.1 单元测试通过
- [ ] 4.2 用户验证：源数据/情报分页、ignore_before 日志、黑猫「暂无更多」早停
