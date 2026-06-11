let sources = [], partners = [], tasks = [], lastTaskId = null;
let aiLogTimer = null;
const RUN_HISTORY_LIMIT = 5;
const runHistoryState = {};
let expandedRunHistoryTaskId = null;
let selectedRunId = null;
let selectedRunTaskId = null;

function toastMsg(msg, isErr) {
  if (window.App && App.showToast) App.showToast(msg, isErr);
  else alert(msg);
}

function restoreHiddenForm(formId) {
  const fields = document.getElementById(formId);
  if (!fields) return;
  fields.classList.add('hidden-form-fields');
  fields.setAttribute('aria-hidden', 'true');
  document.body.appendChild(fields);
}

function mountHiddenForm(wrap, formId) {
  const mount = wrap.querySelector('.ui-modal-body');
  const fields = document.getElementById(formId);
  if (!mount || !fields) return;
  fields.classList.remove('hidden-form-fields');
  fields.setAttribute('aria-hidden', 'false');
  mount.appendChild(fields);
}

function intelFilterParams() {
  const params = new URLSearchParams();
  const task = document.getElementById('fTask');
  const partner = document.getElementById('fPartner');
  const source = document.getElementById('fSource');
  const rel = document.getElementById('fRelevance');
  if (task && task.value) params.set('task_id', task.value);
  if (partner && partner.value) params.set('partner_id', partner.value);
  if (source && source.value) params.set('source', source.value);
  if (rel && rel.value) params.set('relevance_min', rel.value);
  return params;
}

function syncIntelFiltersFromQuery() {
  const q = App.readQuery();
  const set = function(id, key) {
    const el = document.getElementById(id);
    if (el && q.get(key) != null && q.get(key) !== '') el.value = q.get(key);
  };
  set('fTask', 'task_id');
  set('fPartner', 'partner_id');
  set('fSource', 'source');
  set('fRelevance', 'relevance_min');
  if (q.get('task_id')) lastTaskId = parseInt(q.get('task_id'), 10) || lastTaskId;
}

function showIntelList() {
  const list = document.getElementById('intelListView');
  const detail = document.getElementById('intelDetailView');
  if (list) list.style.display = '';
  if (detail) detail.style.display = 'none';
}

function onIntelTabActivate() {
  syncIntelFiltersFromQuery();
  const intelId = App.getQuery('intel_id');
  if (intelId) showIntelDetail(parseInt(intelId, 10));
  else {
    showIntelList();
    loadRecords();
  }
}

async function onTasksTabActivate() {
  await loadTasks();
  const runId = App.getQuery('run_id');
  if (runId) {
    const taskId = App.getQuery('task_id');
    await openRunDrawer(parseInt(runId, 10), taskId ? parseInt(taskId, 10) : null);
  }
}

const RUN_GLOSSARY_KEYS = [
  'trigger', 'analyze_mode', 'status', 'started_at', 'finished_at',
  'crawl_duration_ms', 'analyze_duration_ms', 'error_message',
  'raw_new', 'raw_updated', 'raw_unchanged', 'intel_written', 'intel_replaced', 'intel_skipped',
  'crawl_ms', 'analyze_ms', 'prompt_tokens', 'completion_tokens', 'total_tokens',
];

const RUN_STATS_KEYS = [
  'raw_new', 'raw_updated', 'raw_unchanged', 'intel_written', 'intel_replaced', 'intel_skipped',
];

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  let data = null;
  const text = await r.text();
  if (text) {
    try { data = JSON.parse(text); } catch (e) { /* 非 JSON 响应 */ }
  }
  if (!r.ok) {
    const err = new Error((data && data.msg) || ('HTTP ' + r.status));
    err.status = r.status;
    err.data = data;
    throw err;
  }
  return data || {};
}

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
}

function sourceTag(s) {
  const cls = s === 'heimao' ? 'tag-heimao' : (s === 'xhs' ? 'tag-xhs' : '');
  const label = s === 'heimao' ? '黑猫' : (s === 'xhs' ? '小红书' : s);
  return `<span class="tag ${cls}">${esc(label)}</span>`;
}

function relTag(r) {
  return `<span class="tag tag-${r || 'medium'}">${esc(r || '-')}</span>`;
}

function sentimentTag(label, score) {
  const cls = { negative: 'tag-off', neutral: 'tag-medium', positive: 'tag-on' };
  const cn = { negative: '负面', neutral: '中性', positive: '正面' };
  const lbl = label || 'neutral';
  const sc = score != null && score !== '' ? ` (${Number(score).toFixed(2)})` : '';
  return `<span class="tag ${cls[lbl] || 'tag-medium'}">${cn[lbl] || esc(lbl)}${sc}</span>`;
}

function statusTag(s) {
  return `<span class="tag tag-status ${esc(s || 'queued')}">${esc(s || '-')}</span>`;
}

function partnerName(id) {
  const p = partners.find(x => x.id === id);
  return p ? p.name : ('#' + id);
}

function partnerNames(ids) {
  return (ids || []).map(id => partnerName(id)).join('、') || '-';
}

function fmtTime(s) {
  return (s || '').replace('T', ' ').slice(0, 16) || '-';
}

function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById('panel-' + tab.dataset.panel).classList.add('active');
      stopAiLogPoll();
      if (tab.dataset.panel === 'partners') loadPartners();
      if (tab.dataset.panel === 'tasks') loadTasks();
      if (tab.dataset.panel === 'analysis') {
        loadAnalysisConfig();
        refreshAiLogTaskSelect();
        loadAnalysisLogs();
        startAiLogPoll();
      }
    });
  });
}

async function loadSources() {
  const d = await api('/api/sources');
  sources = d.sources || [];
  const opts = '<option value="">全部</option>' + sources.map(s =>
    `<option value="${esc(s.source_id)}">${esc(s.label)}</option>`).join('');
  const fsel = document.getElementById('fSource');
  if (fsel) fsel.innerHTML = opts;
  const frsel = document.getElementById('frSource');
  if (frsel) frsel.innerHTML = opts.replace('全部', '全部');
  renderSourceChecks();
}

function renderSourceChecks(selectedIds) {
  const srcBox = document.getElementById('tSourceChecks');
  if (!srcBox) return;
  const selected = selectedIds || sources.map(s => s.source_id);
  srcBox.innerHTML = sources.map(s =>
    `<label><input type="checkbox" name="taskSource" value="${esc(s.source_id)}" ${selected.includes(s.source_id) ? 'checked' : ''}> ${esc(s.label)}</label>`
  ).join('');
}

