# -*- coding: utf-8 -*-
import re
import os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
idx = open(os.path.join(base, 'templates', 'index.html'), encoding='utf-8').read()
dash = open(os.path.join(base, 'templates', 'dashboard.html'), encoding='utf-8').read()


def extract_panel(html, panel_id):
    m = re.search(
        r'<div id="' + panel_id + r'" class="panel[^"]*">(.*?)</div>\s*(?=\s*<!--|\s*<div id="panel-|\s*</div>\s*</div>\s*<script)',
        html,
        re.S,
    )
    if not m:
        return ''
    return m.group(1)


cfg = re.search(
    r'<div class="card config-panel" id="config-panel".*?</div>\s*(?=<div class="controls")',
    idx,
    re.S,
)
cfg_html = cfg.group(0) if cfg else ''
cfg_html = re.sub(r'<div class="config-tab"[^>]*data-tab="analysis"[^>]*>.*?</div>\s*', '', cfg_html)
cfg_html = re.sub(r'<div class="config-section" id="cfg-analysis".*?</div>\s*', '', cfg_html, flags=re.S)
cfg_html = cfg_html.replace('id="config-panel"', 'id="system-config-panel"')
cfg_html = cfg_html.replace('style="display:none"', '')

controls = re.search(
    r'<div class="controls">.*?</div>\s*<div class="card">\s*<h2>.*?</h2>.*?launchChrome.*?</div>\s*',
    idx,
    re.S,
)
ctrl_html = controls.group(0) if controls else ''

logs = (
    '<div class="card" style="margin-top:16px">'
    '<h2 style="font-size:14px;color:#94a3b8;margin-bottom:8px">运行日志</h2>'
    '<div class="logs" id="logs"></div></div>'
)

mon_defaults = '''
<div class="card" style="margin-top:16px">
<h2>监测默认</h2>
<p class="muted">新建监测任务的默认来源与超时</p>
<div id="monDefaultSources" class="source-checks"></div>
<div class="field-grid">
  <div class="field"><label>默认采集页数</label><input id="monDefaultPages" type="number" min="1" value="2"></div>
  <div class="field"><label>任务超时(秒)</label><input id="monTaskTimeout" type="number" min="60" value="7200"></div>
</div>
<div class="btn-group admin-only-save">
  <button class="btn btn-primary btn-sm" onclick="saveMonitorDefaults()">保存监测默认</button>
</div>
</div>
'''

panels = {
    'intel': extract_panel(dash, 'panel-intel'),
    'partners': extract_panel(dash, 'panel-partners'),
    'tasks': extract_panel(dash, 'panel-tasks'),
    'analysis': extract_panel(dash, 'panel-analysis'),
    'crawl': ctrl_html,
    'system': cfg_html + mon_defaults,
    'sources': (
        '<div class="card"><p id="sourcesNotice" class="muted" style="margin-bottom:12px"></p>'
        '<div id="sourcesList"></div></div>'
    ),
}

nav = ''.join([
    '<a href="#" data-tab="intel">监测看板</a>',
    '<a href="#" data-tab="partners">合作方</a>',
    '<a href="#" data-tab="tasks">监测任务</a>',
    '<a href="#" data-tab="sources">数据源</a>',
    '<a href="#" data-tab="crawl">采集调试</a>',
    '<a href="#" data-tab="system">系统设置</a>',
    '<a href="#" data-tab="analysis">大模型</a>',
])

status_m = re.search(r'<div class="status-bar">.*?</div>\s*<div class="login-wait-banner".*?</div>', idx, re.S)
if status_m:
    status_block = status_m.group(0)
else:
    status_block = ''
status_block = status_block.replace("toggleConfig()", "App.switchAppTab('system')")

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>舆情情报平台</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>
<div class="header">
  <h1>舆情情报平台</h1>
  <div class="admin-bar">
    <span id="adminStatus" class="muted">…</span>
    <div id="adminLoginBox" class="admin-bar" style="display:none">
      <input id="adminPassword" type="password" placeholder="管理员口令">
      <button class="btn btn-gray btn-sm" onclick="adminLogin()">登录</button>
    </div>
    <button id="adminLogoutBtn" class="btn btn-gray btn-sm" style="display:none" onclick="adminLogout()">退出</button>
    <a href="/docs/intel-api" target="_blank" style="color:#93c5fd;font-size:12px;margin-left:8px">API</a>
  </div>
</div>
''' + status_block + '''
<div class="app-shell">
  <nav class="app-nav">''' + nav + '''</nav>
  <main class="app-main">
'''

for key, content in panels.items():
    active = ' active' if key == 'intel' else ''
    html += '    <div id="panel-' + key + '" class="app-panel' + active + '">' + content + '</div>\n'

html += logs + '''
  </main>
</div>
<div class="toast" id="toast"></div>
<script src="/static/app-core.js"></script>
<script src="/static/panel-intel.js"></script>
<script src="/static/panel-crawl.js"></script>
<script src="/static/app-sources.js"></script>
</body>
</html>
'''

out = os.path.join(base, 'templates', 'app.html')
open(out, 'w', encoding='utf-8').write(html)
print('wrote', out, len(html))
