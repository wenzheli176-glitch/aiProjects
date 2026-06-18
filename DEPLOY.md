# 舆情爬虫 - 部署指南

## 快速部署（目标机器）

### 第一步：安装 Python 依赖

```powershell
cd 舆情爬虫-pkg
pip install -r requirements.txt
python -m patchright install chromium
```

### 第二步：配置与 Cookie

1. 复制 `config.json.example` → `config.json`，填写 `MINIMAX_API_KEY`（或看板「大模型」页保存）。
2. **推荐**：启动后访问 **http://localhost:5000/?tab=cookies**，在 **Cookie 实例** Tab 粘贴各 Worker 的 Cookie JSON 并「诊断」。
3. **备选**：运行 `setup_cookies.bat`，按提示在 Chrome 中登录黑猫与小红书（导出至 `credentials/*_cookies.json`）。

Cookie 权威路径为 `monitor.workers.{source}.instances[].cookies_file`（默认与 `config.auth.{site}.cookies_file` 对齐）。

### 第三步：启动

```powershell
start.bat
# 或
python crawler_web.py
```

访问 **http://localhost:5000**

---

## 多 Chrome 端口与 Profile（Worker 模式）

默认 `monitor.workers.enabled=false`（单 Chrome、单进程，与旧版行为接近）。生产并行爬取可开启 Worker：

| 实例 | 默认 CDP 端口 | Profile 目录 | Cookie 文件 |
|------|---------------|--------------|-------------|
| heimao-0 | 9222 | `chrome_heimao_profile/` | `credentials/heimao_cookies.json` |
| xhs-0 | 9230 | `chrome_profiles/xhs_0/` | `credentials/xhs_cookies.json` |

在 `config.json` 中设置：

```json
"monitor": {
  "workers": {
    "enabled": true,
    "max_workers_total": 4,
    "heimao": { "instances": [{ "instance_id": "heimao-0", "cdp_port": 9222, ... }] },
    "xhs": { "max_instances": 1, "instances": [{ "instance_id": "xhs-0", "cdp_port": 9230, ... }] }
  },
  "run_state": { "claim_timeout_sec": 600, "heartbeat_interval_sec": 30 }
}
```

**注意：**

- 每个实例需 **独立** `cdp_port` + `user_data_dir`，勿与手工「采集调试」Tab 争用同一端口。
- Run 进行中 Worker 占用端口时，手工 `/api/crawl_*` 返回 **409**。
- 回滚并行：设 `monitor.workers.enabled=false` 并重启服务。

---

## Web 控制台 Tab

| Tab | 用途 |
|-----|------|
| 首页看板 | KPI、最近 Run |
| 监测任务 | 创建/执行监测、Run 历史 |
| **Cookie 实例** | 按 Worker 上传 Cookie、手动诊断；失效时顶栏红色横幅 |
| 采集调试 | 黑猫/小红书手工爬取（独立 CDP 9222） |
| 系统设置 | `config.json` 可视化编辑 |

监测 Run 等待登录时，**任意 Tab** 顶栏显示 `login_wait`；多 Worker 时聚合展示各实例 site/耗时。

---

## API 调用（简要）

```bash
# 运行状态（含 worker_states、login_wait）
curl http://localhost:5000/api/status

# Cookie 实例列表
curl http://localhost:5000/api/cookie-instances

# 执行监测（body 示例）
curl -X POST http://localhost:5000/api/monitor/run \
  -H "Content-Type: application/json" \
  -d "{\"task_id\": 1}"

# 停止当前 Run（设 stop_requested）
curl -X POST http://localhost:5000/api/stop
```

完整 REST 说明见 `docs/API对接说明.md`。

---

## Cookie 失效怎么办？

1. 打开 **Cookie 实例** Tab → 对应源/实例 → 粘贴新 Cookie → **保存** → **诊断**（需管理员）。
2. 或删除 `credentials/*_cookies.json` 后重新 `setup_cookies.bat` / 扫码登录。
3. 若 profile 登录态损坏，可删除对应 `chrome_*_profile/` 或 `chrome_profiles/xhs_*` 后重登。

---

## 依赖说明

- Python 3.12+
- Google Chrome（系统已安装）
- patchright 浏览器驱动（`python -m patchright install chromium`）