function renderPartnerChecks(selectedIds) {
  const box = document.getElementById('tPartnerChecks');
  const enabled = partners.filter(p => p.enabled);
  if (!enabled.length) {
    box.innerHTML = '<span class="muted">暂无启用的合作方，请先在「合作方管理」中添加</span>';
    return;
  }
  box.innerHTML = enabled.map(p =>
    `<label><input type="checkbox" name="taskPartner" value="${p.id}" ${selectedIds.includes(p.id) ? 'checked' : ''}> ${esc(p.name)}</label>`
  ).join('');
}

function refreshPartnerSelects() {
  const fp = document.getElementById('fPartner');
  fp.innerHTML = '<option value="">全部</option>' + partners.map(p =>
    `<option value="${p.id}">${esc(p.name)}</option>`).join('');
  if (typeof refreshRawFilters === 'function') refreshRawFilters();
}

function refreshTaskSelect() {
  const sel = document.getElementById('fTask');
  const cur = sel.value;
  sel.innerHTML = '<option value="">全部任务</option>' + tasks.map(t =>
    `<option value="${t.id}">#${t.id} ${esc(t.name || '')} (${t.status})</option>`).join('');
  if (cur) sel.value = cur;
  else if (lastTaskId) sel.value = String(lastTaskId);
  if (typeof refreshRawFilters === 'function') refreshRawFilters();
}

function refreshAiLogTaskSelect() {
  const sel = document.getElementById('aiLogTask');
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = '<option value="">全部（最新）</option>' + tasks.map(t =>
    `<option value="${t.id}">#${t.id} ${esc(t.name || '')} (${t.status})</option>`).join('');
  if (cur) sel.value = cur;
  else if (lastTaskId) sel.value = String(lastTaskId);
}

function aiLogStatusTag(status) {
  const cls = { ok: 'tag-on', mock: 'tag-med', failed: 'tag-off' };
  const cn = { ok: '成功', mock: 'Mock', failed: '失败' };
  return `<span class="tag ${cls[status] || ''}">${cn[status] || esc(status)}</span>`;
}

function formatUsageSummary(job) {
  if (!job) return '暂无分析记录';
  const u = job.usage || {};
  return [
    `作业 #${job.id}`,
    `状态 ${job.status}`,
    `模型 ${job.model || '-'}`,
    `API ${u.api_calls || 0} 次`,
    `Mock ${u.mock_batches || 0} 批`,
    `失败 ${u.failed_batches || 0} 批`,
    `tokens ${u.total_tokens || 0} (in ${u.prompt_tokens || 0} / out ${u.completion_tokens || 0})`,
    `情报 ${job.processed_count || 0} 条`,
    job.finished_at ? `完成 ${fmtTime(job.finished_at)}` : `更新 ${fmtTime(job.updated_at)}`,
  ].join(' · ');
}

async function loadAnalysisLogs() {
  const sel = document.getElementById('aiLogTask');
  const summaryEl = document.getElementById('aiUsageSummary');
  const body = document.getElementById('aiLogBody');
  if (!body) return;
  try {
    const params = new URLSearchParams({ limit: '80' });
    const taskId = sel ? sel.value : '';
    if (taskId) params.set('task_id', taskId);
    const d = await api('/api/analysis/logs?' + params.toString());
    if (summaryEl) summaryEl.textContent = formatUsageSummary(d.latest_job);
    const logs = (d.logs || []).slice().reverse();
    if (!logs.length) {
      body.innerHTML = '<tr><td colspan="9" class="empty">暂无批次日志</td></tr>';
      return;
    }
    body.innerHTML = logs.map(l => `<tr>
      <td>${fmtTime(l.created_at)}</td>
      <td>${l.batch_index || '-'}</td>
      <td>${esc(l.partner_name || '-')}</td>
      <td>${aiLogStatusTag(l.status)}</td>
      <td>${l.item_count || 0}</td>
      <td>${l.latency_ms || 0}ms</td>
      <td>${l.prompt_tokens || 0} / ${l.completion_tokens || 0} / ${l.total_tokens || 0}</td>
      <td>${l.items_written || 0}</td>
      <td class="truncate" title="${esc(l.error_message || l.model || '')}">${esc(l.error_message || l.model || '-')}</td>
    </tr>`).join('');
  } catch (e) {
    if (summaryEl) summaryEl.textContent = '加载失败: ' + (e.message || '');
  }
}

function startAiLogPoll() {
  stopAiLogPoll();
  aiLogTimer = setInterval(loadAnalysisLogs, 4000);
}

function stopAiLogPoll() {
  if (aiLogTimer) {
    clearInterval(aiLogTimer);
    aiLogTimer = null;
  }
}

async function loadPartners() {
  const d = await api('/api/partners');
  partners = d.partners || [];
  refreshPartnerSelects();
  renderPartnerChecks([]);
  const body = document.getElementById('partnerTableBody');
  if (!partners.length) {
    body.innerHTML = '<tr><td colspan="8" class="empty">暂无合作方，点击「添加合作方」创建</td></tr>';
    return;
  }
  body.innerHTML = partners.map(p => `<tr>
    <td>${p.id}</td>
    <td><b>${esc(p.name)}</b></td>
    <td class="truncate" title="${esc((p.aliases||[]).join('、'))}">${esc((p.aliases||[]).join('、') || '-')}</td>
    <td class="truncate" title="${esc((p.exclude_words||[]).join('、'))}">${esc((p.exclude_words||[]).join('、') || '-')}</td>
    <td class="truncate" title="${esc((p.monitor_keywords||[]).join('、'))}">${esc((p.monitor_keywords||[]).join('、') || '-')}</td>
    <td><span class="tag ${p.enabled ? 'tag-on' : 'tag-off'}">${p.enabled ? '启用' : '停用'}</span></td>
    <td>${fmtTime(p.updated_at)}</td>
    <td class="actions">
      <button class="btn btn-gray btn-sm" onclick="openPartnerModal(${p.id})">编辑</button>
      <button class="btn btn-gray btn-sm" onclick="togglePartner(${p.id})">${p.enabled ? '停用' : '启用'}</button>
      <button class="btn btn-red btn-sm" onclick="deletePartner(${p.id})">删除</button>
    </td>
  </tr>`).join('');
}

function resetPartnerForm() {
  document.getElementById('editPartnerId').value = '';
  document.getElementById('pName').value = '';
  document.getElementById('pAliases').value = '';
  document.getElementById('pExclude').value = '';
  document.getElementById('pMonitorKw').value = '';
  document.getElementById('pNotes').value = '';
  document.getElementById('pEnabled').checked = true;
}

