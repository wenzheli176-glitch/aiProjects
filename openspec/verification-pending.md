# OpenSpec 待验证清单

本文件为**唯一待办验证入口**：各已归档 change 中未勾选的「手动验证」项汇总于此。  
验证完成后在本文件勾选 `- [x]`，再运行同步脚本写回对应 archive 的 `tasks.md`。

```bash
# 查看进度
python scripts/sync_verification_tasks.py status

# 将本文件已勾选项同步到各 archive .../tasks.md
python scripts/sync_verification_tasks.py push

# 从 archive 重新扫描未验证项（保留本文件已勾选状态）
python scripts/sync_verification_tasks.py scan
```

---

## monitor-timeout-unify-xhs-pages

<!-- archive: openspec/changes/archive/2026-06-09-monitor-timeout-unify-xhs-pages/tasks.md -->

- [x] 4.1 将 `monitor.task_timeout_sec` 临时设为 60，创建 2 合作方 × 2 源任务，确认约 60s 后任务 `failed` 且 error 含「任务超时」
- [x] 4.2 单次 xhs 爬取 `max_pages=2`，确认日志为「2页」且出现「XHS第 1/2 页」「XHS第 2/2 页」，第 1 页前有滚动
- [x] 4.3 确认 heimao `max_pages=2` 行为与变更前一致（回归）
- [x] 4.4 确认 `reanalyze` 在大量 raw 数据下不因 60s 测试配置被误杀（使用正常 timeout 或单独测 reanalyze）

## partner-risk-intel

<!-- archive: openspec/changes/archive/2026-06-09-partner-risk-intel/tasks.md -->

- [x] 7.1 创建 2 个合作方（含别名），手动触发 heimao+xhs 监测任务，确认 raw_records 入库
- [x] 7.2 未登录 heimao/xhs 时：确认 login_gate 等待登录后续跑，任务不写入无效详情（沿用既有门禁）
- [x] 7.3 xhs 详情：确认弹窗路径抓取成功，无 App 墙误报为有效正文
- [x] 7.4 AI 分析完成后：看板默认展示 medium+，API 可按 source/partner 过滤
- [x] 7.5 导出 JSON/Excel，确认每条含 `source` 与 `schema_version`

## unified-console-source-admin

<!-- archive: openspec/changes/archive/2026-06-09-unified-console-source-admin/tasks.md -->

- [x] 7.1 访问 `/` 切换全部 Tab，功能与整合前等价（情报筛选、创建任务、手工爬取）
- [x] 7.2 `/dashboard` redirect 正常；监测任务 waiting_login 时任意 Tab 见横幅
- [x] 7.3 未登录：可 run 监测、不可 PATCH sources / POST partners
- [x] 7.4 管理员登录：可改源 enabled、xhs default_max_pages；保存后下次爬取生效
- [x] 7.5 采集调试 Tab：黑猫/XHS 手工爬 + 登录续跑 + 弹窗详情回归
- [x] 7.6 `admin.enabled=false` 本地模式写 API 仍可用（开发文档说明）

## intel-ux-normalize-prompts

<!-- archive: openspec/changes/archive/2026-06-10-intel-ux-normalize-prompts/tasks.md -->

- [x] 6.1 跑监测任务：看板三列时间正确；captured_at 早于 analyzed_at
- [x] 6.2 关闭 heimao `include_reply_in_body` 后重跑：body 变化可观测
- [x] 6.3 Prompt：新建版本→激活→重跑 AI→intel.prompt_version 为新 id
- [x] 6.4 全站抽样：数据源/系统/大模型字段均为中文（英文键）
- [x] 6.5 导出 Excel/JSON 含三时间列

## monitor-runs-schedule-incremental

<!-- archive: openspec/changes/archive/2026-06-10-monitor-runs-schedule-incremental/tasks.md -->

- [x] 9.1 同一 task 执行两次：第二次 raw 不变则 skip LLM；新 URL 仅分析新增
- [x] 9.2 模拟 payload 变化（如 heimao 回复增多）：raw updated_at 刷新且 intel 覆盖重写
- [x] 9.3 全量重分析：intel 清空后全部重写；run 记录 full_replace
- [x] 9.4 启用定时（短 cron 测试）：到点自动 run；运行中重叠 → skipped_overlap
- [x] 9.5 Run 详情：分源 crawl/analyze ms 与 token 与日志量级一致
- [x] 9.6 Schedule UI：选「工作日 09:00」保存重载后 cron 与预览正确

## monitor-run-history-ui

<!-- archive: openspec/changes/archive/2026-06-01-monitor-run-history-ui/tasks.md -->

- [x] 6.1 创建或选用已有监测任务，执行至少 2 次 manual run，点击「历史」展开：默认显示 ≤5 条，摘要列完整
- [x] 6.2 当 total>5 时点击「加载更多」，较旧 Run 追加显示且不丢失已加载行
- [x] 6.3 点击某 Run 行：右侧切换详情，分源 timing/token 与 stats 与 API JSON 一致；「返回编辑」恢复任务表单
- [x] 6.4 失败 Run：`error_message` 可见；`skipped_overlap` run 状态展示正确
- [x] 6.5 确认全程无 `alert()` 展示 Run 历史；Ctrl+F5 后行为正常

## console-ux-overhaul

<!-- archive: openspec/changes/archive/2026-06-11-console-ux-overhaul/tasks.md -->

- [x] 7.1 访问 `/` 默认 home；看板 KPI 点击跳转 intel 且 filter 正确
- [x] 7.2 情报：筛选在上、详情页 `intel_id` 深链、返回保留筛选；导出当前筛选全量
- [x] 7.3 源数据：列表无 payload 全文；详情页全文；导出 json/xlsx；跳转 intel
- [x] 7.4 合作方/任务 Modal 创建编辑；任务页全宽无右栏表单
- [x] 7.5 Run Drawer：展开历史、点击 Run、stats 含义可见；`run_id` 深链
- [x] 7.6 数据源 heimao/xhs Tab 切换保存生效
- [x] 7.7 窄屏（≤900px）主要 Tab 可用；全站浅色无深色残留块
- [x] 7.8 `/dashboard` → home；login_wait 横幅各 Tab 仍可见
