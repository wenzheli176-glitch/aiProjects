let sources = [], partners = [], tasks = [], lastTaskId = null;
let aiLogTimer = null;
const RUN_HISTORY_LIMIT = 5;
const SUBTASK_RUN_LIMIT = 40;
const runHistoryState = {};
let expandedRunHistoryTaskId = null;
let selectedRunId = null;
let selectedRunTaskId = null;
let intelListPage = 1;
let intelListPageSize = LIST_PAGE_SIZE_DEFAULT;

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
  const sentiment = document.getElementById('fSentiment');
  const sMin = document.getElementById('fSentimentMin');
  const sMax = document.getElementById('fSentimentMax');
  if (task && task.value) params.set('task_id', task.value);
  if (partner && partner.value) params.set('partner_id', partner.value);
  if (source && source.value) params.set('source', source.value);
  if (rel && rel.value) params.set('relevance_min', rel.value);
  if (sentiment && sentiment.value) params.set('sentiment_label', sentiment.value);
  if (sMin && sMin.value !== '') params.set('sentiment_score_min', sMin.value);
  if (sMax && sMax.value !== '') params.set('sentiment_score_max', sMax.value);
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
  set('fSentiment', 'sentiment_label');
  set('fSentimentMin', 'sentiment_score_min');
  set('fSentimentMax', 'sentiment_score_max');
  if (q.get('task_id')) lastTaskId = parseInt(q.get('task_id'), 10) || lastTaskId;
  if (q.get('intel_page')) intelListPage = Math.max(1, parseInt(q.get('intel_page'), 10) || 1);
  if (q.get('intel_page_size')) intelListPageSize = clampListPageSize(q.get('intel_page_size'));
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
  const monitorTaskId = App.getQuery('monitor_task_id');
  if (monitorTaskId) {
    const taskTab = App.getQuery('task_tab') || 'overview';
    await openTaskDetail(parseInt(monitorTaskId, 10), taskTab);
    const runId = App.getQuery('run_id');
    if (runId) {
      await openRunDrawer(parseInt(runId, 10), parseInt(monitorTaskId, 10));
    }
    return;
  }
  showTaskListView();
  await loadTasks();
  const runId = App.getQuery('run_id');
  if (runId) {
    const taskId = App.getQuery('task_id');
    await openRunDrawer(parseInt(runId, 10), taskId ? parseInt(taskId, 10) : null);
  }
}

const RUN_GLOSSARY_GROUPS = [
  {
    title: 'Run',
    keys: ['trigger', 'analyze_mode', 'status', 'started_at', 'finished_at', 'error_message'],
  },
  {
    title: 'Timing',
    keys: ['crawl_duration_ms', 'analyze_duration_ms', 'crawl_ms', 'analyze_ms'],
  },
  {
    title: 'Stats',
    keys: [
      'raw_new', 'raw_updated', 'raw_unchanged', 'intel_written', 'intel_replaced', 'intel_skipped',
      'triage_high', 'triage_medium', 'triage_noise', 'needs_investigation_count',
      'investigation_queued', 'investigation_done', 'investigation_failed',
      'investigation_modal_done', 'investigation_skipped_quota',
    ],
  },
  {
    title: 'Tokens',
    keys: ['prompt_tokens', 'completion_tokens', 'total_tokens'],
  },
];

