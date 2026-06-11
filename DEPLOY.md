# 舆情爬虫 - 部署指南 v1.0

## 快速部署（目标机器）

### 第一步：安装Python依赖
打开PowerShell，运行：
```powershell
cd舆情爬虫-pkg
pip install -r requirements.txt
python -m patchright install chromium
```

### 第二步：提取登录Cookie
运行 `setup_cookies.bat`，按提示在Chrome中登录黑猫投诉和小红书。

### 第三步：启动爬虫
运行 `start.bat`，然后访问 **http://localhost:5000**

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `crawler_web.py` | Flask主程序 |
| `templates/index.html` | Web管理面板 |
| `requirements.txt` | Python依赖 |
| `setup_cookies.bat` | Cookie提取工具 |
| `start.bat` | 一键启动 |
| `chrome_profile/` | 登录Cookie存储目录 |
| `DEPLOY.md` | 详细部署文档 |

---

## Web面板使用

访问 http://localhost:5000 后：
1. 点击"启动Chrome"按钮
2. 输入关键词（默认：小米）
3. 选择平台和页数
4. 点击"开始爬取"
5. 等待完成后下载CSV/JSON/TXT

---

## API调用（QClaw集成）

```bash
# 启动Chrome
curl -X POST http://localhost:5000/api/launch

# 爬取黑猫投诉（2页含详情）
curl -X POST http://localhost:5000/api/crawl_heimao \
  -H "Content-Type: application/json" \
  -d "{\"keyword\":\"小米\",\"max_pages\":2,\"fetch_detail\":true}"

# 爬取小红书（3页）
curl -X POST http://localhost:5000/api/crawl_xhs \
  -H "Content-Type: application/json" \
  -d "{\"keyword\":\"小米\",\"max_pages\":3}"

# 导出结果
curl -O http://localhost:5000/api/export_all?format=csv
```

---

## QClaw Skill 集成

在目标机器的QClaw中创建一个Skill调用爬虫API：

1. 将爬虫作为后台服务运行
2. 在QClaw Skill中用HTTP请求调用API
3. 或者用 `subprocess` 直接调用Python脚本

---

## Cookie失效怎么办？

1. 删除 `chrome_profile/Network/Cookies*` 文件
2. 重新运行 `setup_cookies.bat`
3. 再次手动登录

---

## 依赖说明

- Python 3.12+
- Google Chrome（系统已安装）
- patchright浏览器驱动（首次运行自动安装）