function editPartner(id) {
  const p = partners.find(x => x.id === id);
  if (!p) return;
  document.getElementById('editPartnerId').value = id;
  document.getElementById('pName').value = p.name || '';
  document.getElementById('pAliases').value = (p.aliases || []).join(', ');
  document.getElementById('pExclude').value = (p.exclude_words || []).join(', ');
  document.getElementById('pMonitorKw').value = (p.monitor_keywords || []).join(', ');
  document.getElementById('pNotes').value = p.notes || '';
  document.getElementById('pEnabled').checked = !!p.enabled;
}

function openPartnerModal(id) {
  if (id) editPartner(id); else resetPartnerForm();
  UiShell.modal({
    title: id ? '编辑合作方 #' + id : '添加合作方',
    bodyHtml: '',
    wide: true,
    confirmLabel: '保存',
    cancelLabel: '取消',
    onMount: function(wrap) { mountHiddenForm(wrap, 'partnerFormFields'); },
    onClose: function() { restoreHiddenForm('partnerFormFields'); },
    onConfirm: function() { return savePartner(); },
  });
}

async function savePartner() {
  const name = document.getElementById('pName').value.trim();
  if (!name) { toastMsg('请输入名称', true); return false; }
  const payload = {
    name,
    aliases: document.getElementById('pAliases').value.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    exclude_words: document.getElementById('pExclude').value.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    monitor_keywords: document.getElementById('pMonitorKw').value.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    notes: document.getElementById('pNotes').value.trim(),
    enabled: document.getElementById('pEnabled').checked,
  };
  const editId = document.getElementById('editPartnerId').value;
  let d;
  try {
    if (editId) {
      d = await api('/api/partners/' + editId, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      d = await api('/api/partners', { method: 'POST', body: JSON.stringify(payload) });
    }
  } catch (e) {
    toastMsg(e.message || '保存失败', true);
    return false;
  }
  if (!d.ok) { toastMsg(d.msg || '保存失败', true); return false; }
  resetPartnerForm();
  await loadPartners();
  await loadTasks();
  toastMsg('合作方已保存');
  return true;
}

async function togglePartner(id) {
  const p = partners.find(x => x.id === id);
  if (!p) return;
  await api('/api/partners/' + id, { method: 'PUT', body: JSON.stringify({ ...p, enabled: !p.enabled }) });
  loadPartners();
}

async function deletePartner(id) {
  const p = partners.find(x => x.id === id);
  const ok = await UiShell.confirm('确定删除合作方「' + (p ? p.name : id) + '」？', '删除合作方');
  if (!ok) return;
  try {
    const d = await api('/api/partners/' + id, { method: 'DELETE' });
    if (!d.ok) { toastMsg('删除失败', true); return; }
    loadPartners();
    loadTasks();
    toastMsg('已删除');
  } catch (e) {
    toastMsg(e.message || '删除失败', true);
  }
}

function fmtDuration(ms) {
  if (ms == null || ms === '') return '-';
  const s = Math.round(Number(ms) / 1000);
  if (s < 60) return s + 's';
  const m = Math.floor(s / 60);
  return m + 'm' + (s % 60) + 's';
}

function runFieldMeta(key) {
  if (window.FieldLabels && FieldLabels.meta) return FieldLabels.meta(key);
  return { label: key, help: '' };
}

function runFieldLabel(key) {
  const m = runFieldMeta(key);
  return m.label + ' (' + key + ')';
}

function runTriggerLabel(t) {
  return { manual: '手动', schedule: '定时' }[t] || t || '-';
}

function runModeLabel(m) {
  return { incremental: '增量', full_replace: '全量' }[m] || m || '-';
}

function sourceLabel(sid) {
  const s = sources.find(x => x.source_id === sid);
  if (s) return s.label;
  return sid === 'heimao' ? '黑猫' : (sid === 'xhs' ? '小红书' : sid);
}

function buildRunDetailHtml(run, task) {
  const totalMs = (run.crawl_duration_ms || 0) + (run.analyze_duration_ms || 0);
  let html = '<div class="run-detail-drawer">';
  html += '<div class="run-detail-overview">'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('status')) + '</span><span class="v">' + statusTag(run.status) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('trigger')) + '</span><span class="v">' + esc(runTriggerLabel(run.trigger)) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('analyze_mode')) + '</span><span class="v">' + esc(runModeLabel(run.analyze_mode)) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">总耗时</span><span class="v">' + fmtDuration(totalMs) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('started_at')) + '</span><span class="v">' + fmtTime(run.started_at) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('finished_at')) + '</span><span class="v">' + fmtTime(run.finished_at) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('crawl_duration_ms')) + '</span><span class="v">' + fmtDuration(run.crawl_duration_ms) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('analyze_duration_ms')) + '</span><span class="v">' + fmtDuration(run.analyze_duration_ms) + '</span></div>'
    + '</div>';
  html += '<h4 class="run-detail-section">统计指标</h4>' + renderRunDetailStats(run.stats);
  html += '<h4 class="run-detail-section">分源耗时</h4>' + renderRunDetailTiming(run.timing_by_source);
  html += '<h4 class="run-detail-section">Token 用量</h4>' + renderRunDetailToken(run.token_usage);
  if (run.error_message) {
    html += '<div class="run-detail-error"><strong>' + esc(runFieldMeta('error_message').label) + '</strong><br>' + esc(run.error_message) + '</div>';
  }
  html += '<details class="run-detail-glossary"><summary>字段说明</summary><dl>';
  html += RUN_GLOSSARY_KEYS.map(function(key) {
    const m = runFieldMeta(key);
    const help = m.help ? esc(m.help) : '—';
    return '<dt>' + esc(runFieldLabel(key)) + '</dt><dd>' + help + '</dd>';
  }).join('');
  html += '</dl></details></div>';
  return html;
}

async function openRunDrawer(runId, taskId) {
  if (window.FieldLabels && FieldLabels.load) await FieldLabels.load();
  let d;
  try {
    d = await api('/api/monitor/runs/' + runId);
  } catch (e) {
    toastMsg(e.message || '加载失败', true);
    return;
  }
  if (!d.ok || !d.run) { toastMsg(d.msg || '加载失败', true); return; }
  const resolvedTaskId = taskId || d.run.task_id;
  const task = tasks.find(function(x) { return x.id === resolvedTaskId; });
  selectedRunId = runId;
  selectedRunTaskId = resolvedTaskId;
  renderTaskTable();
  App.setQuery({ tab: 'tasks', run_id: runId, task_id: resolvedTaskId || null }, true);
  UiShell.drawer({
    title: 'Run #' + runId + (task && task.name ? ' · ' + task.name : ''),
    bodyHtml: buildRunDetailHtml(d.run, task),
    width: '720px',
    onClose: function() {
      selectedRunId = null;
      selectedRunTaskId = null;
      renderTaskTable();
      App.setQuery({ run_id: null }, true);
    },
  });
}