const RUN_STATS_KEYS = [
  'raw_new', 'raw_updated', 'raw_unchanged', 'intel_written', 'intel_replaced', 'intel_skipped',
  'triage_high', 'triage_medium', 'triage_noise', 'needs_investigation_count',
  'investigation_queued', 'investigation_done', 'investigation_failed',
  'investigation_modal_done', 'investigation_skipped_quota',
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

/** 生成可嵌入 HTML 双引号 onclick 属性的 JS 字符串字面量 */
function jsAttrStr(s) {
  return "'" + String(s ?? '').replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
}

function sourceTag(s) {
  const cls = s === 'heimao' ? 'tag-heimao' : (s === 'xhs' ? 'tag-xhs' : '');
  const label = s === 'heimao' ? '黑猫' : (s === 'xhs' ? '小红书' : s);
  return `<span class="tag ${cls}">${esc(label)}</span>`;
}

function relLabelText(r) {
  const cn = { high: '高', medium: '中', low: '低', noise: '无关' };
  return cn[r] || r || '—';
}

function relTag(r) {
  return `<span class="tag tag-${r || 'medium'}">${esc(relLabelText(r))}</span>`;
}

function sentimentLabelText(label) {
  const cn = { negative: '负面', neutral: '中性', positive: '正面' };
  return cn[label] || label || '—';
}

function sentimentTag(label, score) {
  const cls = { negative: 'tag-off', neutral: 'tag-medium', positive: 'tag-on' };
  const lbl = label || 'neutral';
  const sc = score != null && score !== '' ? ` (${Number(score).toFixed(2)})` : '';
  return `<span class="tag ${cls[lbl] || 'tag-medium'}">${esc(sentimentLabelText(lbl))}${sc}</span>`;
}

function statusTag(s) {
  const labels = {
    queued: '排队',
    crawling: '爬取中',
    analyzing: '分析中',
    done: '完成',
    failed: '失败',
    paused: '已暂停',
    stopped: '已终止',
  };
  const label = labels[s] || s || '-';
  return '<span class="tag tag-status ' + esc(s || 'queued') + '">' + esc(label) + '</span>';
}

function partnerName(id) {
  const p = partners.find(x => x.id === id);
  return p ? p.name : ('#' + id);
}

function partnerNames(ids) {
  return (ids || []).map(id => partnerName(id)).join('、') || '-';
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
  srcBox.querySelectorAll('input').forEach(el => {
    el.addEventListener('change', syncCrawlModeFieldVisibility);
  });
  syncCrawlModeFieldVisibility();
}

function syncCrawlModeFieldVisibility() {
  const field = document.getElementById('tCrawlModeField');
  const note = document.getElementById('tCrawlModeNote');
  if (!field || !note) return;
  const sourcesSel = getSelectedSourceIds();
  const hasXhs = sourcesSel.includes('xhs');
  const heimaoOnly = sourcesSel.length === 1 && sourcesSel[0] === 'heimao';
  if (hasXhs) {
    field.style.display = 'none';
    note.textContent = sourcesSel.length > 1
      ? '混合源：黑猫 legacy（可勾选详情），小红书固定 list_first（routine 无详情，勘察弹窗）。'
      : '小红书固定 list_first：常规仅列表，详情在勘察阶段弹窗。';
  } else if (heimaoOnly) {
    field.style.display = '';
    note.textContent = '黑猫 crawl_mode 以「数据源管理 → 黑猫投诉 → 爬取策略」为准；此处选项仅在源级未配置时作为单源黑猫任务的 fallback。';
  } else {
    field.style.display = 'none';
    note.textContent = '请选择数据来源；爬取策略由数据源配置决定。';
  }
}

function getEnabledPartnersForTask() {
  return partners.filter(p => p.enabled);
}

function getSelectedPartnerIds() {
  return Array.from(document.querySelectorAll('input[name=taskPartner]:checked')).map(el => parseInt(el.value, 10));
}

function isTaskFormVisible() {
  const fields = document.getElementById('taskFormFields');
  return !!(fields && !fields.classList.contains('hidden-form-fields'));
}

/** 任务表单在 Modal 中打开时，刷新列表后保留已选合作方，避免轮询清空勾选。 */
function refreshTaskFormPartnerChecksIfVisible() {
  if (!isTaskFormVisible()) return;
  renderPartnerChecks(getSelectedPartnerIds());
}

function _partnerPickerLabels(visibleOnly) {
  const box = document.getElementById('tPartnerChecks');
  if (!box) return [];
  const labels = Array.from(box.querySelectorAll('label[data-partner-id]'));
  if (!visibleOnly) return labels;
  return labels.filter(l => !l.classList.contains('is-hidden'));
}

function _syncPartnerCheckLabelState(label) {
  const input = label.querySelector('input[name=taskPartner]');
  if (input) label.classList.toggle('is-checked', !!input.checked);
}

function updatePartnerCheckSummary() {
  const summary = document.getElementById('tPartnerCheckSummary');
  if (!summary) return;
  const all = document.querySelectorAll('input[name=taskPartner]');
  const checked = document.querySelectorAll('input[name=taskPartner]:checked');
  const visible = _partnerPickerLabels(true);
  const visibleChecked = visible.filter(l => l.querySelector('input[name=taskPartner]:checked')).length;
  const filterEl = document.getElementById('tPartnerFilter');
  const filtering = filterEl && filterEl.value.trim();
  if (filtering && visible.length !== all.length) {
    summary.textContent = '已选 ' + checked.length + ' / ' + all.length + '（可见 ' + visibleChecked + '/' + visible.length + '）';
  } else {
    summary.textContent = '已选 ' + checked.length + ' / ' + all.length;
  }
  _partnerPickerLabels(false).forEach(_syncPartnerCheckLabelState);
  syncPartnerQuickPickActive();
}

function applyPartnerFilter() {
  const q = ((document.getElementById('tPartnerFilter') || {}).value || '').trim().toLowerCase();
  _partnerPickerLabels(false).forEach(function(label) {
    if (!q) {
      label.classList.remove('is-hidden');
      return;
    }
    const hay = (label.getAttribute('data-search') || '').toLowerCase();
    label.classList.toggle('is-hidden', hay.indexOf(q) === -1);
  });
  updatePartnerCheckSummary();
}

function taskPartnerSelectAll() {
  _partnerPickerLabels(true).forEach(function(label) {
    const input = label.querySelector('input[name=taskPartner]');
    if (input) input.checked = true;
  });
  updatePartnerCheckSummary();
}

function taskPartnerSelectNone() {
  document.querySelectorAll('input[name=taskPartner]').forEach(function(el) { el.checked = false; });
  updatePartnerCheckSummary();
}

function taskPartnerSelectInvert() {
  _partnerPickerLabels(true).forEach(function(label) {
    const input = label.querySelector('input[name=taskPartner]');
    if (input) input.checked = !input.checked;
  });
  updatePartnerCheckSummary();
}

function _partnerIdsMatching(filterFn) {
  return getEnabledPartnersForTask().filter(filterFn).map(function(p) { return p.id; });
}

function taskPartnerToggleGroup(ids) {
  const idList = ids || [];
  if (!idList.length) return;
  const inputs = idList.map(function(id) {
    return document.querySelector('input[name=taskPartner][value="' + id + '"]');
  }).filter(Boolean);
  if (!inputs.length) return;
  const allChecked = inputs.every(function(el) { return el.checked; });
  inputs.forEach(function(el) { el.checked = !allChecked; });
  updatePartnerCheckSummary();
}

function syncPartnerQuickPickActive() {
  const wrap = document.getElementById('tPartnerQuickPick');
  if (!wrap) return;
  wrap.querySelectorAll('.partner-quick-chip[data-kind]').forEach(function(chip) {
    const kind = chip.getAttribute('data-kind');
    const val = chip.getAttribute('data-value') || '';
    let ids = [];
    if (kind === 'cohort') {
      ids = _partnerIdsMatching(function(p) { return (p.industry_cohort || '').trim() === val; });
    } else if (kind === 'tier') {
      ids = _partnerIdsMatching(function(p) { return (p.priority_tier || 'P1') === val; });
    }
    const inputs = ids.map(function(id) {
      return document.querySelector('input[name=taskPartner][value="' + id + '"]');
    }).filter(Boolean);
    const active = inputs.length > 0 && inputs.every(function(el) { return el.checked; });
    chip.classList.toggle('is-active', active);
  });
}

function renderPartnerQuickPick() {
  const wrap = document.getElementById('tPartnerQuickPick');
  if (!wrap) return;
  const enabled = getEnabledPartnersForTask();
  if (!enabled.length) {
    wrap.innerHTML = '';
    return;
  }
  const cohortMap = {};
  const tierMap = { P0: 0, P1: 0, P2: 0 };
  enabled.forEach(function(p) {
    const cohort = (p.industry_cohort || '').trim();
    if (cohort) cohortMap[cohort] = (cohortMap[cohort] || 0) + 1;
    const tier = p.priority_tier || 'P1';
    if (tierMap[tier] !== undefined) tierMap[tier] += 1;
  });
  const cohorts = Object.keys(cohortMap).sort(function(a, b) {
    return cohortMap[b] - cohortMap[a] || a.localeCompare(b, 'zh-CN');
  });
  const parts = [];
  if (cohorts.length) {
    parts.push('<div class="partner-quick-group"><span class="partner-quick-group-label">cohort</span>' +
      cohorts.map(function(c) {
        return '<button type="button" class="partner-quick-chip" data-kind="cohort" data-value="' + esc(c) + '" title="切换选择该 cohort 下合作方">' +
          esc(c) + ' <span class="muted">(' + cohortMap[c] + ')</span></button>';
      }).join('') + '</div>');
  }
  const tiers = ['P0', 'P1', 'P2'].filter(function(t) { return tierMap[t] > 0; });
  if (tiers.length) {
    parts.push('<div class="partner-quick-group"><span class="partner-quick-group-label">优先级</span>' +
      tiers.map(function(t) {
        return '<button type="button" class="partner-quick-chip" data-kind="tier" data-value="' + t + '" title="切换选择 ' + t + ' 合作方">' +
          t + ' <span class="muted">(' + tierMap[t] + ')</span></button>';
      }).join('') + '</div>');
  }
  wrap.innerHTML = parts.join('');
  wrap.querySelectorAll('.partner-quick-chip').forEach(function(chip) {
    chip.addEventListener('click', function() {
      const kind = chip.getAttribute('data-kind');
      const val = chip.getAttribute('data-value') || '';
      let ids = [];
      if (kind === 'cohort') {
        ids = _partnerIdsMatching(function(p) { return (p.industry_cohort || '').trim() === val; });
      } else if (kind === 'tier') {
        ids = _partnerIdsMatching(function(p) { return (p.priority_tier || 'P1') === val; });
      }
      taskPartnerToggleGroup(ids);
    });
  });
  syncPartnerQuickPickActive();
}

function _partnerSearchText(p) {
  return [
    p.name || '',
    (p.aliases || []).join(' '),
    p.industry_cohort || '',
    p.priority_tier || '',
  ].join(' ').toLowerCase();
}

function _partnerCheckLabelHtml(p, selectedIds) {
  const cohort = (p.industry_cohort || '').trim();
  const tier = p.priority_tier || 'P1';
  const meta = [
    cohort ? '<span class="partner-chip-meta">' + esc(cohort) + '</span>' : '',
    '<span class="partner-chip-meta">' + esc(tier) + '</span>',
  ].filter(Boolean).join('');
  const checked = selectedIds.includes(p.id) ? ' checked' : '';
  return '<label data-partner-id="' + p.id + '" data-search="' + esc(_partnerSearchText(p)) + '">' +
    '<input type="checkbox" name="taskPartner" value="' + p.id + '"' + checked + '> ' +
    '<span>' + esc(p.name) + '</span>' + meta + '</label>';
}

function initPartnerPickerToolbar() {
  const root = document.getElementById('taskFormFields');
  if (!root || root.dataset.partnerPickerBound) return;
  root.dataset.partnerPickerBound = '1';
  const filterEl = document.getElementById('tPartnerFilter');
  if (filterEl) filterEl.addEventListener('input', applyPartnerFilter);
  const btnAll = document.getElementById('tPartnerSelectAll');
  const btnNone = document.getElementById('tPartnerSelectNone');
  const btnInvert = document.getElementById('tPartnerSelectInvert');
  if (btnAll) btnAll.addEventListener('click', taskPartnerSelectAll);
  if (btnNone) btnNone.addEventListener('click', taskPartnerSelectNone);
  if (btnInvert) btnInvert.addEventListener('click', taskPartnerSelectInvert);
  const checks = document.getElementById('tPartnerChecks');
  if (checks) {
    checks.addEventListener('change', function(e) {
      if (e.target && e.target.name === 'taskPartner') updatePartnerCheckSummary();
    });
  }
}

function renderPartnerChecks(selectedIds) {
  const box = document.getElementById('tPartnerChecks');
  if (!box) return;
  const enabled = getEnabledPartnersForTask();
  initPartnerPickerToolbar();
  const filterEl = document.getElementById('tPartnerFilter');
  if (filterEl) filterEl.value = '';
  if (!enabled.length) {
    box.innerHTML = '<span class="muted">暂无启用的合作方，请先在「合作方管理」中添加</span>';
    renderPartnerQuickPick();
    updatePartnerCheckSummary();
    return;
  }
  const ids = selectedIds || getSelectedPartnerIds();
  box.innerHTML = enabled.map(function(p) { return _partnerCheckLabelHtml(p, ids); }).join('');
  _partnerPickerLabels(false).forEach(_syncPartnerCheckLabelState);
  renderPartnerQuickPick();
  updatePartnerCheckSummary();
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

function aiPhaseLabel(phase) {
  return { list_triage: '初筛', analysis: '分析' }[phase] || phase || '分析';
}

function fmtTokens(n) {
  const v = Number(n) || 0;
  return v.toLocaleString('zh-CN');
}

function fmtUsageCalls(u) {
  u = u || {};
  return `${u.api_calls || 0} / ${u.mock_calls || 0} / ${u.failed_calls || 0}`;
}

function renderUsagePhaseBars(byPhase, totalTokens) {
  const el = document.getElementById('aiUsageByPhase');
  if (!el) return;
  const phases = [
    { key: 'list_triage', label: '初筛', cls: 'triage' },
    { key: 'analysis', label: '分析', cls: 'analysis' },
  ];
  const max = Math.max(totalTokens || 0, 1);
  el.innerHTML = phases.map(p => {
    const u = (byPhase && byPhase[p.key]) || {};
    const tt = u.total_tokens || 0;
    const pct = Math.max(2, Math.round((tt / max) * 100));
    return `<div class="usage-phase-row">
      <span>${p.label}</span>
      <div class="usage-phase-bar"><span class="${p.cls}" style="width:${pct}%"></span></div>
      <span>${fmtTokens(tt)} · ${fmtUsageCalls(u)}</span>
    </div>`;
  }).join('');
}

function renderUsageInOut(periodTotal) {
  const el = document.getElementById('aiUsageInOut');
  if (!el) return;
  const u = periodTotal || {};
  const total = Math.max((u.prompt_tokens || 0) + (u.completion_tokens || 0), 1);
  const inPct = Math.round(((u.prompt_tokens || 0) / total) * 100);
  const outPct = 100 - inPct;
  el.innerHTML = `
    <div class="usage-phase-row"><span>输入</span><div class="usage-phase-bar"><span class="triage" style="width:${inPct}%"></span></div><span>${fmtTokens(u.prompt_tokens)}</span></div>
    <div class="usage-phase-row"><span>输出</span><div class="usage-phase-bar"><span class="analysis" style="width:${outPct}%"></span></div><span>${fmtTokens(u.completion_tokens)}</span></div>
    <p class="muted" style="margin:8px 0 0;font-size:12px">合计 ${fmtTokens(u.total_tokens)} · 耗时 ${fmtTokens(u.latency_ms)} ms</p>`;
}

function renderUsageDaily(daily) {
  const el = document.getElementById('aiUsageDaily');
  if (!el) return;
  const rows = daily || [];
  if (!rows.length) {
    el.innerHTML = '<p class="empty">所选时间范围内暂无 LLM 调用记录</p>';
    return;
  }
  const max = Math.max(...rows.map(d => (d.total && d.total.total_tokens) || 0), 1);
  el.innerHTML = `<table><thead><tr>
    <th>日期</th><th>用量</th><th>合计</th><th>初筛</th><th>分析</th><th>API</th>
  </tr></thead><tbody>${rows.map(d => {
    const t = d.total || {};
    const tri = d.list_triage || {};
    const ana = d.analysis || {};
    const tt = t.total_tokens || 0;
    const triPct = tt ? Math.round(((tri.total_tokens || 0) / tt) * 100) : 0;
    const anaPct = tt ? Math.max(0, 100 - triPct) : 0;
    return `<tr>
      <td>${esc(d.date || '-')}</td>
      <td><div class="usage-daily-bar" style="width:${Math.max(8, Math.round((tt / max) * 100))}%">
        <span class="triage" style="width:${triPct}%"></span><span class="analysis" style="width:${anaPct}%"></span>
      </div></td>
      <td>${fmtTokens(tt)}</td>
      <td>${fmtTokens(tri.total_tokens)}</td>
      <td>${fmtTokens(ana.total_tokens)}</td>
      <td>${fmtUsageCalls(t)}</td>
    </tr>`;
  }).join('')}</tbody></table>`;
}

function renderUsageByTask(byTask) {
  const body = document.getElementById('aiUsageByTask');
  if (!body) return;
  const rows = byTask || [];
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty">暂无按任务统计</td></tr>';
    return;
  }
  body.innerHTML = rows.map(r => `<tr>
    <td>#${r.task_id || '-'} ${esc(r.task_name || '')}</td>
    <td>${fmtTokens((r.total || {}).total_tokens)}</td>
    <td>${fmtTokens((r.list_triage || {}).total_tokens)}</td>
    <td>${fmtTokens((r.analysis || {}).total_tokens)}</td>
    <td>${fmtUsageCalls(r.total)}</td>
  </tr>`).join('');
}

function renderAnalysisUsage(usage) {
  if (!usage) return;
  const period = usage.period || {};
  const total = period.total || {};
  const byPhase = period.by_phase || {};
  const today = usage.today || {};
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
  set('aiUsageTotalTokens', fmtTokens(total.total_tokens));
  set('aiUsageTodayTokens', fmtTokens(today.total_tokens));
  set('aiUsageApiCalls', fmtUsageCalls(total));
  renderUsagePhaseBars(byPhase, total.total_tokens);
  renderUsageInOut(total);
  renderUsageDaily(usage.daily);
  renderUsageByTask(usage.by_task);
}

async function loadAnalysisUsage() {
  const daysEl = document.getElementById('aiUsageDays');
  const taskSel = document.getElementById('aiLogTask');
  const days = daysEl ? daysEl.value : '30';
  try {
    const params = new URLSearchParams({ days: String(days) });
    const taskId = taskSel ? taskSel.value : '';
    if (taskId) params.set('task_id', taskId);
    const d = await api('/api/analysis/usage?' + params.toString());
    renderAnalysisUsage(d.usage);
  } catch (e) {
    renderUsageDaily([]);
    const body = document.getElementById('aiUsageByTask');
    if (body) body.innerHTML = `<tr><td colspan="5" class="empty">加载失败: ${esc(e.message || '')}</td></tr>`;
  }
}

function onAiLogTaskFilterChange() {
  loadAnalysisUsage();
  loadAnalysisLogs();
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
      body.innerHTML = '<tr><td colspan="10" class="empty">暂无批次日志</td></tr>';
      return;
    }
    body.innerHTML = logs.map(l => `<tr>
      <td>${fmtTime(l.created_at)}</td>
      <td>${esc(aiPhaseLabel(l.phase))}</td>
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
  loadAnalysisUsage();
  aiLogTimer = setInterval(function() {
    loadAnalysisLogs();
    loadAnalysisUsage();
  }, 4000);
}

function stopAiLogPoll() {
  if (aiLogTimer) {
    clearInterval(aiLogTimer);
    aiLogTimer = null;
  }
}

let partnerDetailState = { partnerId: null, partner: null, context: null, partnerTab: 'intel', taskId: null };

function showPartnerListView() {
  const list = document.getElementById('partnerListView');
  const detail = document.getElementById('partnerDetailView');
  if (list) list.style.display = '';
  if (detail) detail.style.display = 'none';
}

function showPartnerDetailView() {
  const list = document.getElementById('partnerListView');
  const detail = document.getElementById('partnerDetailView');
  if (list) list.style.display = 'none';
  if (detail) detail.style.display = '';
}

async function onPartnersTabActivate() {
  const partnerId = App.getQuery('partner_id');
  if (partnerId) {
    await openPartnerDetail(parseInt(partnerId, 10));
  } else {
    showPartnerListView();
    await loadPartners();
  }
}

function backToPartnerList() {
  App.setQuery({ partner_id: null, partner_tab: null, task_id: null });
  showPartnerListView();
  loadPartners();
}

function navigatePartnerIntel(partnerId) {
  App.navigatePartnerDetail(partnerId, { partner_tab: 'intel' });
}

async function navigatePartnerRaw(partnerId) {
  try {
    const d = await api('/api/partners/' + partnerId + '/context');
    App.navigatePartnerDetail(partnerId, {
      partner_tab: 'raw',
      task_id: d.default_task_id || null,
    });
  } catch (e) {
    toastMsg(e.message || '加载失败', true);
    App.navigatePartnerDetail(partnerId, { partner_tab: 'raw' });
  }
}

function renderPartnerDetailHeader() {
  const p = partnerDetailState.partner;
  const title = document.getElementById('partnerDetailTitle');
  const tags = document.getElementById('partnerDetailTags');
  if (!p || !title) return;
  title.textContent = p.name + ' #' + p.id;
  const bits = [];
  if (p.industry_cohort) bits.push('<span class="tag tag-medium">' + esc(p.industry_cohort) + '</span>');
  if (p.priority_tier) bits.push('<span class="tag tag-on">' + esc(p.priority_tier) + '</span>');
  bits.push('<span class="tag ' + (p.enabled ? 'tag-on' : 'tag-off') + '">' + (p.enabled ? '启用' : '停用') + '</span>');
  if (tags) tags.innerHTML = bits.join('');
}

function switchPartnerSubTab(tab, linkEl) {
  partnerDetailState.partnerTab = tab;
  document.querySelectorAll('.partner-subtabs .tab').forEach(function(el) {
    el.classList.toggle('active', el.getAttribute('data-partner-tab') === tab);
  });
  if (linkEl) linkEl.classList.add('active');
  const intelPane = document.getElementById('partnerIntelPane');
  const rawPane = document.getElementById('partnerRawPane');
  if (intelPane) intelPane.style.display = tab === 'intel' ? '' : 'none';
  if (rawPane) rawPane.style.display = tab === 'raw' ? '' : 'none';
  const patch = { partner_tab: tab };
  if (tab === 'intel') patch.task_id = null;
  else if (partnerDetailState.taskId) patch.task_id = partnerDetailState.taskId;
  App.setQuery(patch, true);
  if (tab === 'intel') loadPartnerIntelRecords();
  else loadPartnerRawPane();
}

async function openPartnerDetail(partnerId) {
  showPartnerDetailView();
  const partnerTab = App.getQuery('partner_tab') || 'intel';
  let taskId = App.getQuery('task_id');
  try {
    const [partnerRes, ctx] = await Promise.all([
      api('/api/partners/' + partnerId),
      api('/api/partners/' + partnerId + '/context'),
    ]);
    if (!partnerRes.ok || !partnerRes.partner) throw new Error(partnerRes.msg || '合作方不存在');
    if (!ctx.ok) throw new Error(ctx.msg || '加载上下文失败');
    partnerDetailState = {
      partnerId: partnerId,
      partner: partnerRes.partner,
      context: ctx,
      partnerTab: partnerTab,
      taskId: taskId ? parseInt(taskId, 10) : (ctx.default_task_id || null),
    };
    if (partnerTab === 'raw' && !partnerDetailState.taskId && ctx.default_task_id) {
      partnerDetailState.taskId = ctx.default_task_id;
      App.setQuery({ task_id: ctx.default_task_id }, true);
    }
    renderPartnerDetailHeader();
    document.querySelectorAll('.partner-subtabs .tab').forEach(function(el) {
      el.classList.toggle('active', el.getAttribute('data-partner-tab') === partnerTab);
    });
    switchPartnerSubTab(partnerTab);
  } catch (e) {
    toastMsg(e.message || '加载合作方详情失败', true);
    backToPartnerList();
  }
}

async function loadPartnerIntelRecords() {
  const body = document.getElementById('partnerIntelTableBody');
  const countEl = document.getElementById('partnerIntelCount');
  if (!body || !partnerDetailState.partnerId) return;
  const ctx = partnerDetailState.context || {};
  const mediumPlus = (ctx.counts && ctx.counts.intel_medium_plus) || 0;
  if (countEl) countEl.textContent = '(中及以上 ' + mediumPlus + ' 条)';
  const params = new URLSearchParams({
    partner_id: String(partnerDetailState.partnerId),
    relevance_min: 'medium',
    page: '1',
    page_size: '100',
  });
  try {
    const d = await api('/api/intel/records?' + params.toString());
    const rows = d.records || [];
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="8" class="empty">暂无中及以上相关度情报</td></tr>';
      return;
    }
    body.innerHTML = rows.map(function(r) {
      return '<tr class="clickable-row" onclick="openPartnerIntelDetail(' + r.id + ')">'
        + '<td>' + sourceTag(r.source) + '</td>'
        + '<td>' + relTag(r.relevance) + '</td>'
        + '<td>' + sentimentTag(r.sentiment_label, r.sentiment_score) + '</td>'
        + '<td>' + esc((r.risk_types || []).join('、') || '-') + '</td>'
        + '<td>' + fmtTime(r.published_at) + '</td>'
        + '<td>' + fmtTime(r.captured_at) + '</td>'
        + '<td class="truncate" title="' + esc(r.body || '') + '">' + esc((r.summary || r.title || '').slice(0, 80)) + '</td>'
        + '<td class="actions" onclick="event.stopPropagation()">'
        + '<button class="btn btn-gray btn-sm" onclick="openPartnerIntelDetail(' + r.id + ')">详情</button>'
        + (r.url ? ' <a href="' + esc(r.url) + '" target="_blank" class="link-muted">原文</a>' : '')
        + '</td></tr>';
    }).join('');
  } catch (e) {
    body.innerHTML = '<tr><td colspan="8" class="msg-err">' + esc(e.message) + '</td></tr>';
  }
}

function openPartnerIntelDetail(intelId) {
  App.setQuery({ tab: 'intel', intel_id: intelId, partner_id: partnerDetailState.partnerId });
  App.switchAppTab('intel');
}

function loadPartnerRawPane() {
  const ctx = partnerDetailState.context || {};
  const tasks = ctx.tasks || [];
  const noTasksEl = document.getElementById('partnerRawNoTasks');
  const withTasksEl = document.getElementById('partnerRawWithTasks');
  if (!tasks.length) {
    if (noTasksEl) noTasksEl.style.display = '';
    if (withTasksEl) withTasksEl.style.display = 'none';
    return;
  }
  if (noTasksEl) noTasksEl.style.display = 'none';
  if (withTasksEl) withTasksEl.style.display = '';
  const sel = document.getElementById('partnerRawTask');
  if (sel) {
    sel.innerHTML = tasks.map(function(t) {
      return '<option value="' + t.id + '">#' + t.id + ' ' + esc(t.name || '') + '</option>';
    }).join('');
    if (partnerDetailState.taskId) sel.value = String(partnerDetailState.taskId);
    else if (ctx.default_task_id) {
      sel.value = String(ctx.default_task_id);
      partnerDetailState.taskId = ctx.default_task_id;
    }
  }
  loadPartnerRawRecords();
}

function onPartnerRawTaskChange() {
  const sel = document.getElementById('partnerRawTask');
  if (!sel || !sel.value) return;
  partnerDetailState.taskId = parseInt(sel.value, 10);
  App.setQuery({ task_id: partnerDetailState.taskId }, true);
  loadPartnerRawRecords();
}

async function loadPartnerRawRecords() {
  const body = document.getElementById('partnerRawTableBody');
  const countEl = document.getElementById('partnerRawCount');
  if (!body || !partnerDetailState.partnerId || !partnerDetailState.taskId) return;
  const params = new URLSearchParams({
    partner_id: String(partnerDetailState.partnerId),
    task_id: String(partnerDetailState.taskId),
    page: '1',
    page_size: '100',
  });
  try {
    const d = await api('/api/raw/records?' + params.toString());
    const rows = d.records || [];
    if (countEl) countEl.textContent = '(共 ' + (d.total || rows.length) + ' 条)';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="8" class="empty">当前任务下暂无源数据（list 阶段可能尚未绑定 partner）</td></tr>';
      return;
    }
    body.innerHTML = rows.map(function(r) {
      return '<tr class="clickable-row" onclick="openPartnerRawDetail(' + r.id + ')">'
        + '<td>' + r.id + '</td><td>#' + r.task_id + '</td>'
        + '<td>' + sourceTag(r.source) + '</td><td>' + esc(r.keyword || '') + '</td>'
        + '<td class="truncate" title="' + esc(r.title_summary || '') + '">' + esc(r.title_summary || '—') + '</td>'
        + '<td>' + (fmtTime(r.published_at) || '—') + '</td>'
        + '<td>' + fmtTime(r.created_at) + '</td>'
        + '<td>' + (r.analyze_status === 'analyzed' ? '已分析' : '待分析') + '</td></tr>';
    }).join('');
  } catch (e) {
    body.innerHTML = '<tr><td colspan="8" class="msg-err">' + esc(e.message) + '</td></tr>';
  }
}

function openPartnerRawDetail(rawId) {
  App.setQuery({
    tab: 'raw',
    raw_id: rawId,
    partner_id: partnerDetailState.partnerId,
    task_id: partnerDetailState.taskId,
  });
  App.switchAppTab('raw');
}

function refreshPurgeTaskSelect(selectedTaskId) {
  const sel = document.getElementById('purgeTaskId');
  if (!sel) return;
  sel.innerHTML = tasks.map(function(t) {
    return '<option value="' + t.id + '">#' + t.id + ' ' + esc(t.name || '') + '</option>';
  }).join('');
  if (selectedTaskId) sel.value = String(selectedTaskId);
}

function refreshPurgePartnerSelect(selectedPartnerId) {
  const sel = document.getElementById('purgePartnerId');
  if (!sel) return;
  sel.innerHTML = '<option value="">全部合作方</option>' + partners.map(function(p) {
    return '<option value="' + p.id + '">' + esc(p.name) + '</option>';
  }).join('');
  if (selectedPartnerId) sel.value = String(selectedPartnerId);
}

function buildPurgeBody(dryRun) {
  const taskId = parseInt(document.getElementById('purgeTaskId').value, 10);
  const partnerVal = document.getElementById('purgePartnerId').value;
  const publishedBefore = document.getElementById('purgePublishedBefore').value || null;
  const body = { task_id: taskId, dry_run: !!dryRun };
  if (partnerVal) body.partner_id = parseInt(partnerVal, 10);
  if (publishedBefore) body.published_before = publishedBefore;
  return body;
}

async function runPurgePreview() {
  const kind = document.getElementById('purgeKind').value;
  const url = kind === 'raw' ? '/api/admin/purge/raw' : '/api/admin/purge/intel';
  const msg = document.getElementById('purgePreviewMsg');
  const d = await api(url, { method: 'POST', body: JSON.stringify(buildPurgeBody(true)) });
  if (msg) msg.textContent = '预览：将匹配 ' + (d.matched_count || 0) + ' 条';
  return d.matched_count || 0;
}

async function openPurgeModal(opts) {
  opts = opts || {};
  if (!App.isAdmin && App.authEnabled) {
    toastMsg('需要管理员权限', true);
    return;
  }
  if (!tasks.length) await loadTasks();
  if (!partners.length) await loadPartners();
  refreshPurgeTaskSelect(opts.taskId);
  refreshPurgePartnerSelect(opts.partnerId || '');
  document.getElementById('purgeKind').value = opts.kind || 'intel';
  document.getElementById('purgePublishedBefore').value = opts.publishedBefore || '';
  document.getElementById('purgePreviewMsg').textContent = '';
  UiShell.modal({
    title: '批量清理数据',
    bodyHtml: '',
    wide: true,
    confirmLabel: '预览并确认删除',
    cancelLabel: '取消',
    onMount: function(wrap) {
      mountHiddenForm(wrap, 'purgeFormFields');
    },
    onClose: function() { restoreHiddenForm('purgeFormFields'); },
    onConfirm: async function() {
      let matched = 0;
      try {
        matched = await runPurgePreview();
      } catch (e) {
        toastMsg(e.message || '预览失败', true);
        return false;
      }
      if (!matched) {
        toastMsg('没有匹配的记录', true);
        return false;
      }
      const ok = await UiShell.confirm('确定删除 ' + matched + ' 条记录？此操作不可撤销。', '确认清理');
      if (!ok) return false;
      const kind = document.getElementById('purgeKind').value;
      const url = kind === 'raw' ? '/api/admin/purge/raw' : '/api/admin/purge/intel';
      try {
        const d = await api(url, { method: 'POST', body: JSON.stringify(buildPurgeBody(false)) });
        toastMsg('已删除 ' + (d.deleted_count || 0) + ' 条');
        await loadTasks();
        await loadPartners();
        if (partnerDetailState.partnerId) await openPartnerDetail(partnerDetailState.partnerId);
        return true;
      } catch (e) {
        toastMsg(e.message || '删除失败', true);
        return false;
      }
    },
  });
}

function openPurgeModalFromPartnerDetail() {
  const ctx = partnerDetailState.context || {};
  openPurgeModal({
    taskId: partnerDetailState.taskId || ctx.default_task_id,
    partnerId: partnerDetailState.partnerId,
  });
}

async function loadPartners() {
  const preservedPartnerIds = isTaskFormVisible() ? getSelectedPartnerIds() : null;
  const d = await api('/api/partners');
  partners = d.partners || [];
  refreshPartnerSelects();
  if (preservedPartnerIds !== null) {
    renderPartnerChecks(preservedPartnerIds);
  }
  const body = document.getElementById('partnerTableBody');
  if (!body) return;
  if (!partners.length) {
    body.innerHTML = '<tr><td colspan="10" class="empty">暂无合作方，点击「添加合作方」创建</td></tr>';
    return;
  }
  body.innerHTML = partners.map(function(p) {
    const st = p.stats || {};
    const intelLabel = (st.intel_medium_plus || 0) + '/' + (st.intel_total || 0);
    const rawLabel = st.default_task_id != null ? String(st.raw_total || 0) : '-';
    return `<tr>
    <td>${p.id}</td>
    <td><b>${esc(p.name)}</b></td>
    <td><button type="button" class="partner-stat-link" onclick="navigatePartnerIntel(${p.id})">${intelLabel}</button></td>
    <td><button type="button" class="partner-stat-link" onclick="navigatePartnerRaw(${p.id})">${rawLabel}</button></td>
    <td class="truncate" title="${esc((p.aliases||[]).join('、'))}">${esc((p.aliases||[]).join('、') || '-')}</td>
    <td class="truncate" title="${esc((p.exclude_words||[]).join('、'))}">${esc((p.exclude_words||[]).join('、') || '-')}</td>
    <td class="truncate" title="${esc((p.monitor_keywords||[]).join('、'))}">${esc((p.monitor_keywords||[]).join('、') || '-')}</td>
    <td><span class="tag ${p.enabled ? 'tag-on' : 'tag-off'}">${p.enabled ? '启用' : '停用'}</span></td>
    <td>${fmtTime(p.updated_at)}</td>
    <td class="actions col-actions">
      <button class="btn btn-gray btn-sm" onclick="navigatePartnerIntel(${p.id})">查看情报</button>
      <button class="btn btn-gray btn-sm" onclick="navigatePartnerRaw(${p.id})">查看源数据</button>
      <button class="btn btn-gray btn-sm" onclick="openPartnerModal(${p.id})">编辑</button>
      <button class="btn btn-gray btn-sm" onclick="togglePartner(${p.id})">${p.enabled ? '停用' : '启用'}</button>
      <button class="btn btn-red btn-sm" onclick="deletePartner(${p.id})">删除</button>
    </td>
  </tr>`;
  }).join('');
}

function resetPartnerForm() {
  document.getElementById('editPartnerId').value = '';
  document.getElementById('pName').value = '';
  document.getElementById('pAliases').value = '';
  document.getElementById('pExclude').value = '';
  document.getElementById('pMonitorKw').value = '';
  document.getElementById('pTimeoutXhs').value = '';
  document.getElementById('pTimeoutHeimao').value = '';
  document.getElementById('pCohort').value = '';
  document.getElementById('pPriorityTier').value = 'P1';
  document.getElementById('pNotes').value = '';
  document.getElementById('pEnabled').checked = true;
  clearCohortSuggestChips();
}

function clearCohortSuggestChips() {
  const el = document.getElementById('pCohortSuggestChips');
  if (el) el.innerHTML = '';
}

function renderCohortSuggestChips(data) {
  const wrap = document.getElementById('pCohortSuggestChips');
  if (!wrap) return;
  if (!data || !data.ok) {
    wrap.innerHTML = '<span class="muted">' + esc(data && data.msg ? data.msg : '暂无推荐') + '</span>';
    return;
  }
  const items = data.candidates || [];
  if (!items.length) {
    wrap.innerHTML = '<span class="muted">暂无推荐候选</span>';
    return;
  }
  wrap.innerHTML = items.map(function(it) {
    const meta = it.is_new
      ? '<span class="tag tag-medium">新建</span>'
      : (it.partner_count > 0
        ? '<span class="tag tag-on">已有·' + it.partner_count + '家</span>'
        : '<span class="tag tag-on">已有</span>');
    return '<button type="button" class="cohort-chip" data-cohort="' + esc(it.cohort) + '">' +
      '<span class="chip-label">' + esc(it.cohort) + '</span>' +
      '<span class="chip-meta">' + meta + '</span></button>';
  }).join('');
  wrap.querySelectorAll('.cohort-chip').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.getElementById('pCohort').value = btn.getAttribute('data-cohort') || '';
      toastMsg('已填入 cohort');
    });
  });
}

async function fetchCohortSuggestions() {
  const name = document.getElementById('pName').value.trim();
  if (!name) { toastMsg('请先填写名称', true); return; }
  const btn = document.getElementById('pCohortSuggestBtn');
  if (btn) { btn.disabled = true; btn.textContent = '推荐中…'; }
  const aliases = document.getElementById('pAliases').value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
  const editId = document.getElementById('editPartnerId').value;
  const body = { name, aliases };
  if (editId) body.exclude_partner_id = parseInt(editId, 10);
  let d;
  try {
    d = await api('/api/partners/suggest-cohort', { method: 'POST', body: JSON.stringify(body) });
  } catch (e) {
    toastMsg(e.message || '获取推荐失败', true);
    d = { ok: false, msg: e.message };
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '获取推荐'; }
  }
  renderCohortSuggestChips(d);
  if (d.ok && d.reason) toastMsg(d.reason);
}

function editPartner(id) {
  const p = partners.find(x => x.id === id);
  if (!p) return;
  document.getElementById('editPartnerId').value = id;
  document.getElementById('pName').value = p.name || '';
  document.getElementById('pAliases').value = (p.aliases || []).join(', ');
  document.getElementById('pExclude').value = (p.exclude_words || []).join(', ');
  document.getElementById('pMonitorKw').value = (p.monitor_keywords || []).join(', ');
  const st = p.source_timeouts || {};
  document.getElementById('pTimeoutXhs').value = st.xhs != null ? st.xhs : '';
  document.getElementById('pTimeoutHeimao').value = st.heimao != null ? st.heimao : '';
  document.getElementById('pCohort').value = p.industry_cohort || '';
  document.getElementById('pPriorityTier').value = p.priority_tier || 'P1';
  document.getElementById('pNotes').value = p.notes || '';
  document.getElementById('pEnabled').checked = !!p.enabled;
  clearCohortSuggestChips();
}

function openPartnerModal(id) {
  if (id) editPartner(id); else resetPartnerForm();
  UiShell.modal({
    title: id ? '编辑合作方 #' + id : '添加合作方',
    bodyHtml: '',
    wide: true,
    confirmLabel: '保存',
    cancelLabel: '取消',
    onMount: function(wrap) {
      mountHiddenForm(wrap, 'partnerFormFields');
      const btn = document.getElementById('pCohortSuggestBtn');
      if (btn) btn.onclick = fetchCohortSuggestions;
    },
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
    industry_cohort: document.getElementById('pCohort').value.trim(),
    priority_tier: document.getElementById('pPriorityTier').value,
    priority_source: 'manual',
    notes: document.getElementById('pNotes').value.trim(),
    enabled: document.getElementById('pEnabled').checked,
  };
  const xhsT = parseInt(document.getElementById('pTimeoutXhs').value, 10);
  const hmT = parseInt(document.getElementById('pTimeoutHeimao').value, 10);
  const sourceTimeouts = {};
  if (!isNaN(xhsT) && xhsT >= 60) sourceTimeouts.xhs = xhsT;
  if (!isNaN(hmT) && hmT >= 60) sourceTimeouts.heimao = hmT;
  if (Object.keys(sourceTimeouts).length) payload.source_timeouts = sourceTimeouts;
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

function renderRunDetailError(message) {
  if (!message) return '';
  return '<div class="run-detail-error-block">'
    + '<div class="run-detail-error-head">' + esc(runFieldMeta('error_message').label) + '</div>'
    + '<pre class="run-detail-error-trace">' + esc(message) + '</pre>'
    + '</div>';
}

function renderRunDetailGlossary() {
  const groups = RUN_GLOSSARY_GROUPS.map(function(group) {
    const rows = group.keys.map(function(key) {
      const m = runFieldMeta(key);
      const help = m.help ? esc(m.help) : '—';
      return '<tr><td class="field-key"><code>' + esc(key) + '</code></td>'
        + '<td class="field-help">' + help + '</td></tr>';
    }).join('');
    return '<div class="run-glossary-group">'
      + '<div class="run-glossary-group-title">' + esc(group.title) + '</div>'
      + '<table class="run-glossary-table"><thead><tr><th>Field</th><th>Description</th></tr></thead>'
      + '<tbody>' + rows + '</tbody></table></div>';
  }).join('');
  return '<details class="run-detail-glossary"><summary>Field reference</summary>'
    + '<div class="run-glossary-groups">' + groups + '</div></details>';
}

function keywordSubtaskStatusTag(st) {
  const map = {
    pending: ['tag-off', '待执行'],
    running: ['tag-medium', '运行中'],
    done: ['tag-on', '完成'],
    failed: ['tag-high', '失败'],
    skipped: ['tag-off', '跳过'],
  };
  const m = map[st] || ['tag-off', st || '-'];
  return '<span class="tag ' + m[0] + '">' + m[1] + '</span>';
}

function normalizePhaseTiming(pt) {
  pt = pt || {};
  const triage = pt.triage_ms || pt.analyze_ms || 0;
  return {
    list_crawl_ms: pt.list_crawl_ms || 0,
    triage_ms: triage,
    investigation_ms: pt.investigation_ms || 0,
  };
}

function sumSourcePhaseTiming(subItems, timing) {
  let list = 0;
  let triage = 0;
  let invest = 0;
  let hasSub = false;
  (subItems || []).forEach(function(it) {
    hasSub = true;
    const pt = normalizePhaseTiming(it.phase_timing_ms);
    list += pt.list_crawl_ms;
    triage += pt.triage_ms;
    invest += pt.investigation_ms;
  });
  const tw = timing || {};
  if (hasSub) {
    return {
      list_crawl_ms: list,
      triage_ms: triage,
      investigation_ms: invest,
      intel_analyze_ms: tw.intel_analyze_ms || 0,
    };
  }
  return {
    list_crawl_ms: tw.list_crawl_ms || tw.crawl_ms || 0,
    triage_ms: tw.triage_ms || 0,
    investigation_ms: tw.investigation_crawl_ms || 0,
    intel_analyze_ms: tw.intel_analyze_ms || tw.analyze_ms || 0,
  };
}

function renderPhaseTimingSummary(timing, subItems) {
  const t = sumSourcePhaseTiming(subItems, timing);
  const parts = [
    '列表爬取 ' + fmtDuration(t.list_crawl_ms),
    '初筛 ' + fmtDuration(t.triage_ms),
    '详情勘察 ' + fmtDuration(t.investigation_ms),
  ];
  if (t.intel_analyze_ms > 0) {
    parts.push('情报分析 ' + fmtDuration(t.intel_analyze_ms));
  }
  const crawlPhase = t.list_crawl_ms + t.triage_ms + t.investigation_ms;
  let html = '<p class="meta">Run 累计：' + parts.join(' · ') + '</p>';
  if (crawlPhase > 0) {
    html += '<p class="meta muted" style="margin-top:4px;font-size:12px">爬取阶段合计 '
      + fmtDuration(crawlPhase) + '（与子任务三列相加一致）</p>';
  }
  return html;
}

function subtaskDetailStatusTag(code, label) {
  const map = {
    queued: ['tag-off', label || '排队'],
    list_crawl: ['tag-medium', label || '爬取列表'],
    triage: ['tag-medium', label || '初筛'],
    investigation: ['tag-medium', label || '勘察详情'],
    analyze: ['tag-on', label || '初筛'],
    intel_analyze: ['tag-on', label || '情报分析'],
    done: ['tag-on', label || '完成'],
    failed: ['tag-high', label || '失败'],
    skipped: ['tag-off', label || '已跳过'],
  };
  const m = map[code] || ['tag-off', label || code || '-'];
  return '<span class="tag ' + m[0] + '">' + esc(m[1]) + '</span>';
}

function fmtSubtaskPhaseMs(pt, key) {
  if (!pt) return '-';
  const norm = normalizePhaseTiming(pt);
  const v = norm[key];
  return v > 0 ? fmtDuration(v) : '-';
}

function fmtXhsAccount(it) {
  if (!it) return '-';
  const label = it.account_label || (it.stats && it.stats.account_label) || '';
  const id = it.account_id || (it.stats && it.stats.account_id) || '';
  if (label && id) return label + ' (' + id + ')';
  return label || id || '-';
}

function renderSourceSubtaskItems(items, task, sourceId) {
  items = items || [];
  if (!items.length) {
    return '<p class="muted">无子任务记录</p>';
  }
  const failedIds = items.filter(function(it) {
    return it.detail_status === 'failed' && it.keyword_run_id;
  }).map(function(it) { return it.keyword_run_id; });
  const showInvCol = sourceId === 'heimao' || items.some(function(x) {
    return x.stats && x.stats.progress_total;
  });
  const rows = items.map(function(it) {
    const pt = normalizePhaseTiming(it.phase_timing_ms);
    const listCount = it.stats && it.stats.list_count != null ? it.stats.list_count : '-';
    const invProg = fmtInvestigationProgress(it);
    const err = it.error_message || '';
    const acct = sourceId === 'xhs' ? fmtXhsAccount(it) : '';
    return '<tr data-subtask-id="' + esc(it.id || '') + '">'
      + '<td class="truncate" title="' + esc(it.label || '') + '">' + esc(it.label || '-') + '</td>'
      + '<td class="truncate">' + esc(it.cohort || '-') + '</td>'
      + (sourceId === 'xhs' ? '<td class="truncate meta" title="' + esc(acct) + '">' + esc(acct) + '</td>' : '')
      + '<td>' + subtaskDetailStatusTag(it.detail_status, it.detail_label) + '</td>'
      + (showInvCol ? '<td class="phase-ms">' + esc(invProg) + '</td>' : '')
      + '<td class="phase-ms">' + fmtSubtaskPhaseMs(pt, 'list_crawl_ms') + '</td>'
      + '<td class="phase-ms">' + fmtSubtaskPhaseMs(pt, 'triage_ms') + '</td>'
      + '<td class="phase-ms">' + fmtSubtaskPhaseMs(pt, 'investigation_ms') + '</td>'
      + '<td>' + (it.timeout_sec ? (it.timeout_sec + 's') : '-') + '</td>'
      + '<td>' + listCount + '</td>'
      + '<td class="truncate" title="' + esc(err) + '">' + esc(err.slice(0, 40)) + '</td></tr>';
  }).join('');
  let actions = '';
  if (failedIds.length && task && task.id && sourceId === 'xhs') {
    actions = '<div class="btn-group" style="margin:8px 0">'
      + '<button type="button" class="btn btn-orange btn-sm" onclick="retryFailedKeywords('
      + task.id + ',' + JSON.stringify(failedIds) + ')">重跑失败 (' + failedIds.length + ')</button></div>';
  }
  return actions
    + '<table class="run-detail-table subtask-items-table"><thead><tr>'
    + '<th>关键词/子任务</th><th>Cohort</th>'
    + (sourceId === 'xhs' ? '<th>账号</th>' : '')
    + '<th>状态</th>'
    + (showInvCol ? '<th>勘察进度</th>' : '')
    + '<th>列表爬取</th><th>初筛</th><th>详情勘察</th>'
    + '<th>超时</th><th>列表数</th><th>错误</th>'
    + '</tr></thead><tbody class="subtask-items-body" data-source-id="' + esc(sourceId || '') + '">'
    + rows + '</tbody></table>';
}

function renderKeywordSubtasks(keywords, run, task) {
  if (!keywords || !keywords.length) {
    return '<p class="muted">无 keyword 子任务记录</p>';
  }
  const failedIds = keywords.filter(function(k) { return k.status === 'failed'; }).map(function(k) { return k.id; });
  const rows = keywords.map(function(k) {
    const acct = k.source_id === 'xhs' ? fmtXhsAccount(k) : '';
    return '<tr><td>' + esc(k.keyword || '') + '</td>'
      + '<td class="truncate">' + esc(k.cohort || '-') + '</td>'
      + (k.source_id === 'xhs' ? '<td class="truncate meta" title="' + esc(acct) + '">' + esc(acct) + '</td>' : '')
      + '<td>' + keywordSubtaskStatusTag(k.status) + '</td>'
      + '<td>' + esc(k.phase || '-') + '</td>'
      + '<td>' + (k.timeout_sec ? (k.timeout_sec + 's') : '-') + '</td>'
      + '<td>' + (k.stats && k.stats.list_count != null ? k.stats.list_count : '-') + '</td>'
      + '<td class="truncate" title="' + esc(k.error_message || '') + '">' + esc((k.error_message || '').slice(0, 40)) + '</td></tr>';
  }).join('');
  let actions = '';
  if (failedIds.length && task && task.id) {
    actions = '<div class="btn-group" style="margin:8px 0">'
      + '<button type="button" class="btn btn-orange btn-sm" onclick="retryFailedKeywords('
      + task.id + ',' + JSON.stringify(failedIds) + ')">重跑失败 keyword (' + failedIds.length + ')</button></div>';
  }
  const hasXhs = keywords.some(function(k) { return k.source_id === 'xhs'; });
  return actions
    + '<table class="run-detail-table"><thead><tr>'
    + '<th>关键词</th><th>Cohort</th>'
    + (hasXhs ? '<th>账号</th>' : '')
    + '<th>状态</th><th>阶段</th><th>超时</th><th>列表</th><th>错误</th>'
    + '</tr></thead><tbody>' + rows + '</tbody></table>';
}

function sourceSubtaskStatusTag(st) {
  const map = {
    running: ['tag-on', '运行中'],
    pending: ['tag-medium', '待执行'],
    done: ['tag-on', '完成'],
    failed: ['tag-high', '失败'],
    paused: ['tag-off', '已暂停'],
    stopped: ['tag-high', '已终止'],
    idle: ['tag-off', '无队列'],
  };
  const m = map[st] || ['tag-off', st || '-'];
  return '<span class="tag ' + m[0] + '">' + m[1] + '</span>';
}

function renderSourceQueueSummary(q) {
  if (!q || !q.total) return '<span class="muted">无队列项</span>';
  return '队列 ' + (q.done || 0) + '/' + q.total
    + (q.pending ? ' · 待 ' + q.pending : '')
    + (q.claimed ? ' · 执行 ' + q.claimed : '')
    + (q.failed ? ' · 失败 ' + q.failed : '')
    + (q.skipped ? ' · 跳过 ' + q.skipped : '');
}

function renderSourceKeywordSummary(k) {
  if (!k || !k.total) return '';
  return 'keyword ' + (k.done || 0) + '/' + k.total
    + (k.running ? ' · 运行 ' + k.running : '')
    + (k.failed ? ' · 失败 ' + k.failed : '');
}

function taskRunTooltip(t) {
  if (t && t.crawl_only) return '仅爬取，不执行 AI 分析';
  return (t && t.run_block_reason) || '增量爬取+分析';
}

function runAnalyzeDeferredTag(run) {
  if (!run || !run.crawl_only) return '';
  const st = run.stats || {};
  if (!st.analyze_deferred) return '';
  const n = st.pending_analyze_raw_count != null ? st.pending_analyze_raw_count : '?';
  return '<span class="tag tag-pending-analyze" title="待分析 raw 条数">待分析 · ' + n + '</span>';
}

function phaseLabel(phase) {
  const map = {
    pending: '待执行',
    list: '列表爬取',
    triage: '初筛',
    investigation: '勘察',
    done: '完成',
    legacy_crawl: 'Legacy 爬取',
    keyword_pipeline: '关键词流水线',
    list_crawl: '列表爬取',
    crawl: '爬取',
    analyze: 'AI 分析',
    crawl_done: '爬取完成（待分析）',
  };
  return map[phase] || phase || '—';
}

function renderSourcePhaseTable(src) {
  const aw = src.active_work;
  const ps = src.phase_summary || {};
  const byPhase = ps.by_phase || {};
  const rows = [];
  const phaseOrder = ['list', 'triage', 'investigation', 'done', 'pending'];
  phaseOrder.forEach(function(ph) {
    const bucket = byPhase[ph];
    if (!bucket) return;
    const running = bucket.running || 0;
    const done = bucket.done || 0;
    const pending = bucket.pending || 0;
    const failed = bucket.failed || 0;
    if (!running && !done && !pending && !failed) return;
    let status = pending ? ('待 ' + pending) : '';
    if (running) status += (status ? ' · ' : '') + '运行 ' + running;
    if (done) status += (status ? ' · ' : '') + '完成 ' + done;
    if (failed) status += (status ? ' · ' : '') + '失败 ' + failed;
    rows.push('<tr><td>' + esc(phaseLabel(ph)) + '</td><td>' + esc(status) + '</td><td>'
      + ((ph === (aw && aw.phase) && aw.elapsed_ms) ? fmtDuration(aw.elapsed_ms) : '—') + '</td></tr>');
  });
  if (!rows.length) return '';
  return '<table class="run-detail-table source-phase-table"><thead><tr>'
    + '<th>阶段</th><th>子任务</th><th>当前用时</th></tr></thead><tbody>'
    + rows.join('') + '</tbody></table>';
}

function renderSourceTimingBlock(src) {
  const aw = src.active_work;
  const ps = src.phase_summary || {};
  const subItems = src.subtask_items || [];
  let html = renderPhaseTimingSummary(src.timing, subItems);
  if (!html && ps.done_total_ms) {
    html = '<p class="meta">已完成 keyword 合计 ' + fmtDuration(ps.done_total_ms) + '</p>';
  }
  if (aw) {
    html += '<p class="meta">当前阶段：<strong>' + esc(phaseLabel(aw.phase)) + '</strong>'
      + ' · 已用 ' + fmtDuration(aw.elapsed_ms || 0)
      + (aw.progress && aw.progress.total
        ? ' · 本批 ' + (aw.progress.done || 0) + '/' + aw.progress.total
          + (aw.progress.investigation_total ? ' · 总 ' + aw.progress.investigation_total + ' 条' : '')
        : (aw.label ? ' · ' + esc(aw.label) : ''))
      + '</p>';
  }
  const phaseTable = renderSourcePhaseTable(src);
  if (phaseTable) html += phaseTable;
  return html || '<p class="muted">暂无阶段数据</p>';
}

function fmtInvestigationProgress(it) {
  const st = it.stats || {};
  if (st.progress_total) {
    return (st.progress_done || 0) + '/' + st.progress_total;
  }
  return '-';
}

function renderCompactSourceProgress(src) {
  const q = src.queue || {};
  const k = src.keywords || {};
  const inv = src.investigation || {};
  const aw = src.active_work;
  const tw = src.timing || {};
  let prog = '';
  if (k.total) prog += 'kw ' + (k.done || 0) + '/' + k.total;
  if (q.total) prog += (prog ? ' · ' : '') + '队列 ' + (q.done || 0) + '/' + q.total;
  if (inv.total) {
    prog += (prog ? ' · ' : '') + '勘察 ' + (inv.finished != null ? inv.finished : ((inv.done || 0) + (inv.failed || 0) + (inv.skipped || 0)))
      + '/' + inv.total;
    if (inv.pending) prog += ' (待' + inv.pending + ')';
  }
  let phaseTxt = '';
  if (aw && aw.phase) {
    phaseTxt = phaseLabel(aw.phase) + ' ' + fmtDuration(aw.elapsed_ms || 0);
    if (aw.progress && aw.progress.total) {
      phaseTxt += ' · ' + (aw.progress.done || 0) + '/' + aw.progress.total;
    } else if (aw.label) {
      phaseTxt += ' · ' + aw.label;
    }
  }
  const t = sumSourcePhaseTiming(src.subtask_items, tw);
  const runMs = t.list_crawl_ms + t.triage_ms + t.investigation_ms + t.intel_analyze_ms;
  return '<div class="task-source-line">'
    + sourceTag(src.source_id) + ' ' + sourceSubtaskStatusTag(src.status)
    + (src.halt ? ' <span class="meta">(' + esc(src.halt === 'pause' ? '暂停' : '终止') + ')</span>' : '')
    + (prog ? ' <span class="meta">' + prog + '</span>' : '')
    + (phaseTxt ? ' <span class="meta">· ' + esc(phaseTxt) + '</span>' : '')
    + (runMs ? ' <span class="meta">· 累计 ' + fmtDuration(runMs) + '</span>' : '')
    + '</div>';
}

function renderTaskSourceProgress(t) {
  const sources = (t.progress && t.progress.sources) || [];
  let html = '';
  if (sources.length) {
    html = '<div class="task-source-progress">' + sources.map(renderCompactSourceProgress).join('') + '</div>';
  } else {
    html = formatTaskSubtasksLegacy(t);
  }
  const ad = (t.progress && t.progress.analyze_drain);
  if (ad && (ad.done || ad.pending_detail != null)) {
    const total = (ad.done || 0) + (ad.pending_detail || 0);
    html += '<div class="task-source-line"><span class="meta">AI 分析 ' + (ad.done || 0) + '/' + total
      + (ad.last_trigger ? (' · ' + esc(ad.last_trigger)) : '') + '</span></div>';
  }
  return html;
}

function formatTaskSubtasksLegacy(t) {
  const prog = t.progress || {};
  const st = prog.subtasks;
  if (!st || !st.total) return '';
  let s = '<br><span class="meta">keyword ' + (st.done || 0) + '/' + st.total;
  if (st.failed) s += ' · 失败 ' + st.failed;
  if (st.running) s += ' · 运行 ' + st.running;
  return s + '</span>';
}

function taskRowSignature(t) {
  const prog = t.progress || {};
  return JSON.stringify({
    status: t.status,
    raw: t.raw_count,
    intel: t.intel_count,
    can_pause: t.can_pause,
    can_stop: t.can_stop,
    can_resume: t.can_resume,
    can_run: t.can_run,
    run_block: t.run_block_reason,
    sources: prog.sources,
    subtasks: prog.subtasks,
    phase: prog.phase,
    analyze_drain: prog.analyze_drain,
    last_run: t.last_run ? {
      id: t.last_run.id,
      status: t.last_run.status,
      crawl_ms: t.last_run.crawl_duration_ms,
      analyze_ms: t.last_run.analyze_duration_ms,
      finished_at: t.last_run.finished_at,
      started_at: t.last_run.started_at,
      trigger: t.last_run.trigger,
    } : null,
    schedule: t.schedule && t.schedule.enabled,
    next_run: t.next_run_at,
    name: t.name,
    partners: t.partner_ids,
    sources_cfg: t.sources,
    max_pages: t.max_pages,
  });
}

let taskRowSigs = {};
let taskDetailRawRowSigs = {};
let taskDetailIntelRowSigs = {};

function buildTaskActionsHtml(t) {
  return (t.can_pause ? '<button class="btn btn-orange btn-sm" onclick="pauseTaskById(' + t.id + ')">暂停</button>' : '')
    + (t.can_stop ? '<button class="btn btn-red btn-sm" onclick="stopTaskById(' + t.id + ',\'all\')">终止任务</button>' : '')
    + (t.can_resume ? '<button class="btn btn-primary btn-sm" onclick="resumeTaskById(' + t.id + ')">继续</button>' : '')
    + '<button class="btn btn-primary btn-sm" onclick="runTaskById(' + t.id + ')" ' + (!t.can_run ? 'disabled' : '') + ' title="' + esc(taskRunTooltip(t)) + '">执行</button>'
    + '<button class="btn btn-gray btn-sm" onclick="openTaskDetail(' + t.id + ')">详情</button>'
    + '<button class="btn btn-gray btn-sm" onclick="deleteTask(' + t.id + ')" '
    + (['crawling', 'analyzing'].includes(t.status) ? 'disabled' : '') + '>删除</button>';
}

function buildTaskRowHtml(t) {
  return '<tr class="task-row task-row-clickable" data-task-id="' + t.id + '" onclick="openTaskDetail(' + t.id + ')">'
    + '<td data-field="id">' + t.id + '</td>'
    + '<td class="truncate cell-name" data-field="name" title="' + esc(t.name || '') + '">' + esc(t.name || '-') + '</td>'
    + '<td class="cell-stack" data-field="status">' + statusTag(t.status)
    + renderTaskSourceProgress(t)
    + '<br><span class="meta">原始 ' + (t.raw_count || 0) + ' / 情报 ' + (t.intel_count || 0) + '</span></td>'
    + '<td class="truncate cell-partners" data-field="partners" title="' + esc(partnerNames(t.partner_ids)) + '">' + esc(partnerNames(t.partner_ids)) + '</td>'
    + '<td data-field="sources">' + ((t.sources || []).map(function(s) { return sourceTag(s); }).join(' ') || '-') + '</td>'
    + '<td data-field="pages">' + (t.max_pages || '-') + '</td>'
    + '<td class="cell-stack" data-field="lastrun">' + formatLastRun(t) + '</td>'
    + '<td class="cell-stack" data-field="created">' + fmtTime(t.created_at) + '</td>'
    + '<td class="actions actions-wrap col-actions" data-field="actions" onclick="event.stopPropagation()">'
    + buildTaskActionsHtml(t) + '</td></tr>';
}

function patchTaskRow(row, t) {
  const setField = function(field, html) {
    const el = row.querySelector('[data-field="' + field + '"]');
    if (el && el.innerHTML !== html) el.innerHTML = html;
  };
  setField('name', esc(t.name || '-'));
  if (row.querySelector('[data-field="name"]')) {
    row.querySelector('[data-field="name"]').setAttribute('title', t.name || '');
  }
  setField('status', statusTag(t.status) + renderTaskSourceProgress(t)
    + '<br><span class="meta">原始 ' + (t.raw_count || 0) + ' / 情报 ' + (t.intel_count || 0) + '</span>');
  setField('partners', esc(partnerNames(t.partner_ids)));
  if (row.querySelector('[data-field="partners"]')) {
    row.querySelector('[data-field="partners"]').setAttribute('title', partnerNames(t.partner_ids));
  }
  setField('sources', (t.sources || []).map(function(s) { return sourceTag(s); }).join(' ') || '-');
  setField('pages', String(t.max_pages || '-'));
  setField('lastrun', formatLastRun(t));
  setField('created', fmtTime(t.created_at));
  setField('actions', buildTaskActionsHtml(t));
}

function normalizeLegacyKeywordItems(keywords) {
  const labels = {
    queued: '排队', list_crawl: '爬取列表', investigation: '勘察详情',
    analyze: '分析', done: '完成', failed: '失败', skipped: '已跳过',
  };
  return (keywords || []).map(function(k) {
    let code = 'queued';
    if (k.status === 'done') code = 'done';
    else if (k.status === 'failed') code = 'failed';
    else if (k.status === 'skipped') code = 'skipped';
    else if (k.status === 'running') {
      if (k.phase === 'investigation') code = 'investigation';
      else if (k.phase === 'triage') code = 'analyze';
      else code = 'list_crawl';
    }
    return {
      id: 'kw:' + k.id,
      kind: 'keyword',
      keyword_run_id: k.id,
      label: k.keyword,
      cohort: k.cohort,
      detail_status: code,
      detail_label: labels[code],
      elapsed_ms: 0,
      phase_timing_ms: { list_crawl_ms: 0, triage_ms: 0, investigation_ms: 0 },
      timeout_sec: k.timeout_sec,
      stats: k.stats,
      error_message: k.error_message,
    };
  });
}

function renderRunSubtasksBySource(sources, task, runId) {
  if (!sources || !sources.length) {
    return '<p class="muted">暂无子任务数据，请点击「刷新」</p>';
  }
  const running = task && ['crawling', 'analyzing'].includes(task.status);
  let html = '';
  sources.forEach(function(src) {
    const sid = src.source_id;
    const q = src.queue || {};
    const k = src.keywords || {};
    let controls = '';
    if (running && task && task.id) {
      controls = '<div class="btn-group" style="margin:8px 0">'
        + '<button type="button" class="btn btn-orange btn-sm" onclick="pauseTaskById(' + task.id + ',' + jsAttrStr(sid) + ')">暂停 ' + sourceTag(sid) + '</button>'
        + '</div>';
    }
    html += '<div class="task-source-card source-subtask-block ' + (src.status === 'failed' ? 'is-failed' : (src.status === 'running' ? 'is-running' : (src.status === 'done' ? 'is-done' : ''))) + '" data-source-id="' + esc(sid) + '">'
      + '<div class="task-source-card-head">'
      + '<div class="task-source-card-title">' + sourceTag(sid) + ' ' + sourceSubtaskStatusTag(src.status)
      + (src.halt ? ' <span class="meta">(' + esc(src.halt === 'pause' ? '已请求暂停' : '已请求终止') + ')</span>' : '')
      + '</div></div>'
      + controls
      + '<div class="task-source-card-metrics source-summary-wrap">' + renderSourceQueueSummary(q)
      + (k.total ? ' · ' + renderSourceKeywordSummary(k) : '')
      + '</div>'
      + '<div class="task-source-card-timing source-timing-block">' + renderSourceTimingBlock(src) + '</div>';
    const subItems = src.subtask_items && src.subtask_items.length
      ? src.subtask_items
      : normalizeLegacyKeywordItems(src.keyword_items);
    if (subItems.length) {
      html += '<div class="source-subtask-items-wrap">' + renderSourceSubtaskItems(subItems, task, sid) + '</div>';
    }
    html += '</div>';
  });
  if (running && task && task.id) {
    let topBtns = '<div class="btn-group" style="margin-bottom:12px">'
      + '<button type="button" class="btn btn-red btn-sm" onclick="stopTaskById(' + task.id + ',\'all\')">终止任务</button>';
    if ((task.sources || []).length > 1) {
      topBtns += '<button type="button" class="btn btn-orange btn-sm" onclick="pauseTaskById(' + task.id + ',\'all\')">暂停全部源</button>';
    }
    topBtns += '</div>';
    html = topBtns + html;
  }
  return html;
}

function renderRunLogsSection(logs) {
  logs = logs || [];
  if (!logs.length) {
    return '<div class="run-detail-section"><h4>执行日志</h4><p class="muted">暂无日志</p></div>';
  }
  const lines = logs.slice().reverse().map(function(l) {
    const lvl = l.level || 'INFO';
    const worker = l.worker_instance_id
      ? ' <span class="meta">' + esc(l.worker_instance_id) + '</span>' : '';
    return '<div class="log-line"><span class="log-time">' + fmtTime(l.created_at) + '</span>'
      + ' <span class="log-level ' + esc(lvl) + '">[' + esc(lvl) + ']</span>'
      + worker
      + ' <span class="log-msg">' + esc(l.message || '') + '</span></div>';
  }).join('');
  return '<div class="run-detail-section"><h4>执行日志</h4>'
    + '<div class="logs scroll" style="max-height:280px;border:1px solid var(--border);border-radius:6px">' + lines + '</div></div>';
}

async function retryFailedKeywords(taskId, keywordRunIds) {
  if (!keywordRunIds || !keywordRunIds.length) return;
  if (!confirm('重跑 ' + keywordRunIds.length + ' 个失败的 keyword 子任务？')) return;
  let d;
  try {
    d = await api('/api/monitor/retry-keywords', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId, keyword_run_ids: keywordRunIds, analyze_mode: 'incremental' }),
    });
  } catch (e) {
    toastMsg(e.message || '重跑失败', true);
    return;
  }
  if (!d.ok) { toastMsg(d.msg || '重跑失败', true); return; }
  toastMsg('已启动 keyword 重跑');
  loadTasks();
}

function buildRunDetailHtml(run, task, keywords) {
  const totalMs = (run.crawl_duration_ms || 0) + (run.analyze_duration_ms || 0);
  let html = '<div class="run-detail-drawer">';
  html += '<div class="run-detail-overview">'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('status')) + '</span><span class="v">' + statusTag(run.status) + ' ' + runAnalyzeDeferredTag(run) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">执行模式</span><span class="v">' + (run.crawl_only ? '仅爬取' : '爬取+分析') + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('trigger')) + '</span><span class="v">' + esc(runTriggerLabel(run.trigger)) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('analyze_mode')) + '</span><span class="v">' + esc(runModeLabel(run.analyze_mode)) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">总耗时</span><span class="v">' + fmtDuration(totalMs) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('started_at')) + '</span><span class="v">' + fmtTime(run.started_at) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('finished_at')) + '</span><span class="v">' + fmtTime(run.finished_at) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('crawl_duration_ms')) + '</span><span class="v">' + fmtDuration(run.crawl_duration_ms) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">' + esc(runFieldLabel('analyze_duration_ms')) + '</span><span class="v">' + fmtDuration(run.analyze_duration_ms) + '</span></div>'
    + (run.triage_duration_ms != null ? '<div class="run-detail-kv"><span class="k">初筛耗时</span><span class="v">' + fmtDuration(run.triage_duration_ms) + '</span></div>' : '')
    + (run.investigation_crawl_duration_ms != null ? '<div class="run-detail-kv"><span class="k">勘察耗时</span><span class="v">' + fmtDuration(run.investigation_crawl_duration_ms) + '</span></div>' : '')
    + '</div>';
  if (run.error_message) {
    html += renderRunDetailError(run.error_message);
  }
  if (run.crawl_only && (run.stats || {}).analyze_deferred && task && task.id) {
    html += '<div class="run-detail-deferred-analyze">'
      + '<p class="muted">本次 Run 已跳过 AI 分析，共 '
      + ((run.stats || {}).pending_analyze_raw_count != null ? run.stats.pending_analyze_raw_count : '?')
      + ' 条 raw 待处理。</p>'
      + '<button type="button" class="btn btn-orange btn-sm" onclick="reanalyzeIncremental(' + task.id + ')">增量 AI</button>'
      + '</div>';
  }
  html += '<h4 class="run-detail-section">统计指标</h4>' + renderRunDetailStats(run.stats);
  html += '<h4 class="run-detail-section">分源耗时</h4>' + renderRunDetailTiming(run.timing_by_source);
  html += '<h4 class="run-detail-section">Token 用量</h4>' + renderRunDetailToken(run.token_usage);
  html += '<h4 class="run-detail-section">Keyword 子任务</h4>' + renderKeywordSubtasks(keywords || [], run, task);
  html += renderRunDetailGlossary();
  html += '</div>';
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
  let keywords = [];
  try {
    const kd = await api('/api/monitor/runs/' + runId + '/keywords');
    if (kd.ok) keywords = kd.keywords || [];
  } catch (e) { /* ignore */ }
  selectedRunId = runId;
  selectedRunTaskId = resolvedTaskId;
  renderTaskTable();
  const qPatch = { tab: 'tasks', run_id: runId, task_id: resolvedTaskId || null };
  if (App.getQuery('monitor_task_id')) qPatch.monitor_task_id = App.getQuery('monitor_task_id');
  if (App.getQuery('task_tab')) qPatch.task_tab = App.getQuery('task_tab');
  App.setQuery(qPatch, true);
  UiShell.drawer({
    title: 'Run #' + runId + (task && task.name ? ' · ' + task.name : ''),
    bodyHtml: buildRunDetailHtml(d.run, task, keywords),
    width: '720px',
    onClose: function() {
      selectedRunId = null;
      selectedRunTaskId = null;
      renderTaskTable();
      const closePatch = { run_id: null };
      if (!App.getQuery('monitor_task_id')) closePatch.task_id = null;
      App.setQuery(closePatch, true);
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
    const listMs = t.list_crawl_ms || t.crawl_ms || 0;
    return '<tr><td>' + sourceTag(sid) + '</td>'
      + '<td>' + fmtDuration(listMs) + '</td>'
      + '<td>' + fmtDuration(t.triage_ms || 0) + '</td>'
      + '<td>' + fmtDuration(t.investigation_crawl_ms || 0) + '</td>'
      + '<td>' + fmtDuration(t.intel_analyze_ms || t.analyze_ms || 0) + '</td>'
      + '<td>' + (t.raw_new || 0) + '</td>'
      + '<td>' + (t.raw_updated || 0) + '</td>'
      + '<td>' + (t.intel_written || 0) + '</td></tr>';
  }).join('');
  return '<table class="run-detail-table"><thead><tr>'
    + '<th>来源</th><th>列表爬取</th><th>初筛</th><th>详情勘察</th><th>情报分析</th>'
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

function renderRunHistoryStatHeaders() {
  return RUN_STATS_KEYS.map(function(key) {
    const m = runFieldMeta(key);
    const title = m.help ? ' title="' + esc(m.help) + '"' : '';
    return '<th' + title + '>' + esc(m.label) + '</th>';
  }).join('');
}

function renderRunHistoryStatCells(stats) {
  stats = stats || {};
  return RUN_STATS_KEYS.map(function(key) {
    return '<td class="num">' + (stats[key] != null ? stats[key] : 0) + '</td>';
  }).join('');
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
    + '<td>' + statusTag(r.status) + ' ' + runAnalyzeDeferredTag(r) + '</td>'
    + '<td>' + fmtDuration(total) + '</td>'
    + renderRunHistoryStatCells(st)
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
  return '<div class="run-history-scroll"><table class="run-summary-table"><thead><tr>'
    + '<th>Run</th><th>开始</th><th>触发</th><th>模式</th><th>状态</th><th>耗时</th>'
    + renderRunHistoryStatHeaders()
    + '</tr></thead><tbody>' + rows + '</tbody></table></div>' + footer;
}

let taskDetailState = {
  taskId: null,
  task: null,
  taskTab: 'overview',
  runs: [],
  runsTotal: 0,
  runsPage: 0,
  runsLoading: false,
  subtaskRunId: null,
};

function showTaskListView() {
  const list = document.getElementById('taskListView');
  const detail = document.getElementById('taskDetailView');
  if (list) list.style.display = '';
  if (detail) detail.style.display = 'none';
}

function showTaskDetailView() {
  const list = document.getElementById('taskListView');
  const detail = document.getElementById('taskDetailView');
  if (list) list.style.display = 'none';
  if (detail) detail.style.display = '';
}

function backToTaskList() {
  App.setQuery({ monitor_task_id: null, task_tab: null, run_id: null, task_id: null }, true);
  showTaskListView();
  loadTasks();
}

function crawlModeLabel(mode) {
  return mode === 'list_first' ? '列表优先' : 'Legacy';
}

function formatTaskScheduleSummary(task) {
  const sched = (task && task.schedule) || {};
  if (!sched.enabled) return '未启用';
  const bits = ['已启用'];
  if (task.next_run_at) bits.push('下次 ' + fmtTime(task.next_run_at));
  if (sched.cron) bits.push('cron ' + sched.cron);
  if (sched.timezone) bits.push(sched.timezone);
  return bits.join(' · ');
}

function renderTaskDetailHeader() {
  const t = taskDetailState.task;
  const title = document.getElementById('taskDetailTitle');
  const tags = document.getElementById('taskDetailTags');
  if (!t || !title) return;
  title.textContent = (t.name || '未命名任务') + ' #' + t.id;
  if (!tags) return;
  const bits = [statusTag(t.status)];
  (t.sources || []).forEach(function(s) { bits.push(sourceTag(s)); });
  bits.push('<span class="tag tag-medium">' + esc(crawlModeLabel(t.crawl_mode)) + '</span>');
  if (t.schedule && t.schedule.enabled) bits.push('<span class="tag tag-on">定时</span>');
  tags.innerHTML = bits.join('');
}

function renderTaskDetailActionBar() {
  const bar = document.getElementById('taskDetailActionBar');
  const t = taskDetailState.task;
  if (!bar || !t) return;
  const running = ['crawling', 'analyzing'].includes(t.status);
  const srcs = t.sources || [];
  let controlGroup = '';
  if (running && srcs.length > 1) {
    controlGroup = '<span class="task-action-group-label">运行</span>'
      + srcs.map(function(s) {
        return '<button type="button" class="btn btn-orange btn-sm" onclick="pauseTaskById(' + t.id + ',' + jsAttrStr(s) + ')">暂停' + esc(sourceLabel(s)) + '</button>';
      }).join(' ')
      + '<button type="button" class="btn btn-orange btn-sm" onclick="pauseTaskById(' + t.id + ',\'all\')">暂停全部</button>'
      + '<button type="button" class="btn btn-red btn-sm" onclick="stopTaskById(' + t.id + ',\'all\')">终止</button>';
  } else if (running) {
    controlGroup = ''
      + (t.can_pause ? '<button type="button" class="btn btn-orange btn-sm" onclick="pauseTaskById(' + t.id + ',\'all\')">暂停</button>' : '')
      + (t.can_stop ? '<button type="button" class="btn btn-red btn-sm" onclick="stopTaskById(' + t.id + ',\'all\')">终止</button>' : '');
  }
  const runGroup = ''
    + (t.can_resume ? '<button type="button" class="btn btn-primary btn-sm" onclick="resumeTaskById(' + t.id + ')" title="继续未完成子任务">继续 (' + (t.incomplete_subtasks || 0) + ')</button>' : '')
    + '<button type="button" class="btn btn-primary btn-sm" onclick="runTaskById(' + t.id + ')" '
    + (!t.can_run ? 'disabled' : '') + ' title="' + esc(taskRunTooltip(t)) + '">执行</button>';
  const manageGroup = ''
    + '<button type="button" class="btn btn-orange btn-sm" onclick="reanalyzeIncremental(' + t.id + ')" '
    + (!t.can_reanalyze ? 'disabled title="' + esc(t.reanalyze_block_reason || '不可增量 AI') + '"' : '') + '>增量 AI</button>'
    + '<button type="button" class="btn btn-orange btn-sm" onclick="reanalyzeFull(' + t.id + ')" '
    + (!t.can_reanalyze_full ? 'disabled title="' + esc(t.reanalyze_full_block_reason || t.reanalyze_block_reason || '不可全量 AI') + '"' : '') + '>全量 AI</button>'
    + '<button type="button" class="btn btn-gray btn-sm" onclick="editTask(' + t.id + ')" '
    + (running ? 'disabled' : '') + '>编辑</button>'
    + '<button type="button" class="btn btn-gray btn-sm admin-only-save" onclick="openPurgeModal({taskId:' + t.id + '})">清理</button>'
    + '<button type="button" class="btn btn-gray btn-sm" onclick="deleteTask(' + t.id + ')" '
    + (running ? 'disabled' : '') + '>删除</button>'
    + '<button type="button" class="btn btn-gray btn-sm" onclick="loadTaskDetail(true)">刷新</button>';
  const groups = [];
  if (controlGroup) {
    groups.push('<div class="task-action-group task-action-group-control">' + controlGroup + '</div>');
  }
  groups.push('<div class="task-action-group task-action-group-primary">' + runGroup + '</div>');
  groups.push('<div class="task-action-group task-action-group-muted">' + manageGroup + '</div>');
  bar.innerHTML = '<div class="task-action-groups">' + groups.join('') + '</div>';
}

function renderTaskDetailProgressHero(t) {
  const prog = t.progress || {};
  if (!prog.phase && !(prog.subtasks && prog.subtasks.total) && !prog.current_keyword) {
    return '<div class="task-detail-progress-hero"><span class="hero-label">执行进度</span><span class="hero-extra">暂无进行中的 Run</span></div>';
  }
  let extras = [];
  if (prog.subtasks && prog.subtasks.total) {
    extras.push('keyword ' + (prog.subtasks.done || 0) + '/' + prog.subtasks.total);
    if (prog.subtasks.failed) extras.push('失败 ' + prog.subtasks.failed);
    if (prog.subtasks.running) extras.push('运行 ' + prog.subtasks.running);
  }
  if (prog.current_keyword) extras.push('当前 ' + prog.current_keyword);
  const ad = prog.analyze_drain;
  if (ad && (ad.done || ad.pending_detail != null)) {
    const total = (ad.done || 0) + (ad.pending_detail || 0);
    extras.push('AI ' + (ad.done || 0) + '/' + total + (ad.last_trigger ? (' · ' + ad.last_trigger) : ''));
  }
  if (t.status === 'crawling' && ad && (ad.done || 0) > 0) {
    extras.push('爬取+分析中');
  }
  return '<div class="task-detail-progress-hero">'
    + '<span class="hero-label">执行进度</span>'
    + '<span class="hero-phase">' + esc(phaseLabel(prog.phase || 'pending')) + '</span>'
    + (extras.length ? '<span class="hero-extra">' + esc(extras.join(' · ')) + '</span>' : '')
    + '</div>';
}

function renderTaskDetailMetricCards(t) {
  const lr = t.last_run;
  let lastRunHtml = '<div class="task-detail-metric"><span class="metric-label">最近 Run</span>'
    + '<span class="metric-value muted">—</span></div>';
  if (lr) {
    const totalMs = (lr.crawl_duration_ms || 0) + (lr.analyze_duration_ms || 0);
    lastRunHtml = '<button type="button" class="task-detail-metric is-link" onclick="openRunDrawer(' + lr.id + ',' + t.id + ')">'
      + '<span class="metric-label">最近 Run</span>'
      + '<span class="metric-value">#' + lr.id + ' ' + (lr.status === 'done' ? '完成' : (lr.status === 'failed' ? '失败' : lr.status)) + '</span>'
      + '<span class="metric-meta">' + esc(runTriggerLabel(lr.trigger)) + ' · ' + fmtDuration(totalMs) + ' · ' + fmtTime(lr.finished_at || lr.started_at) + '</span>'
      + '</button>';
  }
  return '<div class="task-detail-metrics">'
    + '<div class="task-detail-metric"><span class="metric-label">源数据</span><span class="metric-value">' + (t.raw_count || 0) + '</span></div>'
    + '<div class="task-detail-metric"><span class="metric-label">情报</span><span class="metric-value">' + (t.intel_count || 0) + '</span></div>'
    + lastRunHtml
    + '</div>';
}

function renderTaskSourceProgressCard(src) {
  const q = src.queue || {};
  const k = src.keywords || {};
  const tw = src.timing || {};
  const aw = src.active_work;
  const statusClass = src.status === 'failed' ? 'is-failed'
    : (src.status === 'running' ? 'is-running' : (src.status === 'done' ? 'is-done' : ''));
  const subItems = src.subtask_items || [];
  const t = sumSourcePhaseTiming(subItems, tw);
  let metrics = [];
  if (q.total) metrics.push('<span>队列 <strong>' + (q.done || 0) + '/' + q.total + '</strong></span>');
  if (q.failed) metrics.push('<span>失败 <strong>' + q.failed + '</strong></span>');
  if (k.total) metrics.push('<span>关键词 <strong>' + (k.done || 0) + '/' + k.total + '</strong></span>');
  if (src.halt) {
    metrics.push('<span>' + esc(src.halt === 'pause' ? '已请求暂停' : '已请求终止') + '</span>');
  }
  let timingHtml = '';
  const crawlPhase = t.list_crawl_ms + t.triage_ms + t.investigation_ms;
  if (crawlPhase || t.intel_analyze_ms) {
    timingHtml = '<div class="task-source-card-timing">'
      + '<div class="timing-row"><span class="timing-label">累计</span>'
      + '<span>列表 ' + fmtDuration(t.list_crawl_ms) + '</span>'
      + '<span>初筛 ' + fmtDuration(t.triage_ms) + '</span>'
      + '<span>勘察 ' + fmtDuration(t.investigation_ms) + '</span>'
      + (t.intel_analyze_ms ? ('<span>情报分析 ' + fmtDuration(t.intel_analyze_ms) + '</span>') : '')
      + '</div>';
    if (aw && aw.phase) {
      timingHtml += '<div class="timing-row"><span class="timing-label">当前</span>'
        + '<span><strong>' + esc(phaseLabel(aw.phase)) + '</strong>'
        + ' · ' + fmtDuration(aw.elapsed_ms || 0)
        + (aw.label ? ' · ' + esc(aw.label) : '') + '</span></div>';
    }
    timingHtml += '</div>';
  }
  const phaseTable = renderSourcePhaseTable(src);
  return '<div class="task-source-card ' + statusClass + '" data-source-id="' + esc(src.source_id) + '">'
    + '<div class="task-source-card-head">'
    + '<div class="task-source-card-title">' + sourceTag(src.source_id) + sourceSubtaskStatusTag(src.status) + '</div>'
    + '</div>'
    + (metrics.length ? '<div class="task-source-card-metrics">' + metrics.join('') + '</div>' : '')
    + timingHtml
    + phaseTable
    + '</div>';
}

function renderTaskDetailOverview() {
  const box = document.getElementById('taskDetailOverviewBody');
  const t = taskDetailState.task;
  if (!box || !t) return;
  const bs = t.business_spec || {};
  const partnerLinks = (t.partner_ids || []).map(function(pid) {
    const name = partnerName(pid);
    return '<button type="button" class="btn btn-gray btn-sm" onclick="App.navigatePartnerDetail(' + pid + ')">' + esc(name) + '</button>';
  }).join(' ') || '<span class="muted">—</span>';

  box.innerHTML = ''
    + '<div class="task-detail-overview">'
    + '<div class="task-detail-panel">'
    + '<div class="task-detail-panel-head"><div><h3 class="task-detail-panel-title">执行状态</h3>'
    + '<div class="task-detail-panel-sub">各数据源当前 Run 的队列、阶段与耗时</div></div></div>'
    + '<div class="task-detail-progress-hero-wrap">' + renderTaskDetailProgressHero(t) + '</div>'
    + renderTaskDetailMetricCards(t)
    + renderTaskDetailSourceProgress(t)
    + (t.error_message ? ('<div style="margin-top:12px">' + renderRunDetailError(t.error_message) + '</div>') : '')
    + '</div>'
    + '<div class="task-detail-panel">'
    + '<div class="task-detail-panel-head"><div><h3 class="task-detail-panel-title">任务配置</h3>'
    + '<div class="task-detail-panel-sub">采集范围、模式与合作方</div></div></div>'
    + '<div class="task-detail-kv-grid">'
    + '<div class="run-detail-kv"><span class="k">任务 ID</span><span class="v">#' + t.id + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">采集页数</span><span class="v">' + (t.max_pages || '-') + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">黑猫模式</span><span class="v">' + esc(crawlModeLabel(t.crawl_mode)) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">Legacy 抓详情</span><span class="v">' + (t.fetch_detail ? '是' : '否') + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">忽略早于</span><span class="v">' + esc(bs.ignore_before || '—') + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">定时</span><span class="v">' + esc(formatTaskScheduleSummary(t)) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">创建</span><span class="v">' + fmtTime(t.created_at) + '</span></div>'
    + '<div class="run-detail-kv"><span class="k">更新</span><span class="v">' + fmtTime(t.updated_at) + '</span></div>'
    + '</div>'
    + '<div class="task-detail-config-block">'
    + '<div class="task-detail-config-row"><span class="config-row-label">来源</span>'
    + ((t.sources || []).map(function(s) { return sourceTag(s); }).join(' ') || '<span class="muted">—</span>') + '</div>'
    + '<div class="task-detail-config-row"><span class="config-row-label">合作方</span>'
    + '<div class="task-detail-partners">' + partnerLinks + '</div></div>'
    + '</div>'
    + '</div>'
    + '</div>';
}

function showTaskDetailPane(tab) {
  taskDetailState.taskTab = tab;
  document.querySelectorAll('.task-subtabs .tab').forEach(function(el) {
    el.classList.toggle('active', el.getAttribute('data-task-tab') === tab);
  });
  const panes = {
    overview: 'taskOverviewPane',
    runs: 'taskRunsPane',
    subtasks: 'taskSubtasksPane',
    raw: 'taskRawPane',
    intel: 'taskIntelPane',
  };
  Object.keys(panes).forEach(function(key) {
    const el = document.getElementById(panes[key]);
    if (el) el.style.display = key === tab ? '' : 'none';
  });
}

function switchTaskSubTab(tab, linkEl) {
  showTaskDetailPane(tab);
  App.setQuery({ task_tab: tab }, true);
  if (tab === 'runs') loadTaskDetailRuns(true);
  else if (tab === 'subtasks') loadTaskDetailSubtasks(true);
  else if (tab === 'raw') loadTaskDetailRaw();
  else if (tab === 'intel') loadTaskDetailIntel();
  else renderTaskDetailOverview();
}

async function loadTaskDetailRuns(reset) {
  const taskId = taskDetailState.taskId;
  const box = document.getElementById('taskDetailRunsBody');
  if (!taskId || !box) return;
  if (reset) {
    taskDetailState.runs = [];
    taskDetailState.runsPage = 0;
    taskDetailState.runsTotal = 0;
  }
  if (taskDetailState.runsLoading) return;
  taskDetailState.runsLoading = true;
  box.innerHTML = '<p class="meta">加载中…</p>';
  const page = reset ? 1 : taskDetailState.runsPage + 1;
  try {
    const d = await api('/api/monitor/tasks/' + taskId + '/runs?page=' + page + '&limit=' + RUN_HISTORY_LIMIT);
    if (!d.ok) throw new Error(d.msg || '加载失败');
    taskDetailState.runsPage = page;
    taskDetailState.runsTotal = d.total || 0;
    const newRuns = d.runs || [];
    taskDetailState.runs = reset ? newRuns : taskDetailState.runs.concat(newRuns);
    if (!taskDetailState.runs.length) {
      box.innerHTML = '<p class="muted">暂无执行记录</p>';
      return;
    }
    const rows = taskDetailState.runs.map(function(r) {
      return renderRunSummaryRow(r, taskId);
    }).join('');
    const hasMore = taskDetailState.runs.length < taskDetailState.runsTotal;
    const footer = hasMore
      ? '<div class="run-history-footer"><span class="meta">已加载 ' + taskDetailState.runs.length + ' / ' + taskDetailState.runsTotal + '</span>'
        + '<button type="button" class="btn btn-gray btn-sm" onclick="loadTaskDetailRuns(false)">加载更多</button></div>'
      : '<div class="run-history-footer"><span class="meta">共 ' + taskDetailState.runsTotal + ' 条</span></div>';
    box.innerHTML = '<div class="run-history-scroll"><table class="run-summary-table"><thead><tr>'
      + '<th>Run</th><th>开始</th><th>触发</th><th>模式</th><th>状态</th><th>耗时</th>'
      + renderRunHistoryStatHeaders()
      + '</tr></thead><tbody>' + rows + '</tbody></table></div>' + footer;
  } catch (e) {
    box.innerHTML = '<p class="msg-err">' + esc(e.message) + '</p>';
  } finally {
    taskDetailState.runsLoading = false;
  }
}

async function loadTaskDetailSubtaskRunOptions() {
  const sel = document.getElementById('taskDetailSubtaskRun');
  if (!sel || !taskDetailState.taskId) return false;
  const taskId = taskDetailState.taskId;
  try {
    const d = await api('/api/monitor/tasks/' + taskId + '/runs?page=1&limit=' + SUBTASK_RUN_LIMIT);
    if (d.ok && d.runs) {
      taskDetailState.runs = d.runs;
      taskDetailState.runsTotal = d.total || d.runs.length;
      taskDetailState.runsPage = 1;
    }
  } catch (e) {
    if (!taskDetailState.runs.length) await loadTaskDetailRuns(true);
  }
  const t = taskDetailState.task;
  const extraRunIds = [];
  if (t) {
    if (t.progress && t.progress.run_id) extraRunIds.push(parseInt(t.progress.run_id, 10));
    if (t.last_run_id) extraRunIds.push(parseInt(t.last_run_id, 10));
    if (t.resume_run_id) extraRunIds.push(parseInt(t.resume_run_id, 10));
  }
  const existing = new Set((taskDetailState.runs || []).map(function(r) { return r.id; }));
  for (let i = 0; i < extraRunIds.length; i++) {
    const rid = extraRunIds[i];
    if (!rid || existing.has(rid)) continue;
    try {
      const rd = await api('/api/monitor/runs/' + rid);
      if (rd.ok && rd.run) {
        taskDetailState.runs.unshift(rd.run);
        existing.add(rid);
      }
    } catch (e) { /* ignore */ }
  }
  taskDetailState.runs.sort(function(a, b) { return b.id - a.id; });
  const runs = taskDetailState.runs || [];
  sel.innerHTML = runs.map(function(r) {
    return '<option value="' + r.id + '">Run #' + r.id + ' · ' + esc(r.status || '') + ' · ' + fmtTime(r.started_at) + '</option>';
  }).join('');
  const preferred = taskDetailState.subtaskRunId
    || (t && t.progress && t.progress.run_id)
    || (t && t.last_run_id)
    || (runs[0] && runs[0].id);
  if (preferred && runs.some(function(r) { return r.id === parseInt(preferred, 10); })) {
    sel.value = String(preferred);
    taskDetailState.subtaskRunId = parseInt(preferred, 10);
  } else if (runs[0]) {
    sel.value = String(runs[0].id);
    taskDetailState.subtaskRunId = runs[0].id;
  }
  return !!runs.length;
}

function onTaskDetailSubtaskRunChange() {
  const sel = document.getElementById('taskDetailSubtaskRun');
  const box = document.getElementById('taskDetailSubtasksBody');
  if (!sel || !sel.value) return;
  taskDetailState.subtaskRunId = parseInt(sel.value, 10);
  if (box) {
    box.innerHTML = '<p class="meta">已选择 Run #' + esc(sel.value) + '，点击「刷新」加载子任务详情</p>';
  }
}

async function loadTaskDetailSubtasks(resetToLatest) {
  const box = document.getElementById('taskDetailSubtasksBody');
  const sel = document.getElementById('taskDetailSubtaskRun');
  if (!box || !taskDetailState.taskId) return;
  if (resetToLatest) taskDetailState.subtaskRunId = null;
  box.innerHTML = '<p class="meta">加载中…</p>';
  const hasRuns = await loadTaskDetailSubtaskRunOptions();
  const runId = sel && sel.value ? parseInt(sel.value, 10) : null;
  if (!hasRuns || !runId) {
    box.innerHTML = '<p class="muted">暂无执行记录</p>';
    return;
  }
  taskDetailState.subtaskRunId = runId;
  box.innerHTML = '<p class="meta">加载中…</p>';
  try {
    const [kd, rd] = await Promise.all([
      api('/api/monitor/runs/' + runId + '/subtasks'),
      api('/api/monitor/runs/' + runId + '?log_limit=200'),
    ]);
    const sources = (kd.ok && kd.sources) ? kd.sources : [];
    const logs = (rd.ok && rd.logs) ? rd.logs : [];
    box.innerHTML = renderRunSubtasksBySource(sources, taskDetailState.task, runId)
      + renderRunLogsSection(logs);
  } catch (e) {
    box.innerHTML = '<p class="msg-err">' + esc(e.message) + '</p>';
  }
}

function taskDetailRawRowSignature(r) {
  const summary = (r.title_summary || r.keyword || '').slice(0, 60);
  return [
    r.id, r.partner_id, r.source, r.keyword || '', summary,
    r.created_at || '', r.analyze_status || '',
  ].join('|');
}

function buildTaskDetailRawRowHtml(r) {
  const summary = (r.title_summary || r.keyword || '').slice(0, 60);
  const taskId = taskDetailState.taskId;
  return '<tr class="clickable-row" data-raw-id="' + r.id + '" onclick="App.setQuery({tab:\'raw\',raw_id:' + r.id + ',task_id:' + taskId + '});App.switchAppTab(\'raw\')">'
    + '<td data-field="id">' + r.id + '</td>'
    + '<td data-field="partner">' + esc(partnerName(r.partner_id)) + '</td>'
    + '<td data-field="source">' + sourceTag(r.source) + '</td>'
    + '<td class="truncate" data-field="keyword">' + esc(r.keyword || '-') + '</td>'
    + '<td class="truncate" data-field="summary" title="' + esc(summary) + '">' + esc(summary) + '</td>'
    + '<td data-field="created">' + fmtTime(r.created_at) + '</td>'
    + '<td data-field="analyze">' + esc(r.analyze_status || '-') + '</td></tr>';
}

function patchTaskDetailRawRow(row, r) {
  const summary = (r.title_summary || r.keyword || '').slice(0, 60);
  const setField = function(field, html) {
    const el = row.querySelector('[data-field="' + field + '"]');
    if (el && el.innerHTML !== html) el.innerHTML = html;
  };
  setField('id', String(r.id));
  setField('partner', esc(partnerName(r.partner_id)));
  setField('source', sourceTag(r.source));
  setField('keyword', esc(r.keyword || '-'));
  setField('summary', esc(summary));
  const sumEl = row.querySelector('[data-field="summary"]');
  if (sumEl) sumEl.setAttribute('title', summary);
  setField('created', fmtTime(r.created_at));
  setField('analyze', esc(r.analyze_status || '-'));
}

function taskDetailIntelRowSignature(r) {
  return [
    r.id, r.partner_name || '', r.source || '', r.relevance || '',
    r.sentiment_label || '', r.sentiment_score != null ? r.sentiment_score : '',
    (r.summary || r.title || '').slice(0, 60), r.captured_at || '',
  ].join('|');
}

function buildTaskDetailIntelRowHtml(r) {
  const taskId = taskDetailState.taskId;
  return '<tr class="clickable-row" data-intel-id="' + r.id + '" onclick="App.setQuery({tab:\'intel\',intel_id:' + r.id + ',task_id:' + taskId + '});App.switchAppTab(\'intel\')">'
    + '<td data-field="partner">' + esc(r.partner_name || '-') + '</td>'
    + '<td data-field="source">' + sourceTag(r.source) + '</td>'
    + '<td data-field="relevance">' + relTag(r.relevance) + '</td>'
    + '<td data-field="sentiment">' + sentimentTag(r.sentiment_label, r.sentiment_score) + '</td>'
    + '<td class="truncate" data-field="summary">' + esc((r.summary || r.title || '').slice(0, 60)) + '</td>'
    + '<td data-field="captured">' + fmtTime(r.captured_at) + '</td>'
    + '<td class="actions" data-field="actions" onclick="event.stopPropagation()">'
    + '<button type="button" class="btn btn-gray btn-sm" onclick="App.setQuery({tab:\'intel\',intel_id:' + r.id + '});App.switchAppTab(\'intel\')">详情</button>'
    + '</td></tr>';
}

function patchTaskDetailIntelRow(row, r) {
  const setField = function(field, html) {
    const el = row.querySelector('[data-field="' + field + '"]');
    if (el && el.innerHTML !== html) el.innerHTML = html;
  };
  setField('partner', esc(r.partner_name || '-'));
  setField('source', sourceTag(r.source));
  setField('relevance', relTag(r.relevance));
  setField('sentiment', sentimentTag(r.sentiment_label, r.sentiment_score));
  setField('summary', esc((r.summary || r.title || '').slice(0, 60)));
  setField('captured', fmtTime(r.captured_at));
}

function syncTaskDetailTableBody(body, rows, opts) {
  const scrollEl = body.closest('.table-wrap');
  const scrollTop = scrollEl ? scrollEl.scrollTop : 0;
  const idKey = opts.idKey;
  const sigStore = opts.sigStore;
  const emptyHtml = opts.emptyHtml;

  if (!rows.length) {
    if (!body.querySelector('tr[' + idKey + ']')) {
      if (body.innerHTML !== emptyHtml) body.innerHTML = emptyHtml;
    } else {
      body.innerHTML = emptyHtml;
      Object.keys(sigStore).forEach(function(k) { delete sigStore[k]; });
    }
    return;
  }

  if (body.querySelector('.empty') && !body.querySelector('tr[' + idKey + ']')) {
    body.innerHTML = '';
  }

  const seen = new Set();
  let prev = null;
  let prependHeight = 0;

  rows.forEach(function(r) {
    const id = String(opts.getId(r));
    seen.add(id);
    const sig = opts.rowSig(r);
    let row = body.querySelector('tr[' + idKey + '="' + id + '"]');

    if (!row) {
      const tmp = document.createElement('tbody');
      tmp.innerHTML = opts.buildRow(r);
      row = tmp.querySelector('tr');
      if (prev) {
        prev.insertAdjacentElement('afterend', row);
      } else if (body.firstElementChild) {
        body.insertBefore(row, body.firstElementChild);
        prependHeight += row.offsetHeight || 0;
      } else {
        body.appendChild(row);
      }
      sigStore[id] = sig;
    } else {
      if (sigStore[id] !== sig) {
        opts.patchRow(row, r);
        sigStore[id] = sig;
      }
      if (prev && row.previousElementSibling !== prev) {
        prev.insertAdjacentElement('afterend', row);
      }
    }
    prev = row;
  });

  body.querySelectorAll('tr[' + idKey + ']').forEach(function(row) {
    const id = row.getAttribute(idKey);
    if (!seen.has(id)) {
      row.remove();
      delete sigStore[id];
    }
  });

  if (scrollEl) scrollEl.scrollTop = scrollTop + prependHeight;
}

function syncTaskDetailRawTable(rows, total) {
  const body = document.getElementById('taskDetailRawBody');
  const countEl = document.getElementById('taskDetailRawCount');
  if (!body) return;
  const countText = '(共 ' + (total || rows.length) + ' 条)';
  if (countEl && countEl.textContent !== countText) countEl.textContent = countText;
  syncTaskDetailTableBody(body, rows, {
    idKey: 'data-raw-id',
    getId: function(r) { return r.id; },
    rowSig: taskDetailRawRowSignature,
    sigStore: taskDetailRawRowSigs,
    buildRow: buildTaskDetailRawRowHtml,
    patchRow: patchTaskDetailRawRow,
    emptyHtml: '<tr><td colspan="7" class="empty">暂无源数据</td></tr>',
  });
}

function syncTaskDetailIntelTable(rows, total) {
  const body = document.getElementById('taskDetailIntelBody');
  const countEl = document.getElementById('taskDetailIntelCount');
  if (!body) return;
  const countText = '(中及以上 ' + (total || rows.length) + ' 条)';
  if (countEl && countEl.textContent !== countText) countEl.textContent = countText;
  syncTaskDetailTableBody(body, rows, {
    idKey: 'data-intel-id',
    getId: function(r) { return r.id; },
    rowSig: taskDetailIntelRowSignature,
    sigStore: taskDetailIntelRowSigs,
    buildRow: buildTaskDetailIntelRowHtml,
    patchRow: patchTaskDetailIntelRow,
    emptyHtml: '<tr><td colspan="7" class="empty">暂无情报</td></tr>',
  });
}

async function refreshTaskDetailRawOnly() {
  if (!taskDetailState.taskId) return;
  const body = document.getElementById('taskDetailRawBody');
  if (!body) return;
  try {
    const p = new URLSearchParams({ task_id: String(taskDetailState.taskId), page_size: '100' });
    const d = await api('/api/raw/records?' + p.toString());
    syncTaskDetailRawTable(d.records || [], d.total);
  } catch (e) { /* ignore background refresh errors */ }
}

async function refreshTaskDetailIntelOnly() {
  if (!taskDetailState.taskId) return;
  const body = document.getElementById('taskDetailIntelBody');
  if (!body) return;
  try {
    const p = new URLSearchParams({
      task_id: String(taskDetailState.taskId),
      relevance_min: 'medium',
      page_size: '100',
    });
    const d = await api('/api/intel/records?' + p.toString());
    syncTaskDetailIntelTable(d.records || [], d.total);
  } catch (e) { /* ignore background refresh errors */ }
}

async function loadTaskDetailRaw(refreshOnly) {
  const body = document.getElementById('taskDetailRawBody');
  if (!body || !taskDetailState.taskId) return;
  const hasRows = !!body.querySelector('tr[data-raw-id]');
  if (!refreshOnly || !hasRows) {
    body.innerHTML = '<tr><td colspan="7" class="empty">加载中…</td></tr>';
  }
  try {
    const p = new URLSearchParams({ task_id: String(taskDetailState.taskId), page_size: '100' });
    const d = await api('/api/raw/records?' + p.toString());
    if (refreshOnly && hasRows) {
      syncTaskDetailRawTable(d.records || [], d.total);
    } else {
      taskDetailRawRowSigs = {};
      syncTaskDetailRawTable(d.records || [], d.total);
    }
  } catch (e) {
    if (!refreshOnly || !hasRows) {
      body.innerHTML = '<tr><td colspan="7" class="msg-err">' + esc(e.message) + '</td></tr>';
    }
  }
}

async function loadTaskDetailIntel(refreshOnly) {
  const body = document.getElementById('taskDetailIntelBody');
  if (!body || !taskDetailState.taskId) return;
  const hasRows = !!body.querySelector('tr[data-intel-id]');
  if (!refreshOnly || !hasRows) {
    body.innerHTML = '<tr><td colspan="7" class="empty">加载中…</td></tr>';
  }
  try {
    const p = new URLSearchParams({
      task_id: String(taskDetailState.taskId),
      relevance_min: 'medium',
      page_size: '100',
    });
    const d = await api('/api/intel/records?' + p.toString());
    if (refreshOnly && hasRows) {
      syncTaskDetailIntelTable(d.records || [], d.total);
    } else {
      taskDetailIntelRowSigs = {};
      syncTaskDetailIntelTable(d.records || [], d.total);
    }
  } catch (e) {
    if (!refreshOnly || !hasRows) {
      body.innerHTML = '<tr><td colspan="7" class="msg-err">' + esc(e.message) + '</td></tr>';
    }
  }
}

async function loadTaskDetail(refreshOnly) {
  const taskId = taskDetailState.taskId;
  if (!taskId) return;
  try {
    const d = await api('/api/monitor/tasks/' + taskId);
    if (!d.ok || !d.task) throw new Error(d.msg || '任务不存在');
    taskDetailState.task = d.task;
    const idx = tasks.findIndex(function(x) { return x.id === taskId; });
    if (idx >= 0) tasks[idx] = d.task;
    else tasks.push(d.task);
    renderTaskDetailHeader();
    renderTaskDetailActionBar();
    if (taskDetailState.taskTab === 'overview') {
      if (refreshOnly) patchTaskDetailOverviewProgress(d.task);
      else renderTaskDetailOverview();
    }
    else if (taskDetailState.taskTab === 'runs') {
      if (!refreshOnly) await loadTaskDetailRuns(true);
    }
    else if (taskDetailState.taskTab === 'subtasks') {
      if (!refreshOnly) await loadTaskDetailSubtasks(false);
    }
    else if (taskDetailState.taskTab === 'raw') await loadTaskDetailRaw(!!refreshOnly);
    else if (taskDetailState.taskTab === 'intel') await loadTaskDetailIntel(!!refreshOnly);
  } catch (e) {
    toastMsg(e.message || '加载任务详情失败', true);
    if (!refreshOnly) backToTaskList();
  }
}

async function openTaskDetail(taskId, taskTab) {
  if (!partners.length) await loadPartners();
  if (!sources.length) await loadSources();
  showTaskDetailView();
  taskDetailState = {
    taskId: taskId,
    task: null,
    taskTab: taskTab || App.getQuery('task_tab') || 'overview',
    runs: [],
    runsTotal: 0,
    runsPage: 0,
    runsLoading: false,
    subtaskRunId: null,
  };
  taskDetailRawRowSigs = {};
  taskDetailIntelRowSigs = {};
  App.setQuery({ tab: 'tasks', monitor_task_id: taskId, task_tab: taskDetailState.taskTab, run_id: null }, true);
  showTaskDetailPane(taskDetailState.taskTab);
  await loadTaskDetail(false);
}

function refreshTaskDetailIfOpen(taskId) {
  if (taskDetailState.taskId !== taskId || !document.getElementById('taskDetailView') || !taskDetailState.task) return;
  if (['subtasks', 'overview', 'raw', 'intel'].includes(taskDetailState.taskTab)) {
    refreshTaskDetailHeaderOnly(taskId);
    return;
  }
  loadTaskDetail(true);
}

async function refreshTaskDetailHeaderOnly(taskId) {
  if (taskDetailState.taskId !== taskId || !document.getElementById('taskDetailView')) return;
  try {
    const d = await api('/api/monitor/tasks/' + taskId);
    if (!d.ok || !d.task) return;
    taskDetailState.task = d.task;
    const idx = tasks.findIndex(function(x) { return x.id === taskId; });
    if (idx >= 0) tasks[idx] = d.task;
    else tasks.push(d.task);
    renderTaskDetailHeader();
    renderTaskDetailActionBar();
    if (taskDetailState.taskTab === 'subtasks') {
      patchSubtasksBodyFromProgress(d.task);
    } else if (taskDetailState.taskTab === 'overview') {
      patchTaskDetailOverviewProgress(d.task);
    } else if (taskDetailState.taskTab === 'raw') {
      await refreshTaskDetailRawOnly();
    } else if (taskDetailState.taskTab === 'intel') {
      await refreshTaskDetailIntelOnly();
    }
    updateTaskTable(false);
  } catch (e) { /* ignore */ }
}

function patchSubtasksBodyFromProgress(task) {
  const box = document.getElementById('taskDetailSubtasksBody');
  if (!box || !task) return;
  const runId = taskDetailState.subtaskRunId;
  const progRunId = task.progress && task.progress.run_id;
  if (!runId || !progRunId || parseInt(progRunId, 10) !== runId) return;
  const sources = (task.progress && task.progress.sources) || [];
  if (!sources.length || !box.querySelector('.source-subtask-block')) return;
  sources.forEach(function(src) {
    const block = box.querySelector('.source-subtask-block[data-source-id="' + src.source_id + '"]');
    if (!block) return;
    const statusWrap = block.querySelector('.source-status-wrap');
    if (statusWrap) {
      const html = sourceTag(src.source_id) + ' ' + sourceSubtaskStatusTag(src.status)
        + (src.halt ? ' <span class="meta">(' + esc(src.halt === 'pause' ? '已请求暂停' : '已请求终止') + ')</span>' : '');
      if (statusWrap.innerHTML !== html) statusWrap.innerHTML = html;
    }
    const summary = block.querySelector('.source-summary-wrap');
    if (summary) {
      const html = renderSourceQueueSummary(src.queue || {})
        + ((src.keywords && src.keywords.total) ? ' · ' + renderSourceKeywordSummary(src.keywords) : '');
      if (summary.innerHTML !== html) summary.innerHTML = html;
    }
    const timing = block.querySelector('.source-timing-block');
    if (timing) {
      const html = renderSourceTimingBlock(src);
      if (timing.innerHTML !== html) timing.innerHTML = html;
    }
    const itemsWrap = block.querySelector('.source-subtask-items-wrap');
    const subItems = src.subtask_items && src.subtask_items.length
      ? src.subtask_items
      : normalizeLegacyKeywordItems(src.keyword_items);
    if (itemsWrap && subItems.length) {
      const html = renderSourceSubtaskItems(subItems, task, src.source_id);
      if (itemsWrap.innerHTML !== html) itemsWrap.innerHTML = html;
    }
  });
}

function patchTaskDetailOverviewProgress(task) {
  const box = document.getElementById('taskDetailOverviewBody');
  if (!box || !task) return;
  const heroWrap = box.querySelector('.task-detail-progress-hero-wrap');
  if (heroWrap) {
    const heroHtml = renderTaskDetailProgressHero(task);
    if (heroWrap.innerHTML !== heroHtml) heroWrap.innerHTML = heroHtml;
  }
  const cards = box.querySelector('.task-detail-source-cards');
  if (cards) {
    const html = renderTaskDetailSourceProgressInner(task);
    if (cards.innerHTML !== html) cards.innerHTML = html;
  }
}

function renderTaskDetailSourceProgressInner(t) {
  const sources = (t.progress && t.progress.sources) || [];
  if (!sources.length) {
    return '<p class="muted" style="margin:0">暂无分源进度（任务未运行或 Run 已结束）</p>';
  }
  return sources.map(renderTaskSourceProgressCard).join('');
}

function renderTaskDetailSourceProgress(t) {
  const inner = renderTaskDetailSourceProgressInner(t);
  if (!inner) return '';
  return '<div class="task-detail-source-cards">' + inner + '</div>';
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
  updateTaskTable(true);
}

function updateTaskTable(forceRebuild) {
  const body = document.getElementById('taskTableBody');
  if (!body) return;
  const scrollEl = body.closest('.table-wrap');
  const scrollTop = scrollEl ? scrollEl.scrollTop : 0;

  if (!tasks.length) {
    if (!body.querySelector('.empty')) {
      body.innerHTML = '<tr><td colspan="9" class="empty">暂无监测任务，点击「创建任务」添加</td></tr>';
    }
    taskRowSigs = {};
    return;
  }

  if (forceRebuild) {
    taskRowSigs = {};
    body.innerHTML = '';
  } else if (body.querySelector('.empty')) {
    body.innerHTML = '';
  }

  const seen = new Set();
  tasks.forEach(function(t) {
    seen.add(t.id);
    const sig = taskRowSignature(t);
    let row = body.querySelector('tr.task-row[data-task-id="' + t.id + '"]');

    if (!row) {
      const tmp = document.createElement('tbody');
      tmp.innerHTML = buildTaskRowHtml(t);
      row = tmp.querySelector('tr.task-row');
      body.appendChild(row);
      if (expandedRunHistoryTaskId === t.id) {
        row.insertAdjacentHTML('afterend', '<tr class="run-history-row" onclick="event.stopPropagation()"><td colspan="9">'
          + renderRunHistoryContent(t.id) + '</td></tr>');
      }
    } else if (taskRowSigs[t.id] !== sig) {
      patchTaskRow(row, t);
    }
    taskRowSigs[t.id] = sig;
  });

  body.querySelectorAll('tr.task-row').forEach(function(row) {
    const id = parseInt(row.getAttribute('data-task-id'), 10);
    if (!seen.has(id)) {
      const hist = row.nextElementSibling;
      row.remove();
      if (hist && hist.classList.contains('run-history-row')) hist.remove();
      delete taskRowSigs[id];
    }
  });

  if (scrollEl) scrollEl.scrollTop = scrollTop;
}

function buildTaskPayload(existingTask) {
  const sched = window.SchedulePicker ? SchedulePicker.getScheduleFromDom() : { enabled: false };
  const { _preview, ...schedule } = sched;
  const prevBs = existingTask && existingTask.business_spec
    ? Object.assign({}, existingTask.business_spec)
    : {};
  const ignoreBefore = (document.getElementById('tIgnoreBefore') || {}).value || '';
  if (ignoreBefore) prevBs.ignore_before = ignoreBefore;
  else delete prevBs.ignore_before;
  return {
    name: document.getElementById('tName').value.trim(),
    partner_ids: getSelectedPartnerIds(),
    sources: getSelectedSourceIds(),
    max_pages: parseInt(document.getElementById('tPages').value, 10) || 2,
    crawl_mode: document.getElementById('tCrawlMode').value || 'list_first',
    fetch_detail: document.getElementById('tFetchDetail').checked,
    crawl_only: !!(document.getElementById('tCrawlOnly') && document.getElementById('tCrawlOnly').checked),
    schedule,
    business_spec: prevBs,
  };
}

function formatTaskSubtasks(t) {
  return renderTaskSourceProgress(t);
}

function formatLastRun(t) {
  const lr = t.last_run;
  if (!lr) return '<span class="muted">—</span>';
  const total = (lr.crawl_duration_ms || 0) + (lr.analyze_duration_ms || 0);
  const deferred = lr.crawl_only && (lr.stats || {}).analyze_deferred
    ? ' · <span class="tag tag-pending-analyze">待分析</span>' : '';
  const sched = t.schedule && t.schedule.enabled ? '<br><span class="meta">定时' + (t.next_run_at ? ' · 下次 ' + fmtTime(t.next_run_at) : '') + '</span>' : '';
  return fmtTime(lr.finished_at || lr.started_at) + deferred + '<br><span class="meta">' + (lr.trigger || '') + ' · ' + fmtDuration(total) + ' · ' + (lr.status || '') + '</span>' + sched;
}

let taskPollTimer = null;

function syncTaskPollTimer() {
  const busy = tasks.some(function(t) {
    return t.status === 'crawling' || t.status === 'analyzing';
  });
  if (busy) {
    if (!taskPollTimer) {
      taskPollTimer = setInterval(function() {
        loadTasks();
        if (taskDetailState.taskId) {
          if (['subtasks', 'overview', 'raw', 'intel'].includes(taskDetailState.taskTab)) {
            refreshTaskDetailHeaderOnly(taskDetailState.taskId);
          } else {
            refreshTaskDetailIfOpen(taskDetailState.taskId);
          }
        }
      }, 3000);
    }
  } else if (taskPollTimer) {
    clearInterval(taskPollTimer);
    taskPollTimer = null;
  }
}

async function loadTasks() {
  const d = await api('/api/monitor/tasks');
  tasks = d.tasks || [];
  refreshTaskSelect();
  refreshAiLogTaskSelect();
  refreshTaskFormPartnerChecksIfVisible();
  updateTaskTable(false);
  syncTaskPollTimer();
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
  document.getElementById('tCrawlMode').value = 'list_first';
  document.getElementById('tFetchDetail').checked = false;
  const crawlOnlyEl = document.getElementById('tCrawlOnly');
  if (crawlOnlyEl) crawlOnlyEl.checked = false;
  const ign = document.getElementById('tIgnoreBefore');
  if (ign) ign.value = '';
  renderPartnerChecks([]);
  renderSourceChecks();
  if (window.SchedulePicker) SchedulePicker.fillScheduleForm({ enabled: false });
}

function fillTaskForm(t) {
  document.getElementById('editingTaskId').value = t.id;
  document.getElementById('tName').value = t.name || '';
  document.getElementById('tPages').value = t.max_pages || 2;
  document.getElementById('tCrawlMode').value = t.crawl_mode || 'list_first';
  document.getElementById('tFetchDetail').checked = !!t.fetch_detail;
  const crawlOnlyEl = document.getElementById('tCrawlOnly');
  if (crawlOnlyEl) crawlOnlyEl.checked = !!t.crawl_only;
  const ign = document.getElementById('tIgnoreBefore');
  if (ign) {
    const bs = t.business_spec || {};
    ign.value = bs.ignore_before || '';
  }
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
  const existingTask = editId ? tasks.find(x => x.id === editId) : null;
  const payload = buildTaskPayload(existingTask);
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
    refreshTaskDetailIfOpen(editId);
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
    if (taskDetailState.taskId === id) backToTaskList();
    await loadTasks();
    if (lastTaskId === id) loadRecords();
    toastMsg('任务已删除');
  } catch (e) {
    toastMsg(e.message || '删除失败', true);
  }
}

async function runTaskById(task_id) {
  const t = tasks.find(function(x) { return x.id === task_id; });
  const crawl_only = t ? !!t.crawl_only : false;
  let d;
  try {
    d = await api('/api/monitor/run', {
      method: 'POST',
      body: JSON.stringify({ task_id, analyze_mode: 'incremental', crawl_only: crawl_only }),
    });
  } catch (e) {
    toastMsg(e.message || '启动失败', true);
    return;
  }
  if (!d.ok) { toastMsg(d.msg || '启动失败', true); return; }
  document.getElementById('taskStatus').textContent = crawl_only
    ? ('任务 #' + task_id + ' 仅爬取已启动…')
    : ('任务 #' + task_id + ' 增量执行已启动…');
  pollTask(task_id);
}

async function pauseTaskById(task_id, source) {
  const src = source || 'all';
  let d;
  try {
    d = await api('/api/monitor/tasks/' + task_id + '/pause', {
      method: 'POST',
      body: JSON.stringify({ source: src }),
    });
  } catch (e) {
    toastMsg(e.message || '暂停失败', true);
    return;
  }
  if (!d.ok) { toastMsg(d.msg || '暂停失败', true); return; }
  const label = src === 'all' ? '全部源' : src;
  toastMsg('已请求暂停任务 #' + task_id + '（' + label + '）');
  document.getElementById('taskStatus').textContent = '任务 #' + task_id + ' 暂停中（' + label + '）…';
  if (taskDetailState.taskId === task_id && taskDetailState.taskTab === 'subtasks') {
    loadTaskDetailSubtasks();
  }
  pollTask(task_id);
}

async function stopTaskById(task_id, source) {
  const src = source || 'all';
  const t = tasks.find(function(x) { return x.id === task_id; }) || taskDetailState.task;
  const name = t ? (t.name || '#' + task_id) : task_id;
  const ok = await UiShell.confirm(
    '确定彻底终止监测任务「' + name + '」？\n\n将停止全部 Worker、结束当前 Run，未完成子任务不会保留为「继续」。\n已完成的数据仍保留；之后可点「执行」开始新一轮。',
    '终止任务'
  );
  if (!ok) return;
  let d;
  try {
    d = await api('/api/monitor/tasks/' + task_id + '/stop', {
      method: 'POST',
      body: JSON.stringify({ source: src }),
    });
  } catch (e) {
    toastMsg(e.message || '终止失败', true);
    return;
  }
  if (!d.ok) { toastMsg(d.msg || '终止失败', true); return; }
  toastMsg('任务 #' + task_id + ' 已终止');
  document.getElementById('taskStatus').textContent = '任务 #' + task_id + ' 已终止';
  await loadTasks();
  if (taskDetailState.taskId === task_id) {
    refreshTaskDetailIfOpen(task_id);
    if (taskDetailState.taskTab === 'subtasks') loadTaskDetailSubtasks();
  }
  pollTask(task_id);
}

async function resumeTaskById(task_id) {
  const t = tasks.find(function(x) { return x.id === task_id; }) || taskDetailState.task;
  const n = t && t.incomplete_subtasks ? t.incomplete_subtasks : '?';
  const srcs = t && t.resume_sources && t.resume_sources.length
    ? t.resume_sources.join('、') : '未完成源';
  const ok = await UiShell.confirm(
    '继续任务 #' + task_id + '，将执行剩余 ' + n + ' 个子任务（' + srcs + '）。',
    '继续任务'
  );
  if (!ok) return;
  let d;
  try {
    d = await api('/api/monitor/tasks/' + task_id + '/resume', {
      method: 'POST',
      body: JSON.stringify({ analyze_mode: 'incremental' }),
    });
  } catch (e) {
    toastMsg(e.message || '继续失败', true);
    return;
  }
  if (!d.ok) { toastMsg(d.msg || '继续失败', true); return; }
  toastMsg('已继续任务 #' + task_id + '（' + (d.keyword_count || n) + ' 个子任务）');
  document.getElementById('taskStatus').textContent = '任务 #' + task_id + ' 继续执行中…';
  await loadTasks();
  if (taskDetailState.taskId === task_id) {
    taskDetailState.subtaskRunId = null;
    await loadTaskDetail(true);
    if (taskDetailState.taskTab === 'subtasks') await loadTaskDetailSubtasks();
  }
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

function onIntelFilterChange() {
  intelListPage = 1;
  lastTaskId = parseInt(document.getElementById('fTask').value, 10) || null;
  App.setQuery({
    tab: 'intel',
    intel_id: null,
    intel_page: 1,
    task_id: document.getElementById('fTask').value || null,
    partner_id: document.getElementById('fPartner').value || null,
    source: document.getElementById('fSource').value || null,
    relevance_min: document.getElementById('fRelevance').value || null,
    sentiment_label: document.getElementById('fSentiment').value || null,
    sentiment_score_min: document.getElementById('fSentimentMin').value || null,
    sentiment_score_max: document.getElementById('fSentimentMax').value || null,
  }, true);
  loadRecords();
}

function onTaskFilterChange() {
  onIntelFilterChange();
}

function formatTaskProgressSummary(t) {
  const prog = t.progress || {};
  const statusLabels = {
    crawling: '爬取中', analyzing: '分析中', stopped: '已终止',
    paused: '已暂停', done: '已完成', failed: '失败', queued: '排队中',
  };
  const parts = [statusLabels[t.status] || t.status || '—'];
  if (prog.phase && (t.status === 'crawling' || t.status === 'analyzing')) {
    parts.push(phaseLabel(prog.phase));
  }
  if (prog.subtasks && prog.subtasks.total) {
    let st = 'keyword ' + (prog.subtasks.done || 0) + '/' + prog.subtasks.total;
    if (prog.subtasks.running) st += ' · 运行 ' + prog.subtasks.running;
    if (prog.subtasks.failed) st += ' · 失败 ' + prog.subtasks.failed;
    parts.push(st);
  }
  const sources = prog.sources || [];
  if (sources.length && (t.status === 'crawling' || t.status === 'analyzing')) {
    const srcStatusCn = {
      running: '运行中', pending: '待执行', paused: '已暂停', stopped: '已终止',
      failed: '失败', done: '完成', idle: '空闲',
    };
    sources.forEach(function(s) {
      if (!s || s.status === 'done' || s.status === 'idle') return;
      const name = s.source_id === 'heimao' ? '黑猫' : (s.source_id === 'xhs' ? '小红书' : s.source_id);
      let bit = name + ' ' + (srcStatusCn[s.status] || s.status);
      const aw = s.active_work;
      if (aw && aw.phase) bit += ' · ' + phaseLabel(aw.phase) + ' ' + fmtDuration(aw.elapsed_ms || 0);
      parts.push(bit);
    });
  }
  if (t.error_message && (t.status === 'stopped' || t.status === 'failed' || t.status === 'paused')) {
    parts.push(String(t.error_message).slice(0, 60));
  }
  return parts.join(' · ');
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
    el.textContent = '任务 #' + id + '：' + formatTaskProgressSummary(t);
    await loadTasks();
    if (taskDetailState.taskId === id && ['subtasks', 'overview', 'raw', 'intel'].includes(taskDetailState.taskTab)) {
      await refreshTaskDetailHeaderOnly(id);
    } else {
      refreshTaskDetailIfOpen(id);
    }
    if (t.status === 'done' || t.status === 'failed' || t.status === 'paused' || t.status === 'stopped') {
      if (runHistoryState[id]) delete runHistoryState[id];
      if (expandedRunHistoryTaskId === id) await fetchRunHistoryPage(id, true);
      if (t.status === 'done') {
        if (taskDetailState.taskId === id) {
          refreshTaskDetailIfOpen(id);
        } else {
          viewTaskIntel(id);
        }
      }
      break;
    }
  }
}

async function loadRecords() {
  const params = intelFilterParams();
  params.set('page', String(intelListPage));
  params.set('page_size', String(intelListPageSize));
  let d;
  try {
    d = await api('/api/intel/records?' + params.toString());
  } catch (e) {
    document.getElementById('recordBody').innerHTML = '<tr><td colspan="10" class="msg-err">' + esc(e.message) + '</td></tr>';
    return;
  }
  const rows = d.records || [];
  const total = d.total != null ? d.total : rows.length;
  const page = d.page || intelListPage;
  const pageSize = d.page_size || intelListPageSize;
  intelListPage = page;
  intelListPageSize = clampListPageSize(pageSize);
  const applied = d.applied_filters || {};
  const sentimentFilter = document.getElementById('fSentiment') && document.getElementById('fSentiment').value;
  if (sentimentFilter && rows.length && rows.some(function(r) { return r.sentiment_label !== sentimentFilter; })) {
    toastMsg('情感筛选未在后端生效，请重启 crawler_web.py', true);
  }
  const countBits = [formatListCountMeta(total, page, pageSize)];
  if (applied.sentiment_label) countBits.push(sentimentLabelText(applied.sentiment_label));
  if (applied.sentiment_score_min != null) countBits.push('分数≥' + applied.sentiment_score_min);
  if (applied.sentiment_score_max != null) countBits.push('分数≤' + applied.sentiment_score_max);
  document.getElementById('recordCount').textContent = '(' + countBits.join(' · ') + ')';
  renderListPagination('intelListPagination', {
    page: page,
    pageSize: intelListPageSize,
    total: total,
    onPageChange: function(p) {
      intelListPage = p;
      App.setQuery({ intel_page: p, intel_page_size: intelListPageSize }, true);
      loadRecords();
    },
    onPageSizeChange: function(s) {
      intelListPageSize = s;
      intelListPage = 1;
      App.setQuery({ intel_page: 1, intel_page_size: s }, true);
      loadRecords();
    },
  });
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
      + intelMetaRow('相关度', relLabelText(r.relevance))
      + intelMetaRow('置信度', r.confidence != null ? Number(r.confidence).toFixed(2) : '')
      + intelMetaRow('情感', sentimentLabelText(r.sentiment_label)
        + (r.sentiment_score != null ? ' (' + Number(r.sentiment_score).toFixed(2) + ')' : ''))
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
  set('aiBatch', ai.batch_size != null ? ai.batch_size : 12);
  set('aiParallelBatches', ai.parallel_batches != null ? ai.parallel_batches : 5);
  set('aiBodyMax', ai.max_body_chars != null ? ai.max_body_chars : 2000);
  const lt = ai.list_triage || {};
  window._analysisListTriage = lt;
  set('aiTriageBatch', lt.batch_size != null ? lt.batch_size : 30);
  set('aiTriageBodyMax', lt.max_body_chars != null ? lt.max_body_chars : 400);
  const triageEn = document.getElementById('aiTriageEnabled');
  if (triageEn) triageEn.checked = lt.enabled !== false;
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
    batch_size: parseInt(document.getElementById('aiBatch').value, 10) || 12,
    parallel_batches: parseInt(document.getElementById('aiParallelBatches').value, 10) || 5,
    max_body_chars: parseInt(document.getElementById('aiBodyMax').value, 10) || 2000,
    max_retries: parseInt(document.getElementById('aiRetries').value, 10) || 2,
    retry_delay_sec: parseFloat(document.getElementById('aiRetryDelay').value) || 2,
    temperature: parseFloat(document.getElementById('aiTemp').value),
    timeout_sec: parseInt(document.getElementById('aiTimeout').value, 10) || 180,
    mock_without_key: document.getElementById('aiMock').checked,
    mock_default_relevance: document.getElementById('aiMockRel').value,
  };
  const ltBase = window._analysisListTriage || {};
  const triageEnEl = document.getElementById('aiTriageEnabled');
  payload.list_triage = Object.assign({}, ltBase, {
    batch_size: parseInt(document.getElementById('aiTriageBatch').value, 10) || 30,
    max_body_chars: parseInt(document.getElementById('aiTriageBodyMax').value, 10) || 400,
    enabled: triageEnEl ? triageEnEl.checked : ltBase.enabled !== false,
  });
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

window.pauseTaskById = pauseTaskById;
window.stopTaskById = stopTaskById;
window.resumeTaskById = resumeTaskById;
window.loadTaskDetailSubtasks = loadTaskDetailSubtasks;
