/* 数据源管理 Tab */
let sourcesDetail = [];

function fieldLabel(key) {
  if (window.FieldLabels && FieldLabels.renderFieldLabel) {
    return FieldLabels.renderFieldLabel(key);
  }
  return key;
}

function renderProfileFields(grid, keys, profile, prefix) {
  grid.innerHTML = keys.map(function(k) {
    const v = profile[k] != null ? profile[k] : '';
    const type = typeof v === 'boolean' ? 'checkbox' : (typeof v === 'number' ? 'number' : 'text');
    const dataKey = prefix ? prefix + '.' + k : k;
    if (type === 'checkbox') {
      return '<div class="field-row"><label class="toggle"><input type="checkbox" data-key="' + k + '" data-scope="' + (prefix || 'crawl') + '" ' +
        (v ? 'checked' : '') + '><span class="slider"></span></label>' +
        '<span class="toggle-label">' + fieldLabel(k) + '</span></div>';
    }
    return '<div class="field"><label>' + fieldLabel(k) + '</label><input type="' + type + '" data-key="' + k + '" data-scope="' + (prefix || 'crawl') + '" value="' + esc(String(v)) + '"></div>';
  }).join('');
}

async function loadSourcesPanel() {
  const notice = document.getElementById('sourcesNotice');
  const tabsBar = document.getElementById('sourceTabsBar');
  const box = document.getElementById('sourcesList');
  if (!box) return;
  try {
    if (window.FieldLabels && FieldLabels.load) await FieldLabels.load();
    const d = await api('/api/sources?detail=1');
    sourcesDetail = d.sources || [];
    if (notice) notice.textContent = d.notice || '';
    if (!sourcesDetail.length) {
      if (tabsBar) tabsBar.innerHTML = '';
      box.innerHTML = '<p class="muted">暂无数据源</p>';
      return;
    }
    let activeId = box.dataset.activeSource || sourcesDetail[0].source_id;
    if (!sourcesDetail.find(function(s) { return s.source_id === activeId; })) {
      activeId = sourcesDetail[0].source_id;
    }
    if (tabsBar) {
      tabsBar.innerHTML = sourcesDetail.map(function(s) {
        const cls = s.source_id === activeId ? ' source-tab active' : ' source-tab';
        return '<button type="button" class="' + cls.trim() + '" data-source-id="' + s.source_id + '" onclick="switchSourceTab(\'' + s.source_id + '\')">' + esc(s.label) + '</button>';
      }).join('');
    }
    box.dataset.activeSource = activeId;
    renderSourceCard(activeId);
    if (typeof App !== 'undefined') document.body.classList.toggle('readonly-mode', App.authEnabled && !App.isAdmin);
  } catch (e) {
    box.innerHTML = '<p class="msg-err">' + esc(e.message) + '</p>';
  }
}

function switchSourceTab(sourceId) {
  const box = document.getElementById('sourcesList');
  if (box) box.dataset.activeSource = sourceId;
  document.querySelectorAll('#sourceTabsBar .source-tab').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.sourceId === sourceId);
  });
  renderSourceCard(sourceId);
}

function renderSourceCard(sourceId) {
  const box = document.getElementById('sourcesList');
  const s = sourcesDetail.find(function(x) { return x.source_id === sourceId; });
  if (!box || !s) return;
  const dis = !s.registered ? ' opacity:.5' : '';
  box.innerHTML = '<div class="card source-card' + dis + '" data-id="' + s.source_id + '">' +
    '<div class="card-head"><h2>' + esc(s.label) + ' <span class="muted">(' + s.source_id + ')</span></h2>' +
    (s.registered ? '' : '<span class="tag tag-off">未注册</span>') + '</div>' +
    '<div class="field-row"><label class="toggle"><input type="checkbox" class="src-enabled" ' +
    (s.enabled ? 'checked' : '') + (s.registered ? '' : ' disabled') + '><span class="slider"></span></label>' +
    '<span class="toggle-label">启用</span></div>' +
    '<div class="field"><label>显示名称 (label)</label><input class="src-label" type="text" value="' + esc(s.label) + '"></div>' +
    '<h3 class="muted" style="font-size:13px;margin:12px 0 8px">采集参数</h3>' +
    '<div class="field-grid profile-fields-crawl"></div>' +
    '<h3 class="muted" style="font-size:13px;margin:16px 0 8px">清洗 / 归一化</h3>' +
    '<div class="field-grid profile-fields-normalize"></div>' +
    '<div class="btn-group admin-only-save"><button class="btn btn-primary btn-sm" onclick="saveSourceCard(\'' + s.source_id + '\')">保存</button></div>' +
    '</div>';
  if (s.registered) fillSourceProfileFields(s.source_id);
}