async function selectRun(runId, taskId) {
  await openRunDrawer(runId, taskId);
}

function renderRunDetailStats(stats) {
  stats = stats || {};
  return '<div class="run-detail-stats-grid">' + RUN_STATS_KEYS.map(function(key) {
    const m = runFieldMeta(key);
    return '<div class="run-detail-stat"><div class="num">' + (stats[key] != null ? stats[key] : 0)
      + '</div><div class="lbl">' + esc(m.label) + '</div>'
      + (m.help ? '<div class="help">' + esc(m.help) + '</div>' : '') + '</div>';
  }).join('') + '</div>';
}

function renderRunDetailTiming(timing) {
  timing = timing || {};
  const ids = Object.keys(timing);
  if (!ids.length) return '<p class="muted">无分源数据</p>';
  const rows = ids.map(function(sid) {
    const t = timing[sid] || {};
    return '<tr><td>' + sourceTag(sid) + '</td>'
      + '<td>' + fmtDuration(t.crawl_ms) + '</td>'
      + '<td>' + fmtDuration(t.analyze_ms) + '</td>'
      + '<td>' + (t.raw_new || 0) + '</td>'
      + '<td>' + (t.raw_updated || 0) + '</td>'
      + '<td>' + (t.intel_written || 0) + '</td></tr>';
  }).join('');
  return '<table class="run-detail-table"><thead><tr>'
    + '<th>来源</th><th>' + esc(runFieldMeta('crawl_ms').label) + '</th>'
    + '<th>' + esc(runFieldMeta('analyze_ms').label) + '</th>'
    + '<th>' + esc(runFieldMeta('raw_new').label) + '</th>'
    + '<th>' + esc(runFieldMeta('raw_updated').label) + '</th>'
    + '<th>' + esc(runFieldMeta('intel_written').label) + '</th>'
    + '</tr></thead><tbody>' + rows + '</tbody></table>';
}

function renderRunDetailToken(usage) {
  usage = usage || {};
  const bySource = usage.by_source || {};
  const ids = Object.keys(bySource);
  if (!ids.length && !usage.total) return '<p class="muted">无 Token 数据</p>';
  const rows = ids.map(function(sid) {
    const t = bySource[sid] || {};
    return '<tr><td>' + sourceTag(sid) + '</td>'
      + '<td>' + (t.prompt_tokens || 0) + '</td>'
      + '<td>' + (t.completion_tokens || 0) + '</td>'
      + '<td>' + (t.total_tokens || 0) + '</td></tr>';
  }).join('');
  const total = usage.total || {};
  return '<table class="run-detail-table"><thead><tr>'
    + '<th>来源</th><th>' + esc(runFieldMeta('prompt_tokens').label) + '</th>'
    + '<th>' + esc(runFieldMeta('completion_tokens').label) + '</th>'
    + '<th>' + esc(runFieldMeta('total_tokens').label) + '</th>'
    + '</tr></thead><tbody>' + rows + '</tbody>'
    + '<tfoot><tr><td>合计</td><td>' + (total.prompt_tokens || 0) + '</td>'
    + '<td>' + (total.completion_tokens || 0) + '</td>'
    + '<td>' + (total.total_tokens || 0) + '</td></tr></tfoot></table>';
}

function renderRunSummaryRow(r, taskId) {
  const total = (r.crawl_duration_ms || 0) + (r.analyze_duration_ms || 0);
  const st = r.stats || {};
  const sel = selectedRunId === r.id && selectedRunTaskId === taskId ? ' run-summary-row-selected' : '';
  return '<tr class="run-summary-row' + sel + '" onclick="selectRun(' + r.id + ', ' + taskId + ')">'
    + '<td>#' + r.id + '</td>'
    + '<td>' + fmtTime(r.started_at) + '</td>'
    + '<td>' + esc(runTriggerLabel(r.trigger)) + '</td>'
    + '<td>' + esc(runModeLabel(r.analyze_mode)) + '</td>'
    + '<td>' + statusTag(r.status) + '</td>'
    + '<td>' + fmtDuration(total) + '</td>'
    + '<td class="meta">+' + (st.raw_new || 0) + ' / ↑' + (st.raw_updated || 0) + ' / intel ' + (st.intel_written || 0) + '</td>'
    + '</tr>';
}

function renderRunHistoryContent(taskId) {
  const st = runHistoryState[taskId] || { runs: [], total: 0, loading: false };
  if (st.loading && !st.runs.length) {
    return '<p class="meta">加载中…</p>';
  }
  if (!st.runs.length) {
    return '<p class="muted">暂无执行记录</p>';
  }
  const rows = st.runs.map(function(r) { return renderRunSummaryRow(r, taskId); }).join('');
  const hasMore = st.runs.length < st.total;
  const footer = hasMore
    ? '<div class="run-history-footer"><span class="meta">已加载 ' + st.runs.length + ' / ' + st.total + '</span>'
      + '<button type="button" class="btn btn-gray btn-sm" onclick="loadMoreRuns(' + taskId + ')"'
      + (st.loading ? ' disabled' : '') + '>' + (st.loading ? '加载中…' : '加载更多') + '</button></div>'
    : '<div class="run-history-footer"><span class="meta">共 ' + st.total + ' 条</span></div>';
  return '<table class="run-summary-table"><thead><tr>'
    + '<th>Run</th><th>开始</th><th>触发</th><th>模式</th><th>状态</th><th>耗时</th><th>统计</th>'
    + '</tr></thead><tbody>' + rows + '</tbody></table>' + footer;
}

async function fetchRunHistoryPage(taskId, reset) {
  if (!runHistoryState[taskId]) {
    runHistoryState[taskId] = { page: 0, runs: [], total: 0, loading: false };
  }
  const st = runHistoryState[taskId];
  if (st.loading) return;
  st.loading = true;
  renderTaskTable();
  const page = reset ? 1 : st.page + 1;
  try {
    const d = await api('/api/monitor/tasks/' + taskId + '/runs?page=' + page + '&limit=' + RUN_HISTORY_LIMIT);
    if (!d.ok) throw new Error(d.msg || '加载失败');
    st.page = page;
    st.total = d.total || 0;
    const newRuns = d.runs || [];
    if (reset) st.runs = newRuns;
    else st.runs = st.runs.concat(newRuns);
  } catch (e) {
    document.getElementById('taskStatus').textContent = 'Run 历史加载失败: ' + e.message;
  } finally {
    st.loading = false;
    renderTaskTable();
  }
}

async function loadMoreRuns(taskId) {
  await fetchRunHistoryPage(taskId, false);
}

