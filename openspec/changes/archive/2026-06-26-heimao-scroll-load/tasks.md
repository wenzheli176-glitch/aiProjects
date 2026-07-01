## 1. 滚动加载

- [x] 1.1 新增 `heimao_scroll.py`：`heimao_scroll_load_batch`（滚到底 / 容器 / 像素）
- [x] 1.2 `crawl_heimao` 每轮先滚动再解析 DOM，移除 URL 翻页与 `heimao_pagination.py`
- [x] 1.3 日志：`黑猫下拉加载: N 次滚动`、`本轮: +X (DOM 链接 Y, 累计 Z)`

## 2. 配置与适配器

- [x] 2.1 `config.py` / `config.json.example`：heimao scroll 参数与 `early_stop.saturation_rounds`
- [x] 2.2 `source_profiles.py` 白名单增加 scroll 键
- [x] 2.3 `intel/sources/heimao.py`：移除 `keywords[:3]`，支持 `max_keywords_per_partner`

## 3. 早停

- [x] 3.1 `crawl_early_stop.py`：heimao 第 1 轮 `empty_page`；复用 `scroll_saturated`
- [x] 3.2 单元测试：`scripts/test_heimao_scroll.py`、`scripts/test_early_stop.py` 更新

## 4. 验证

- [x] 4.1 用户验证：监测任务黑猫可下拉加载，采集量显著高于 60 条
