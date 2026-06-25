/* 数据源管理 Tab */
let sourcesDetail = [];

function fieldLabel(key) {
  if (window.FieldLabels && FieldLabels.renderFieldLabel) {
    return FieldLabels.renderFieldLabel(key);
  }
  return key;
}

function crawlModeOptionLabel(mode) {
  if (mode === 'list_first') return '列表优先（list_first）';
  if (mode === 'legacy') return 'Legacy（合作方×源串行）';
  return mode || '-';
}

function renderCrawlModeField(s) {
  const modes = s.allowed_crawl_modes || ['legacy', 'list_first'];
  const current = s.crawl_mode || modes[0] || 'legacy';
  const readOnly = modes.length <= 1;
  const opts = modes.map(function(m) {
    return '<option value="' + m + '"' + (m === current ? ' selected' : '') + '>' + crawlModeOptionLabel(m) + '</option>';
  }).join('');
  const hint = s.source_id === 'heimao'
    ? 'list_first：列表→初筛→详情勘察；legacy：routine 爬取（可配合任务「抓取详情」）'
    : (s.source_id === 'xhs' ? '小红书固定为 list_first（keyword 流水线）' : '');
  return '<div class="field source-crawl-mode-field">'
    + '<label>爬取策略 (crawl_mode)</label>'
    + '<select class="src-crawl-mode"' + (readOnly ? ' disabled' : '') + '>' + opts + '</select>'
    + (hint ? '<p class="muted" style="margin:4px 0 0;font-size:12px">' + hint + '</p>' : '')
    + '</div>';
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
  let html = '<div class="card source-card' + dis + '" data-id="' + s.source_id + '">' +
    '<div class="card-head"><h2>' + esc(s.label) + ' <span class="muted">(' + s.source_id + ')</span></h2>' +
    (s.registered ? '' : '<span class="tag tag-off">未注册</span>') + '</div>' +
    '<div class="field-row"><label class="toggle"><input type="checkbox" class="src-enabled" ' +
    (s.enabled ? 'checked' : '') + (s.registered ? '' : ' disabled') + '><span class="slider"></span></label>' +
    '<span class="toggle-label">启用</span></div>' +
    '<div class="field"><label>显示名称 (label)</label><input class="src-label" type="text" value="' + esc(s.label) + '"></div>' +
    renderCrawlModeField(s) +
    '<h3 class="muted" style="font-size:13px;margin:12px 0 8px">采集参数</h3>' +
    '<div class="field-grid profile-fields-crawl"></div>' +
    '<h3 class="muted" style="font-size:13px;margin:16px 0 8px">清洗 / 归一化</h3>' +
    '<div class="field-grid profile-fields-normalize"></div>' +
    '<div class="btn-group admin-only-save"><button class="btn btn-primary btn-sm" onclick="saveSourceCard(\'' + s.source_id + '\')">保存</button></div>';
  if (sourceId === 'xhs') {
    html += '<div id="xhsAccountsSection" class="xhs-accounts-section"><p class="meta">加载账号池…</p></div>';
  }
  html += '</div>';
  box.innerHTML = html;
  if (s.registered) fillSourceProfileFields(s.source_id);
  if (sourceId === 'xhs') loadXhsAccountsPanel();
}

let xhsLoginPollTimer = null;

function xhsAccountDiagBadge(acc) {
  const ld = acc.last_diagnose;
  if (!acc.cookies_file_exists) return '<span class="badge badge-red">无 Cookie</span>';
  if (!ld) return '<span class="badge">未诊断</span>';
  if (ld.diagnose_ok) return '<span class="badge badge-green">通过</span>';
  return '<span class="badge badge-red">失败</span>';
}