async function toggleRunHistory(taskId) {
  if (expandedRunHistoryTaskId === taskId) {
    expandedRunHistoryTaskId = null;
    renderTaskTable();
    return;
  }
  expandedRunHistoryTaskId = taskId;
  const st = runHistoryState[taskId];
  if (!st || !st.runs.length) {
    await fetchRunHistoryPage(taskId, true);
  } else {
    renderTaskTable();
  }
}

function renderTaskTable() {
  const body = document.getElementById('taskTableBody');
  if (!tasks.length) {
    body.innerHTML = '<tr><td colspan="9" class="empty">暂无监测任务，点击「创建任务」添加</td></tr>';
    return;
  }
  let html = '';
  tasks.forEach(function(t) {
    html += '<tr class="task-row" data-task-id="' + t.id + '">'
      + '<td>' + t.id + '</td>'
      + '<td class="truncate cell-name" title="' + esc(t.name || '') + '">' + esc(t.name || '-') + '</td>'
      + '<td class="cell-stack">' + statusTag(t.status) + '<br><span class="meta">原始 ' + (t.raw_count || 0) + ' / 情报 ' + (t.intel_count || 0) + '</span></td>'
      + '<td class="truncate cell-partners" title="' + esc(partnerNames(t.partner_ids)) + '">' + esc(partnerNames(t.partner_ids)) + '</td>'
      + '<td>' + ((t.sources || []).map(function(s) { return sourceTag(s); }).join(' ') || '-') + '</td>'
      + '<td>' + (t.max_pages || '-') + '</td>'
      + '<td class="cell-stack">' + formatLastRun(t) + '</td>'
      + '<td class="cell-stack">' + fmtTime(t.created_at) + '</td>'
      + '<td class="actions actions-wrap col-actions">'
      + '<button class="btn btn-primary btn-sm" onclick="runTaskById(' + t.id + ')" ' + (!t.can_run ? 'disabled' : '') + ' title="增量爬取+分析">执行</button>'
      + '<button class="btn btn-orange btn-sm" onclick="reanalyzeIncremental(' + t.id + ')" ' + (!t.can_reanalyze ? 'disabled' : '') + ' title="仅分析新增/更新的 raw">增量AI</button>'
      + '<button class="btn btn-orange btn-sm" onclick="reanalyzeFull(' + t.id + ')" ' + (!t.can_reanalyze ? 'disabled' : '') + ' title="清除情报后全量重分析">全量AI</button>'
      + '<button class="btn btn-gray btn-sm" onclick="toggleRunHistory(' + t.id + ')">' + (expandedRunHistoryTaskId === t.id ? '收起' : '历史') + '</button>'
      + '<button class="btn btn-gray btn-sm" onclick="editTask(' + t.id + ')" ' + (['crawling', 'analyzing'].includes(t.status) ? 'disabled' : '') + '>编辑</button>'
      + '<button class="btn btn-gray btn-sm" onclick="deleteTask(' + t.id + ')" ' + (['crawling', 'analyzing'].includes(t.status) ? 'disabled' : '') + '>删除</button>'
      + '<button class="btn btn-gray btn-sm" onclick="viewTaskIntel(' + t.id + ')">看情报</button>'
      + '</td></tr>';
    if (expandedRunHistoryTaskId === t.id) {
      html += '<tr class="run-history-row"><td colspan="9">' + renderRunHistoryContent(t.id) + '</td></tr>';
    }
  });
  body.innerHTML = html;
}

function buildTaskPayload() {
  const sched = window.SchedulePicker ? SchedulePicker.getScheduleFromDom() : { enabled: false };
  const { _preview, ...schedule } = sched;
  return {
    name: document.getElementById('tName').value.trim(),
    partner_ids: getSelectedPartnerIds(),
    sources: getSelectedSourceIds(),
    max_pages: parseInt(document.getElementById('tPages').value, 10) || 2,
    fetch_detail: document.getElementById('tFetchDetail').checked,
    schedule,
  };
}

function formatLastRun(t) {
  const lr = t.last_run;
  if (!lr) return '<span class="muted">—</span>';
  const total = (lr.crawl_duration_ms || 0) + (lr.analyze_duration_ms || 0);
  const sched = t.schedule && t.schedule.enabled ? '<br><span class="meta">定时' + (t.next_run_at ? ' · 下次 ' + fmtTime(t.next_run_at) : '') + '</span>' : '';
  return fmtTime(lr.finished_at || lr.started_at) + '<br><span class="meta">' + (lr.trigger || '') + ' · ' + fmtDuration(total) + ' · ' + (lr.status || '') + '</span>' + sched;
}

async function loadTasks() {
  const d = await api('/api/monitor/tasks');
  tasks = d.tasks || [];
  refreshTaskSelect();
  refreshAiLogTaskSelect();
  renderPartnerChecks([]);
  renderTaskTable();
}

function getSelectedPartnerIds() {
  return Array.from(document.querySelectorAll('input[name=taskPartner]:checked')).map(el => parseInt(el.value, 10));
}

function getSelectedSourceIds() {
  return Array.from(document.querySelectorAll('input[name=taskSource]:checked')).map(el => el.value);
}

async function createTask() {
  const payload = buildTaskPayload();
  if (!payload.partner_ids.length) { toastMsg('请至少选择一个合作方', true); return false; }
  if (!payload.sources.length) { toastMsg('请至少选择一个数据来源', true); return false; }
  let d;
  try {
    d = await api('/api/monitor/tasks', { method: 'POST', body: JSON.stringify(payload) });
  } catch (e) {
    toastMsg(e.message || '创建失败', true);
    return false;
  }
  if (!d.ok) { toastMsg(d.msg || '创建失败', true); return false; }
  lastTaskId = d.task.id;
  document.getElementById('taskStatus').textContent = '已创建任务 #' + lastTaskId;
  resetTaskForm();
  await loadTasks();
  toastMsg('任务已创建');
  return true;
}

function resetTaskForm() {
  document.getElementById('editingTaskId').value = '';
  document.getElementById('tName').value = '';
  document.getElementById('tPages').value = '2';
  document.getElementById('tFetchDetail').checked = true;
  renderPartnerChecks([]);
  renderSourceChecks();
  if (window.SchedulePicker) SchedulePicker.fillScheduleForm({ enabled: false });
}

function fillTaskForm(t) {
  document.getElementById('editingTaskId').value = t.id;
  document.getElementById('tName').value = t.name || '';
  document.getElementById('tPages').value = t.max_pages || 2;
  document.getElementById('tFetchDetail').checked = !!t.fetch_detail;
  renderPartnerChecks(t.partner_ids || []);
  renderSourceChecks(t.sources || []);
  if (window.SchedulePicker) SchedulePicker.fillScheduleForm(t.schedule || {});
}

