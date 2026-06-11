/* 首页看板 */
async function loadHomeDashboard() {
  const grid = document.getElementById('homeKpiGrid');
  const runsBody = document.getElementById('homeRunsBody');
  if (!grid) return;
  try {
    const d = await api('/api/dashboard/summary');
    if (!d.ok) throw new Error(d.msg || '加载失败');
    const src = d.by_source || {};
    grid.innerHTML =
      '<div class="kpi-card" onclick="App.navigateIntel({relevance_min:\'\'})"><div class="kpi-value">' + (d.intel_total || 0)
      + '</div><div class="kpi-label">情报总数</div></div>'
      + '<div class="kpi-card" onclick="App.navigateIntel({relevance_min:\'medium\'})"><div class="kpi-value">' + (d.intel_medium_plus || 0)
      + '</div><div class="kpi-label">medium+</div></div>'
      + '<div class="kpi-card" onclick="App.navigateIntel({})"><div class="kpi-value">' + (d.intel_today || 0)
      + '</div><div class="kpi-label">今日新增情报</div></div>'
      + '<div class="kpi-card" onclick="App.switchAppTab(\'tasks\')"><div class="kpi-value">' + (d.tasks_running || 0)
      + '</div><div class="kpi-label">运行中任务</div></div>'
      + '<div class="kpi-card" onclick="App.navigateIntel({source:\'heimao\'})"><div class="kpi-value">' + (src.heimao || 0)
      + '</div><div class="kpi-label">黑猫情报</div></div>'
      + '<div class="kpi-card" onclick="App.navigateIntel({source:\'xhs\'})"><div class="kpi-value">' + (src.xhs || 0)
      + '</div><div class="kpi-label">小红书情报</div></div>'
      + '<div class="kpi-card" onclick="App.switchAppTab(\'tasks\')"><div class="kpi-value">' + (d.tasks_failed_recent || 0)
      + '</div><div class="kpi-label">近7日失败任务</div></div>';

    const runs = d.recent_runs || [];
    if (!runsBody) return;
    if (!runs.length) {
      runsBody.innerHTML = '<tr><td colspan="5" class="empty">暂无 Run</td></tr>';
      return;
    }
    runsBody.innerHTML = runs.map(function(r) {
      const total = (r.crawl_duration_ms || 0) + (r.analyze_duration_ms || 0);
      return '<tr class="clickable-row" onclick="openRunFromHome(' + r.id + ',' + r.task_id + ')">'
        + '<td>#' + r.id + '</td><td>任务 #' + r.task_id + '</td><td>' + esc(r.status || '') + '</td>'
        + '<td>' + fmtDuration(total) + '</td><td>' + fmtTime(r.started_at) + '</td></tr>';
    }).join('');
  } catch (e) {
    grid.innerHTML = '<p class="msg-err">' + esc(e.message) + '</p>';
  }
}

function openRunFromHome(runId, taskId) {
  App.setQuery({ tab: 'tasks', run_id: String(runId), task_id: taskId ? String(taskId) : null });
  App.switchAppTab('tasks');
}