async function loadXhsAccountsPanel() {
  const sec = document.getElementById('xhsAccountsSection');
  if (!sec) return;
  try {
    const d = await api('/api/xhs/accounts');
    const list = d.accounts || [];
    let warn = '';
    if (d.below_min) {
      warn = '<p class="msg-warn">当前仅 ' + (d.enabled_count || 0) + ' 个可用账号，建议至少 '
        + (d.min_accounts || 2) + ' 个以启用 keyword 轮换。</p>';
    }
    const rows = list.map(function(acc) {
      const cool = acc.cooldown_until ? ('<span class="meta">' + esc(acc.cooldown_until).slice(0, 10) + '</span>') : '—';
      const uploadId = 'xhs-cookie-' + acc.id.replace(/[^a-z0-9_-]/gi, '_');
      return '<tr data-account-id="' + esc(acc.id) + '">'
        + '<td>' + esc(acc.label || acc.id) + '<div class="meta"><code>' + esc(acc.id) + '</code></div></td>'
        + '<td>' + (acc.enabled !== false ? '启用' : '<span class="muted">禁用</span>') + '</td>'
        + '<td>' + (acc.cookie_count || 0) + '</td>'
        + '<td>' + xhsAccountDiagBadge(acc) + '</td>'
        + '<td>' + cool + '</td>'
        + '<td class="xhs-acc-actions admin-only-save">'
        + '<button type="button" class="btn btn-primary btn-sm" onclick="startXhsAccountLogin(\'' + esc(acc.id) + '\')">登录获取</button> '
        + '<button type="button" class="btn btn-gray btn-sm" onclick="diagnoseXhsAccount(\'' + esc(acc.id) + '\')">诊断</button> '
        + '<button type="button" class="btn btn-gray btn-sm" onclick="toggleXhsAccountEnabled(\'' + esc(acc.id) + '\',' + (acc.enabled !== false ? 'false' : 'true') + ')">'
        + (acc.enabled !== false ? '禁用' : '启用') + '</button> '
        + '<input type="date" class="xhs-cooldown-input" data-account="' + esc(acc.id) + '" title="禁言冷却至" style="max-width:130px;font-size:11px" /> '
        + '<button type="button" class="btn btn-gray btn-sm" onclick="saveXhsCooldown(\'' + esc(acc.id) + '\')">设冷却</button>'
        + (acc.id !== 'acc-default' ? ' <button type="button" class="btn btn-gray btn-sm" onclick="deleteXhsAccount(\'' + esc(acc.id) + '\')">删除</button>' : '')
        + '<div style="margin-top:6px"><textarea id="' + uploadId + '" rows="2" placeholder="或粘贴 Cookie JSON" style="width:100%;font-size:11px"></textarea> '
        + '<button type="button" class="btn btn-blue btn-sm" onclick="uploadXhsAccountCookies(\'' + esc(acc.id) + '\',\'' + uploadId + '\')">保存 Cookie</button></div>'
        + '</td></tr>';
    }).join('');
    sec.innerHTML = '<h3 class="muted" style="font-size:13px;margin:16px 0 8px">登录账号池（每 keyword 轮换）</h3>'
      + warn
      + '<div class="btn-group admin-only-save" style="margin-bottom:8px">'
      + '<button type="button" class="btn btn-primary btn-sm" onclick="createXhsAccount()">添加账号</button>'
      + '<button type="button" class="btn btn-gray btn-sm" onclick="loadXhsAccountsPanel()">刷新</button></div>'
      + '<div id="xhsLoginStatus" class="meta" style="margin:8px 0"></div>'
      + '<table class="run-detail-table xhs-accounts-table"><thead><tr>'
      + '<th>账号</th><th>状态</th><th>Cookie</th><th>诊断</th><th>冷却至</th><th>操作</th>'
      + '</tr></thead><tbody>' + (rows || '<tr><td colspan="6" class="muted">暂无账号</td></tr>') + '</tbody></table>';
  } catch (e) {
    sec.innerHTML = '<p class="msg-err">' + esc(e.message) + '</p>';
  }
}

async function createXhsAccount() {
  const label = window.prompt('账号备注名称', '备用账号');
  if (label === null) return;
  try {
    await api('/api/xhs/accounts', { method: 'POST', body: JSON.stringify({ label: label }) });
    showToast('已添加账号');
    await loadXhsAccountsPanel();
  } catch (e) {
    showToast(e.message || '添加失败', true);
  }
}

async function diagnoseXhsAccount(id) {
  try {
    showToast('诊断中…');
    const d = await api('/api/xhs/accounts/' + id + '/diagnose', { method: 'POST', body: '{}' });
    const ok = d.result && d.result.diagnose_ok;
    showToast(ok ? '诊断通过' : '诊断失败', !ok);
    await loadXhsAccountsPanel();
  } catch (e) {
    showToast(e.message || '诊断失败', true);
  }
}

async function uploadXhsAccountCookies(id, textareaId) {
  const el = document.getElementById(textareaId);
  const cookies = el && el.value ? el.value.trim() : '';
  if (!cookies) return showToast('请粘贴 Cookie', true);
  try {
    await api('/api/xhs/accounts/' + id + '/cookies', {
      method: 'POST',
      body: JSON.stringify({ cookies: cookies, diagnose: true }),
    });
    if (el) el.value = '';
    showToast('Cookie 已保存');
    await loadXhsAccountsPanel();
  } catch (e) {
    showToast(e.message || '保存失败', true);
  }
}

async function toggleXhsAccountEnabled(id, enabled) {
  try {
    await api('/api/xhs/accounts/' + id, {
      method: 'PATCH',
      body: JSON.stringify({ enabled: enabled === true || enabled === 'true' }),
    });
    await loadXhsAccountsPanel();
  } catch (e) {
    showToast(e.message || '更新失败', true);
  }
}