function openTaskModal() {
  resetTaskForm();
  showTaskModal('创建监测任务', '创建任务');
}

function showTaskModal(title, confirmLabel) {
  UiShell.modal({
    title: title,
    bodyHtml: '',
    wide: true,
    confirmLabel: confirmLabel || '保存',
    cancelLabel: '取消',
    onMount: function(wrap) {
      mountHiddenForm(wrap, 'taskFormFields');
      if (window.SchedulePicker && SchedulePicker.initSchedulePicker) SchedulePicker.initSchedulePicker();
    },
    onClose: function() { restoreHiddenForm('taskFormFields'); },
    onConfirm: function() { return saveTask(); },
  });
}

async function editTask(id) {
  let d;
  try {
    d = await api('/api/monitor/tasks/' + id);
  } catch (e) {
    toastMsg(e.message || '加载失败', true);
    return;
  }
  if (!d.ok || !d.task) { toastMsg(d.msg || '加载失败', true); return; }
  if (['crawling', 'analyzing'].includes(d.task.status)) { toastMsg('运行中的任务不可编辑', true); return; }
  fillTaskForm(d.task);
  document.getElementById('taskStatus').textContent = '正在编辑任务 #' + id;
  showTaskModal('编辑监测任务 #' + id, '保存修改');
}

async function saveTask() {
  const editId = parseInt(document.getElementById('editingTaskId').value, 10);
  const payload = buildTaskPayload();
  if (!payload.partner_ids.length) { toastMsg('请至少选择一个合作方', true); return false; }
  if (!payload.sources.length) { toastMsg('请至少选择一个数据来源', true); return false; }
  if (editId) {
    let d;
    try {
      d = await api('/api/monitor/tasks/' + editId, { method: 'PUT', body: JSON.stringify(payload) });
    } catch (e) {
      toastMsg(e.message || '保存失败', true);
      return false;
    }
    if (!d.ok) { toastMsg(d.msg || '保存失败', true); return false; }
    document.getElementById('taskStatus').textContent = '任务 #' + editId + ' 已更新';
    resetTaskForm();
    await loadTasks();
    toastMsg('任务已保存');
    return true;
  }
  return createTask();
}

async function deleteTask(id) {
  const t = tasks.find(x => x.id === id);
  const ok = await UiShell.confirm(
    '确定删除监测任务「' + (t ? (t.name || '#' + id) : id) + '」？关联的原始/情报数据将一并删除。',
    '删除任务'
  );
  if (!ok) return;
  try {
    const d = await api('/api/monitor/tasks/' + id, { method: 'DELETE' });
    if (!d.ok) { toastMsg(d.msg || '删除失败', true); return; }
    if (parseInt(document.getElementById('editingTaskId').value, 10) === id) resetTaskForm();
    document.getElementById('taskStatus').textContent = '任务 #' + id + ' 已删除';
    await loadTasks();
    if (lastTaskId === id) loadRecords();
    toastMsg('任务已删除');
  } catch (e) {
    toastMsg(e.message || '删除失败', true);
  }
}

async function runTaskById(task_id) {
  let d;
  try {
    d = await api('/api/monitor/run', { method: 'POST', body: JSON.stringify({ task_id, analyze_mode: 'incremental' }) });
  } catch (e) {
    toastMsg(e.message || '启动失败', true);
    return;
  }
  if (!d.ok) { toastMsg(d.msg || '启动失败', true); return; }
  document.getElementById('taskStatus').textContent = '任务 #' + task_id + ' 增量执行已启动…';
  pollTask(task_id);
}

async function reanalyzeIncremental(task_id) {
  const ok = await UiShell.confirm('任务 #' + task_id + ' 将仅对新增/更新的原始数据做 AI 分析。继续？', '增量 AI');
  if (!ok) return;
  await startReanalyze(task_id, 'incremental');
}

async function reanalyzeFull(task_id) {
  const t = tasks.find(x => x.id === task_id);
  const intel = t ? (t.intel_count || 0) : '?';
  const ok = await UiShell.confirm('任务 #' + task_id + ' 将清除现有 ' + intel + ' 条情报并全量重分析。继续？', '全量 AI');
  if (!ok) return;
  await startReanalyze(task_id, 'full_replace');
}

async function startReanalyze(task_id, analyze_mode) {
  let d;
  try {
    d = await api('/api/monitor/reanalyze', { method: 'POST', body: JSON.stringify({ task_id, analyze_mode }) });
  } catch (e) {
    toastMsg(e.message || '启动失败', true);
    return;
  }
  if (!d.ok) { toastMsg(d.msg || '启动失败', true); return; }
  document.getElementById('taskStatus').textContent = '任务 #' + task_id + ' 正在 ' + (analyze_mode === 'full_replace' ? '全量' : '增量') + ' AI 分析…';
  pollTask(task_id);
}

async function reanalyzeTask(task_id) {
  await reanalyzeFull(task_id);
}

function viewTaskIntel(task_id) {
  lastTaskId = task_id;
  App.navigateIntel({ task_id: task_id });
}

function onTaskFilterChange() {
  lastTaskId = parseInt(document.getElementById('fTask').value, 10) || null;
  App.setQuery({
    task_id: lastTaskId || null,
    partner_id: document.getElementById('fPartner').value || null,
    source: document.getElementById('fSource').value || null,
    relevance_min: document.getElementById('fRelevance').value || null,
  }, true);
  loadRecords();
}

async function pollTask(id) {
  if (!id) return;
  const el = document.getElementById('taskStatus');
  if (!el) return;
  for (let i = 0; i < 600; i++) {
    await new Promise(r => setTimeout(r, 3000));
    const d = await api('/api/monitor/tasks/' + id);
    if (!d.ok) break;
    const t = d.task;
    el.textContent = `任务 #${id}: ${t.status}` + (t.progress && Object.keys(t.progress).length ? ' · ' + JSON.stringify(t.progress) : '');
    await loadTasks();
    if (t.status === 'done' || t.status === 'failed') {
      if (runHistoryState[id]) delete runHistoryState[id];
      if (expandedRunHistoryTaskId === id) await fetchRunHistoryPage(id, true);
      if (t.status === 'done') viewTaskIntel(id);
      break;
    }
  }
}

