# 舆情爬虫 - 完整技术文档

## 系统架构

```
Flask Web服务 (localhost:5000)
  ├── Patchright (CDP连接Chrome)
  │     └── Chrome (调试端口9222)
  │           └── chrome_profile/ (Cookie持久化)
  ├── 黑猫投诉爬虫
  │     ├── 列表页：通过搜索框输入（绕过反爬）
  │     └── 详情页：新标签页 + JS提取innerText
  └── 小红书爬虫
        ├── 列表页：.note-item选择器
        └── 详情页：需要登录（当前未实现）
```

## 核心发现

### 黑猫投诉反爬
- 直接访问搜索URL被拦截，必须通过首页搜索框输入
- 详情页是SPA，同标签页goto不更新DOM，必须用new_page()
- Cookie需持久化在独立User Data目录

### 小红书反爬
- 详情页需要登录才能访问
- 列表页通过.scrollBy滚动触发动态加载
- 登录Cookie可复用（需手动提取）

## API接口

| 方法 | 路径 | 参数 |
|------|------|------|
| POST | /api/launch | - |
| POST | /api/crawl_heimao | keyword, max_pages, fetch_detail |
| POST | /api/crawl_xhs | keyword, max_pages |
| POST | /api/stop | - |
| GET | /api/status | - |
| GET | /api/results_heimao | - |
| GET | /api/results_xhs | - |
| GET | /api/export_heimao | format=csv/json/txt |
| GET | /api/export_xhs | format=csv/json/txt |
| GET | /api/export_all | format=csv/json/txt |
| POST | /api/clear | - |

## 数据字段

### 黑猫投诉
title, content, demand, merchant, problem, amount, reply, author, time, status, comments, link, page, source

### 小红书
title, content, time, author, likes, link, page, source

## 已知问题
- JS字符串中的\r会导致page.evaluate报错（已在代码中处理）
- 小红书详情页需要登录（计划实现）
- Cookie提取需手动（setup_cookies.bat辅助）