async function fillSourceProfileFields(sourceId) {
  const card = document.querySelector('.source-card[data-id="' + sourceId + '"]');
  if (!card) return;
  const d = await api('/api/sources/' + sourceId + '/profile');
  const crawl = d.profile || {};
  const norm = d.profile_normalize || {};
  const crawlKeys = d.profile_keys_crawl || d.profile_keys || [];
  const normKeys = d.profile_keys_normalize || [];
  renderProfileFields(card.querySelector('.profile-fields-crawl'), crawlKeys, crawl, 'crawl');
  renderProfileFields(card.querySelector('.profile-fields-normalize'), normKeys, norm, 'normalize');
}

async function saveSourceCard(sourceId) {
  const card = document.querySelector('.source-card[data-id="' + sourceId + '"]');
  if (!card) return;
  try {
    await api('/api/sources/' + sourceId, {
      method: 'PATCH',
      body: JSON.stringify({
        enabled: card.querySelector('.src-enabled').checked,
        label: card.querySelector('.src-label').value.trim(),
      }),
    });
    const profile = {};
    const normalize = {};
    card.querySelectorAll('[data-key]').forEach(function(el) {
      const k = el.dataset.key;
      const scope = el.dataset.scope || 'crawl';
      let val;
      if (el.type === 'checkbox') val = el.checked;
      else if (el.type === 'number') val = Number(el.value);
      else val = el.value;
      if (scope === 'normalize') normalize[k] = val;
      else profile[k] = val;
    });
    await api('/api/sources/' + sourceId + '/profile', {
      method: 'PATCH',
      body: JSON.stringify({profile: profile, normalize: normalize}),
    });
    showToast('已保存 ' + sourceId);
    if (typeof loadSources === 'function') loadSources();
  } catch (e) {
    showToast(e.message || '保存失败', true);
  }
}

async function saveMonitorDefaults() {
  const src = [];
  document.querySelectorAll('#monDefaultSources input:checked').forEach(function(el) {
    src.push(el.value);
  });
  try {
    await api('/api/monitor/defaults', {
      method: 'PATCH',
      body: JSON.stringify({
        default_sources: src,
        default_max_pages: parseInt(document.getElementById('monDefaultPages').value, 10) || 2,
        task_timeout_sec: parseInt(document.getElementById('monTaskTimeout').value, 10) || 7200,
      }),
    });
    showToast('监测默认配置已保存');
  } catch (e) {
    showToast(e.message || '保存失败', true);
  }
}

async function loadMonitorDefaultsForm() {
  try {
    if (!sourcesDetail.length) {
      const sd = await api('/api/sources?detail=1');
      sourcesDetail = sd.sources || [];
    }
    const d = await api('/api/monitor/defaults');
    const def = d.defaults || {};
    const box = document.getElementById('monDefaultSources');
    if (box && sourcesDetail.length) {
      const sel = def.default_sources || [];
      box.innerHTML = sourcesDetail.filter(function(s) { return s.registered; }).map(function(s) {
        return '<label><input type="checkbox" value="' + s.source_id + '" ' +
          (sel.indexOf(s.source_id) >= 0 ? 'checked' : '') + '> ' + esc(s.label) + '</label>';
      }).join('');
    }
    const pg = document.getElementById('monDefaultPages');
    const to = document.getElementById('monTaskTimeout');
    if (pg) pg.value = def.default_max_pages || 2;
    if (to) to.value = def.task_timeout_sec || 7200;
  } catch (e) {}
}