async function loadRecords() {
  const params = intelFilterParams();
  params.set('page_size', '100');
  let d;
  try {
    d = await api('/api/intel/records?' + params.toString());
  } catch (e) {
    document.getElementById('recordBody').innerHTML = '<tr><td colspan="10" class="msg-err">' + esc(e.message) + '</td></tr>';
    return;
  }
  const rows = d.records || [];
  document.getElementById('recordCount').textContent = '(共 ' + (d.total || rows.length) + ' 条)';
  const body = document.getElementById('recordBody');
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="10" class="empty">暂无数据</td></tr>';
    return;
  }
  body.innerHTML = rows.map(r => `<tr class="clickable-row" onclick="showIntelDetail(${r.id})">
    <td>${esc(r.partner_name || '-')}</td>
    <td>${sourceTag(r.source)}</td>
    <td>${relTag(r.relevance)}</td>
    <td>${sentimentTag(r.sentiment_label, r.sentiment_score)}</td>
    <td>${esc((r.risk_types || []).join('、') || '-')}</td>
    <td>${fmtTime(r.published_at)}</td>
    <td>${fmtTime(r.captured_at)}</td>
    <td>${fmtTime(r.analyzed_at || r.created_at)}</td>
    <td class="truncate" title="${esc(r.body || '')}">${esc((r.summary || r.title || '').slice(0, 80))}</td>
    <td class="actions" onclick="event.stopPropagation()">
      <button class="btn btn-gray btn-sm" onclick="showIntelDetail(${r.id})">详情</button>
      ${r.url ? `<a href="${esc(r.url)}" target="_blank" class="link-muted">原文</a>` : ''}
    </td>
  </tr>`).join('');
}

async function showIntelDetail(intelId) {
  const list = document.getElementById('intelListView');
  const detail = document.getElementById('intelDetailView');
  const box = document.getElementById('intelDetailContent');
  if (list) list.style.display = 'none';
  if (detail) detail.style.display = '';
  if (!box) return;
  box.innerHTML = '<p class="meta">加载中…</p>';
  try {
    const d = await api('/api/intel/records/' + intelId);
    if (!d.ok || !d.record) throw new Error(d.msg || '不存在');
    const r = d.record;
    const rawLink = r.raw_record_id
      ? '<button class="btn btn-gray btn-sm" onclick="App.setQuery({tab:\'raw\',raw_id:' + r.raw_record_id + ',task_id:' + r.task_id + '});App.switchAppTab(\'raw\')">源数据 #' + r.raw_record_id + '</button>'
      : '<span class="muted">无关联源数据</span>';
    box.innerHTML =
      '<div class="detail-head"><button class="btn btn-gray btn-sm" onclick="backToIntelList()">← 返回列表</button>'
      + '<h2>情报 #' + r.id + '</h2></div>'
      + '<div class="detail-meta">'
      + intelMetaRow('合作方', r.partner_name || ('#' + r.partner_id))
      + intelMetaRow('任务', '#' + r.task_id)
      + intelMetaRow('来源', r.source)
      + intelMetaRow('相关度', r.relevance)
      + intelMetaRow('情感', (r.sentiment_label || '') + (r.sentiment_score != null ? ' (' + Number(r.sentiment_score).toFixed(2) + ')' : ''))
      + intelMetaRow('风险类型', (r.risk_types || []).join('、') || '—')
      + intelMetaRow('发布时间', fmtTime(r.published_at))
      + intelMetaRow('采集时间', fmtTime(r.captured_at))
      + intelMetaRow('生成时间', fmtTime(r.analyzed_at || r.created_at))
      + intelMetaRow('dedup_key', r.dedup_key || '—')
      + '</div>'
      + '<div class="detail-actions">' + rawLink
      + (r.url ? ' <a href="' + esc(r.url) + '" target="_blank" class="btn btn-gray btn-sm">打开原文</a>' : '')
      + '</div>'
      + (r.title ? '<h3 class="detail-subtitle">' + esc(r.title) + '</h3>' : '')
      + '<div class="detail-body-text">' + esc(r.body || r.summary || '—') + '</div>';
    App.setQuery({ intel_id: intelId }, true);
  } catch (e) {
    box.innerHTML = '<p class="msg-err">' + esc(e.message) + '</p>';
  }
}

function intelMetaRow(k, v) {
  return '<div class="detail-kv"><span class="k">' + esc(k) + '</span><span class="v">' + esc(v) + '</span></div>';
}

function backToIntelList() {
  App.setQuery({ intel_id: null }, true);
  showIntelList();
  loadRecords();
}

function exportIntel(fmt) {
  const params = intelFilterParams();
  params.set('format', fmt);
  window.open('/api/intel/export?' + params.toString(), '_blank');
}

function fillAnalysisForm(analysis, status, activePromptBody) {
  const ai = analysis || {};
  window._activePromptBody = activePromptBody || '';
  const set = (id, v) => { const el = document.getElementById(id); if (el && v !== undefined && v !== null) el.value = v; };
  set('aiProvider', ai.provider || '');
  set('aiEndpoint', ai.endpoint || '');
  set('aiEndpointIntl', ai.endpoint_intl || '');
  set('aiModel', ai.model || '');
  set('aiPromptVer', ai.prompt_version || '');
  set('aiKeyEnv', ai.api_key_env || 'MINIMAX_API_KEY');
  set('aiBatch', ai.batch_size != null ? ai.batch_size : 10);
  set('aiBodyMax', ai.max_body_chars != null ? ai.max_body_chars : 2000);
  set('aiRetries', ai.max_retries != null ? ai.max_retries : 2);
  set('aiRetryDelay', ai.retry_delay_sec != null ? ai.retry_delay_sec : 2);
  set('aiTemp', ai.temperature != null ? ai.temperature : 0.3);
  set('aiTimeout', ai.timeout_sec != null ? ai.timeout_sec : 180);
  const mockEl = document.getElementById('aiMock');
  if (mockEl) mockEl.checked = !!ai.mock_without_key;
  const mockRel = document.getElementById('aiMockRel');
  if (mockRel) mockRel.value = ai.mock_default_relevance || 'medium';
  const sp = document.getElementById('aiSystemPrompt');
  if (sp) {
    sp.value = activePromptBody || window._activePromptBody || '';
  }
  const eb = document.getElementById('aiExtraBody');
  if (eb) eb.value = ai.extra_body ? JSON.stringify(ai.extra_body, null, 2) : '';
  const keyEl = document.getElementById('aiKey');
  if (keyEl) {
    if (ai.api_key && ai.api_key !== '***已配置***') keyEl.value = ai.api_key;
    else keyEl.value = '';
    keyEl.placeholder = (ai.api_key === '***已配置***' || (status && status.has_api_key))
      ? '已配置（留空不修改）' : '留空则读环境变量 MINIMAX_API_KEY';
  }
  const badge = document.getElementById('aiStatusBadge');
  if (status) {
    if (status.mock_mode) {
      badge.textContent = 'Mock 模式';
      badge.className = 'tag tag-medium';
    } else if (status.has_api_key) {
      badge.textContent = '已配置 Key · ' + (status.model || ai.model || '');
      badge.className = 'tag tag-on';
    } else {
      badge.textContent = '未配置 Key';
      badge.className = 'tag tag-off';
    }
  }
}