async function saveXhsCooldown(id) {
  const inp = document.querySelector('.xhs-cooldown-input[data-account="' + id + '"]');
  const val = inp && inp.value ? inp.value : '';
  const cooldown_until = val ? (val + 'T23:59:59Z') : null;
  try {
    await api('/api/xhs/accounts/' + id, {
      method: 'PATCH',
      body: JSON.stringify({ cooldown_until: cooldown_until }),
    });
    showToast(val ? '已设置冷却' : '已清除冷却');
    await loadXhsAccountsPanel();
  } catch (e) {
    showToast(e.message || '失败', true);
  }
}

async function deleteXhsAccount(id) {
  if (!window.confirm('删除账号 ' + id + '？（不删 Cookie 文件）')) return;
  try {
    await api('/api/xhs/accounts/' + id, { method: 'DELETE' });
    showToast('已删除');
    await loadXhsAccountsPanel();
  } catch (e) {
    showToast(e.message || '删除失败', true);
  }
}

function stopXhsLoginPoll() {
  if (xhsLoginPollTimer) {
    clearInterval(xhsLoginPollTimer);
    xhsLoginPollTimer = null;
  }
}

async function startXhsAccountLogin(accountId) {
  stopXhsLoginPoll();
  const statusEl = document.getElementById('xhsLoginStatus');
  try {
    if (statusEl) statusEl.textContent = '正在打开登录 Chrome…';
    const d = await api('/api/xhs/accounts/' + accountId + '/login/start', { method: 'POST', body: '{}' });
    if (statusEl) statusEl.innerHTML = '请在弹出 Chrome 完成小红书登录 · 账号 <code>' + esc(accountId) + '</code> '
      + '<button type="button" class="btn btn-primary btn-sm" id="xhsLoginFinishBtn">完成并保存</button> '
      + '<button type="button" class="btn btn-gray btn-sm" onclick="cancelXhsAccountLogin(\'' + esc(accountId) + '\')">取消</button>';
    const finishBtn = document.getElementById('xhsLoginFinishBtn');
    if (finishBtn) {
      finishBtn.onclick = function() { finishXhsAccountLogin(accountId); };
    }
    xhsLoginPollTimer = setInterval(function() {
      pollXhsLoginStatus(accountId);
    }, 2000);
    pollXhsLoginStatus(accountId);
  } catch (e) {
    if (statusEl) statusEl.textContent = '';
    showToast(e.message || '无法启动登录', true);
  }
}

async function pollXhsLoginStatus(accountId) {
  const statusEl = document.getElementById('xhsLoginStatus');
  try {
    const d = await api('/api/xhs/accounts/' + accountId + '/login/status');
    if (d.status === 'logged_in' && statusEl) {
      statusEl.innerHTML = '已检测到登录 · 账号 <code>' + esc(accountId) + '</code> '
        + '<button type="button" class="btn btn-primary btn-sm" onclick="finishXhsAccountLogin(\'' + esc(accountId) + '\')">完成并保存</button>';
    } else if (d.status === 'timeout') {
      stopXhsLoginPoll();
      showToast('登录超时', true);
      await loadXhsAccountsPanel();
    }
  } catch (e) { /* ignore poll errors */ }
}

async function finishXhsAccountLogin(accountId) {
  stopXhsLoginPoll();
  try {
    const d = await api('/api/xhs/accounts/' + accountId + '/login/finish', { method: 'POST', body: '{}' });
    showToast(d.ok ? 'Cookie 已保存' : (d.msg || '保存失败'), !d.ok);
    await loadXhsAccountsPanel();
  } catch (e) {
    showToast(e.message || '保存失败', true);
  }
}

async function cancelXhsAccountLogin(accountId) {
  stopXhsLoginPoll();
  try {
    await api('/api/xhs/accounts/' + accountId + '/login/cancel', { method: 'POST', body: '{}' });
  } catch (e) { /* ignore */ }
  const statusEl = document.getElementById('xhsLoginStatus');
  if (statusEl) statusEl.textContent = '';
  showToast('已取消登录');
}

window.loadXhsAccountsPanel = loadXhsAccountsPanel;
window.createXhsAccount = createXhsAccount;

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
    const crawlSel = card.querySelector('.src-crawl-mode');
    const metaPatch = {
      enabled: card.querySelector('.src-enabled').checked,
      label: card.querySelector('.src-label').value.trim(),
    };
    if (crawlSel && !crawlSel.disabled && crawlSel.value) {
      metaPatch.crawl_mode = crawlSel.value;
    }
    await api('/api/sources/' + sourceId, {
      method: 'PATCH',
      body: JSON.stringify(metaPatch),
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
    await loadSourcesPanel();
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
