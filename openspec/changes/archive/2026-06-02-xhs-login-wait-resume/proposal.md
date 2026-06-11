## 背景

小红书在未登录状态下无法正常访问笔记详情页，但当前爬虫在 `fetch_detail=true` 时仍会继续执行，导致任务“跑完”却得到空详情或登录墙页面数据。用户需要在检测到未登录时暂停任务、引导完成登录后自动续跑；在未勾选详情时，仍允许仅抓取搜索列表。

## 变更内容

- 为小红书爬取引入 **WAITING_LOGIN** 任务状态：检测到未登录时暂停，不写入无效详情结果。
- **仅当 `fetch_detail=true`** 时强制登录门禁；`fetch_detail=false` 时仅抓列表，沿用现有宽松策略。
- 登录检测增强：Cookie（`web_session` / `webId`）+ 页面文案 + 可选详情探针。
- 等待登录期间：打日志、更新 `/api/status`、前端展示“等待登录”；提供打开登录页；轮询直至通过或超时。
- 登录成功后 **从当前步骤自动续跑**（搜索/滚动/详情），无需用户重新点「开始」。
- 新增或扩展小红书登录诊断信息（与黑猫对称）。

## 能力范围

### 新增能力

- `xhs-login-gate`：小红书登录检测、等待登录、超时失败、续跑语义及与 `fetch_detail` 的分支规则。

### 修改的能力

- （无既有 `openspec/specs/` 基线）

## 影响范围

- `crawler_web.py`：`crawl_xhs`、`S` 状态机、`/api/status`
- `auth_utils.py`：小红书 `check_login`、Cookie 校验、详情页探针
- `config.json` / `config.py`：`auth.xhs` 等待超时、轮询间隔、关键 Cookie 名
- `templates/index.html`：等待登录 UI、状态展示
- 文档：`docs/如何获取登录凭证.md` 补充小红书等待登录流程