function setAiMsg(text, ok) {
  const msg = document.getElementById('aiSaveMsg');
  if (!msg) return;
  msg.textContent = text || '';
  msg.className = 'meta' + (text ? (ok ? ' msg-ok' : ' msg-err') : '');
}

async function loadAnalysisConfig() {
  try {
    const d = await api('/api/analysis/config');
    if (!d.ok) {
      setAiMsg(d.msg || '加载失败', false);
      return;
    }
    fillAnalysisForm(d.analysis, d.status, d.active_prompt_body);
    fillPromptSelect(d.prompts || [], d.active_prompt_id);
    setAiMsg('', true);
  } catch (e) {
    const hint = e.status === 404 ? '（接口不存在，请重启 python crawler_web.py）' : '';
    setAiMsg('加载大模型配置失败' + hint + (e.message ? '：' + e.message : ''), false);
  }
}

async function saveAnalysisConfig() {
  let extraBody = undefined;
  const extraRaw = document.getElementById('aiExtraBody').value.trim();
  if (extraRaw) {
    try { extraBody = JSON.parse(extraRaw); } catch (e) {
      setAiMsg('extra_body 须为合法 JSON', false);
      return;
    }
  }
  const payload = {
    provider: document.getElementById('aiProvider').value.trim(),
    endpoint: document.getElementById('aiEndpoint').value.trim(),
    endpoint_intl: document.getElementById('aiEndpointIntl').value.trim(),
    model: document.getElementById('aiModel').value.trim(),
    prompt_version: document.getElementById('aiPromptVer').value.trim(),
    api_key_env: document.getElementById('aiKeyEnv').value.trim() || 'MINIMAX_API_KEY',
    batch_size: parseInt(document.getElementById('aiBatch').value, 10) || 10,
    max_body_chars: parseInt(document.getElementById('aiBodyMax').value, 10) || 2000,
    max_retries: parseInt(document.getElementById('aiRetries').value, 10) || 2,
    retry_delay_sec: parseFloat(document.getElementById('aiRetryDelay').value) || 2,
    temperature: parseFloat(document.getElementById('aiTemp').value),
    timeout_sec: parseInt(document.getElementById('aiTimeout').value, 10) || 180,
    mock_without_key: document.getElementById('aiMock').checked,
    mock_default_relevance: document.getElementById('aiMockRel').value,
  };
  if (extraBody !== undefined) payload.extra_body = extraBody;
  const key = document.getElementById('aiKey').value.trim();
  if (key) payload.api_key = key;
  setAiMsg('正在保存…', true);
  try {
    const d = await api('/api/analysis/config', { method: 'POST', body: JSON.stringify({ analysis: payload }) });
    if (!d.ok) {
      setAiMsg(d.msg || '保存失败', false);
      return;
    }
    fillAnalysisForm(d.analysis || payload, d.status, d.active_prompt_body);
    fillPromptSelect(d.prompts || [], d.active_prompt_id);
    const keyHint = (d.status && d.status.has_api_key) ? ' · API Key 已配置' : '';
    setAiMsg('保存成功 · ' + new Date().toLocaleTimeString() + keyHint, true);
  } catch (e) {
    setAiMsg('保存失败' + (e.message ? '：' + e.message : ''), false);
  }
}

let _promptCatalog = [];

function fillPromptSelect(prompts, activeId) {
  _promptCatalog = prompts || [];
  const sel = document.getElementById('aiPromptSelect');
  if (!sel) return;
  sel.innerHTML = _promptCatalog.map(function(p) {
    const mark = p.is_active ? ' ✓' : '';
    return '<option value="' + esc(p.id) + '"' + (p.id === activeId || p.is_active ? ' selected' : '') + '>' +
      esc(p.name || p.id) + mark + '</option>';
  }).join('');
}

async function onPromptSelectChange() {
  const id = document.getElementById('aiPromptSelect').value;
  if (!id) return;
  try {
    const d = await api('/api/analysis/prompts/' + encodeURIComponent(id));
    if (d.prompt && d.prompt.body != null) {
      document.getElementById('aiSystemPrompt').value = d.prompt.body;
    }
  } catch (e) {}
}

async function activateSelectedPrompt() {
  const id = document.getElementById('aiPromptSelect').value;
  if (!id) return;
  try {
    await api('/api/analysis/prompts/' + encodeURIComponent(id) + '/activate', { method: 'POST', body: '{}' });
    showToast('已切换 Prompt: ' + id);
    await loadAnalysisConfig();
  } catch (e) {
    showToast(e.message || '切换失败', true);
  }
}

async function saveCurrentPromptBody() {
  const id = document.getElementById('aiPromptSelect').value;
  const body = document.getElementById('aiSystemPrompt').value;
  if (!id) return showToast('请选择模板', true);
  try {
    await api('/api/analysis/prompts/' + encodeURIComponent(id), {
      method: 'PUT',
      body: JSON.stringify({ body: body }),
    });
    showToast('Prompt 已保存');
    await loadAnalysisConfig();
  } catch (e) {
    showToast(e.message || '保存失败', true);
  }
}

async function savePromptAsNew() {
  const body = document.getElementById('aiSystemPrompt').value;
  if (!body.trim()) return showToast('Prompt 不能为空', true);
  const id = prompt('新版本 ID（英文 slug）', 'custom-' + Date.now());
  if (!id) return;
  const name = prompt('显示名称', id) || id;
  try {
    await api('/api/analysis/prompts', {
      method: 'POST',
      body: JSON.stringify({ id: id.trim(), name: name.trim(), body: body }),
    });
    showToast('已创建 ' + id);
    await loadAnalysisConfig();
  } catch (e) {
    showToast(e.message || '创建失败', true);
  }
}

async function deleteSelectedPrompt() {
  const id = document.getElementById('aiPromptSelect').value;
  if (!id) return;
  if (!confirm('确定删除 Prompt「' + id + '」？')) return;
  try {
    await api('/api/analysis/prompts/' + encodeURIComponent(id), { method: 'DELETE' });
    showToast('已删除');
    await loadAnalysisConfig();
  } catch (e) {
    showToast(e.message || '删除失败', true);
  }
}

if (window.SchedulePicker) {
  document.addEventListener('DOMContentLoaded', function () {
    SchedulePicker.initSchedulePicker();
  });
}
