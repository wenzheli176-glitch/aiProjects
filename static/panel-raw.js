/* 源数据 Tab */
function rawFilterParams() {
  const p = new URLSearchParams();
  const task = document.getElementById('frTask');
  const partner = document.getElementById('frPartner');
  const source = document.getElementById('frSource');
  if (task && task.value) p.set('task_id', task.value);
  if (partner && partner.value) p.set('partner_id', partner.value);
  if (source && source.value) p.set('source', source.value);
  return p;
}

function syncRawFiltersFromQuery() {
  const q = App.readQuery();
  const set = function(id, key) {
    const el = document.getElementById(id);
    if (el && q.get(key)) el.value = q.get(key);
  };
  set('frTask', 'task_id');
  set('frPartner', 'partner_id');
  set('frSource', 'source');
}

function onRawTabActivate() {
  syncRawFiltersFromQuery();
  const rawId = App.getQuery('raw_id');
  if (rawId) showRawDetail(parseInt(rawId, 10));
  else {
    showRawList();
    loadRawRecords();
  }
}

function showRawList() {
  const list = document.getElementById('rawListView');
  const detail = document.getElementById('rawDetailView');
  if (list) list.style.display = '';
  if (detail) detail.style.display = 'none';
}

async function showRawDetail(rawId) {
  const list = document.getElementById('rawListView');
  const detail = document.getElementById('rawDetailView');
  if (list) list.style.display = 'none';
  if (detail) detail.style.display = '';
  const box = document.getElementById('rawDetailContent');
  if (!box) return;
  box.innerHTML = '<p class="meta">加载中…</p>';
  try {
    const d = await api('/api/raw/records/' + rawId);
    if (!d.ok || !d.record) throw new Error(d.msg || '不存在');
    const r = d.record;
    const payload = r.payload || {};
    const intelLink = r.intel_id
      ? '<button class="btn btn-gray btn-sm" onclick="App.setQuery({tab:\'intel\',intel_id:' + r.intel_id + '});App.switchAppTab(\'intel\')">查看情报 #' + r.intel_id + '</button>'
      : '<span class="muted">暂无关联情报</span>';
    box.innerHTML =
      '<div class="detail-head"><button class="btn btn-gray btn-sm" onclick="backToRawList()">← 返回列表</button>'
      + '<h2>源数据 #' + r.id + '</h2></div>'
      + '<div class="detail-meta">'
      + metaRow('任务', '#' + r.task_id) + metaRow('合作方', '#' + (r.partner_id || ''))
      + metaRow('来源', r.source) + metaRow('关键词', r.keyword)
      + metaRow('采集时间', fmtTime(r.created_at)) + metaRow('更新时间', fmtTime(r.updated_at))
      + metaRow('dedup_key', r.dedup_key || '—') + metaRow('content_hash', r.content_hash || '—')
      + '</div><div class="detail-actions">' + intelLink + '</div>'
      + '<h3 class="detail-subtitle">Payload</h3>'
      + '<pre class="detail-pre">' + esc(JSON.stringify(payload, null, 2)) + '</pre>';
    App.setQuery({ raw_id: rawId }, true);
  } catch (e) {
    box.innerHTML = '<p class="msg-err">' + esc(e.message) + '</p>';
  }
}

function metaRow(k, v) {
  return '<div class="detail-kv"><span class="k">' + esc(k) + '</span><span class="v">' + esc(v) + '</span></div>';
}

function backToRawList() {
  const q = App.readQuery();
  q.delete('raw_id');
  history.replaceState(null, '', '/?' + q.toString());
  showRawList();
  loadRawRecords();
}

async function loadRawRecords() {
  const body = document.getElementById('rawTableBody');
  const countEl = document.getElementById('rawRecordCount');
  if (!body) return;
  const params = rawFilterParams();
  params.set('page', '1');
  params.set('page_size', '100');
  try {
    const d = await api('/api/raw/records?' + params.toString());
    const rows = d.records || [];
    if (countEl) countEl.textContent = '(共 ' + (d.total || rows.length) + ' 条)';
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="9" class="empty">暂无源数据</td></tr>';
      return;
    }
    body.innerHTML = rows.map(function(r) {
      return '<tr class="clickable-row" onclick="showRawDetail(' + r.id + ')">'
        + '<td>' + r.id + '</td><td>#' + r.task_id + '</td><td>#' + (r.partner_id || '') + '</td>'
        + '<td>' + sourceTag(r.source) + '</td><td>' + esc(r.keyword || '') + '</td>'
        + '<td class="truncate" title="' + esc(r.title_summary || '') + '">' + esc(r.title_summary || '—') + '</td>'
        + '<td>' + fmtTime(r.created_at) + '</td><td>' + fmtTime(r.updated_at) + '</td>'
        + '<td>' + (r.analyze_status === 'analyzed' ? '已分析' : '待分析') + '</td></tr>';
    }).join('');
  } catch (e) {
    body.innerHTML = '<tr><td colspan="9" class="msg-err">' + esc(e.message) + '</td></tr>';
  }
}

function exportRaw(fmt) {
  const params = rawFilterParams();
  params.set('format', fmt);
  window.open('/api/raw/export?' + params.toString(), '_blank');
}

function refreshRawFilters() {
  refreshTaskSelectForRaw();
  refreshPartnerSelectForRaw();
}

function refreshTaskSelectForRaw() {
  const sel = document.getElementById('frTask');
  if (!sel || typeof tasks === 'undefined') return;
  sel.innerHTML = '<option value="">全部任务</option>' + tasks.map(function(t) {
    return '<option value="' + t.id + '">#' + t.id + ' ' + esc(t.name || '') + '</option>';
  }).join('');
}

function refreshPartnerSelectForRaw() {
  const sel = document.getElementById('frPartner');
  if (!sel || typeof partners === 'undefined') return;
  sel.innerHTML = '<option value="">全部合作方</option>' + partners.map(function(p) {
    return '<option value="' + p.id + '">' + esc(p.name) + '</option>';
  }).join('');
}
