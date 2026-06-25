## 1. 后端推荐 API

- [x] 1.1 新增 `intel/partner_cohort_suggest.py`：`list_distinct_cohorts()`、LLM prompt、已有 cohort 归一化、mock 模式
- [x] 1.2 可选联网搜索模块（配置 `web_search_enabled`；失败降级 LLM-only）
- [x] 1.3 `POST /api/partners/suggest-cohort` in `intel/api.py`
- [x] 1.4 `config.py` / `config.json.example`：`analysis.partner_cohort_suggest.*`

## 2. 前端

- [x] 2.1 合作方表单：「获取推荐」按钮 + 候选 chip 列表（点击填入 `pCohort`，不自动保存）
- [x] 2.2 展示「已有·N 家」/「新建」标签；cohort 输入框仍可留空保存
- [x] 2.3 `field-labels.json` / 表单 hint 说明 cohort 开放标签与合并作用

## 3. 测试与文档

- [x] 3.1 `scripts/test_partner_cohort_suggest.py`：已有 cohort 优先排序、归一化、空 name 400
- [x] 3.2 更新 `docs/API对接说明.md` suggest-cohort 接口
- [x] 3.3 更新 `代码说明.md` partner cohort 推荐章节

## 4. 手动验证

- [x] 4.1 新建「蔚来汽车」→ 获取推荐 → 点选 cohort → 再建「小鹏汽车」同 cohort → 执行 list 任务验证 keyword 合并（`scripts/test_partner_cohort_acceptance.py` 验收 keyword 合并 + suggest 只读）
- [x] 4.2 cohort 留空保存成功；编辑时不自动覆盖已填 cohort（同上脚本 + UI 逻辑：chip 仅填入 input，edit 不触发推荐）
