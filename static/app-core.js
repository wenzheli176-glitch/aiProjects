/* 统一控制台：核心 API、Tab、管理员 Session、全局状态、URL query */
window.App = window.App || {};
App.isAdmin = false;
App.authEnabled = true;

async function api(url, opts) {
  opts = opts || {};
  const headers = Object.assign({'Content-Type': 'application/json'}, opts.headers || {});
  const r = await fetch(url, Object.assign({}, opts, {headers}));
  let data = {};
  try { data = await r.json(); } catch (e) { data = {}; }
  if (!r.ok) {
    const err = new Error(data.msg || ('HTTP ' + r.status));
    err.status = r.status;
    err.data = data;
    throw err;
  }
  return data;
}

App.api = api;

App.readQuery = function() {
  return new URLSearchParams(window.location.search);
};

App.getQuery = function(key) {
  return App.readQuery().get(key);
};

App.setQuery = function(patch, replace) {
  const q = App.readQuery();
  Object.keys(patch).forEach(function(k) {
    const v = patch[k];
    if (v === null || v === undefined || v === '') q.delete(k);
    else q.set(k, String(v));
  });
  const qs = q.toString();
  const url = qs ? '/?' + qs : '/';
  if (replace) history.replaceState(null, '', url);
  else history.pushState(null, '', url);
  return q;
};

App.navigateIntel = function(filters) {
  const q = Object.assign({ tab: 'intel' }, filters || {});
  q.intel_id = null;
  App.setQuery(q);
  App.switchAppTab('intel');
};

App.navigateRaw = function(filters) {
  const q = Object.assign({ tab: 'raw' }, filters || {});
  q.raw_id = null;
  App.setQuery(q);
  App.switchAppTab('raw');
};

function showToast(msg, isErr) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast' + (isErr ? ' error' : '');
  t.style.display = 'block';
  setTimeout(function() { t.style.display = 'none'; }, 2800);
}

App.showToast = showToast;

function getTabFromUrl() {
  return App.getQuery('tab') || 'home';
}

function switchAppTab(tab, linkEl) {
  document.querySelectorAll('.app-nav a').forEach(function(a) {
    a.classList.toggle('active', a.dataset.tab === tab);
  });
  document.querySelectorAll('.app-panel').forEach(function(p) {
    p.classList.toggle('active', p.id === 'panel-' + tab);
  });
  if (linkEl) linkEl.classList.add('active');
  const q = App.readQuery();
  if (q.get('tab') !== tab) {
    q.set('tab', tab);
    history.replaceState(null, '', '/?' + q.toString());
  }
  if (tab === 'home' && typeof loadHomeDashboard === 'function') loadHomeDashboard();
  if (tab === 'intel' && typeof onIntelTabActivate === 'function') onIntelTabActivate();
  if (tab === 'raw' && typeof onRawTabActivate === 'function') onRawTabActivate();
  if (tab === 'partners' && typeof loadPartners === 'function') loadPartners();
  if (tab === 'tasks' && typeof onTasksTabActivate === 'function') onTasksTabActivate();
  if (tab === 'analysis' && typeof loadAnalysisConfig === 'function') loadAnalysisConfig();
  if (tab === 'analysis' && typeof startAiLogPoll === 'function') startAiLogPoll();
  if (tab !== 'analysis' && typeof stopAiLogPoll === 'function') stopAiLogPoll();
  if (tab === 'sources' && typeof loadSourcesPanel === 'function') loadSourcesPanel();
  if (window.FieldLabels && FieldLabels.applyFieldLabels) FieldLabels.applyFieldLabels(document);
  if (tab === 'system') {
    if (typeof loadMonitorDefaultsForm === 'function') loadMonitorDefaultsForm();
    if (typeof reloadConfig === 'function') reloadConfig();
  }
}

App.switchAppTab = switchAppTab;

function initAppNav() {
  document.querySelectorAll('.app-nav a').forEach(function(a) {
    a.addEventListener('click', function(e) {
      e.preventDefault();
      const tab = a.dataset.tab;
      const q = App.readQuery();
      q.set('tab', tab);
      if (tab !== 'intel') q.delete('intel_id');
      if (tab !== 'raw') q.delete('raw_id');
      if (tab !== 'tasks') q.delete('run_id');
      history.replaceState(null, '', '/?' + q.toString());
      switchAppTab(tab, a);
    });
  });
  switchAppTab(getTabFromUrl());
}

window.addEventListener('popstate', function() {
  switchAppTab(getTabFromUrl());
});

async function refreshAdminSession() {
  try {
    const d = await api('/api/admin/session');
    App.isAdmin = !!(d.logged_in && d.role === 'admin');
    App.authEnabled = d.auth_enabled !== false;
    document.body.classList.toggle('readonly-mode', App.authEnabled && !App.isAdmin);
    const st = document.getElementById('adminStatus');
    if (st) st.textContent = App.isAdmin ? '管理员' : (App.authEnabled ? '操作员' : '鉴权关闭');
    const loginBox = document.getElementById('adminLoginBox');
    const logoutBtn = document.getElementById('adminLogoutBtn');
    if (loginBox) loginBox.style.display = (App.authEnabled && !App.isAdmin) ? 'flex' : 'none';
    if (logoutBtn) logoutBtn.style.display = App.isAdmin ? 'inline-block' : 'none';
  } catch (e) {
    console.warn('admin session', e);
  }
}

async function adminLogin() {
  const pw = document.getElementById('adminPassword');
  if (!pw || !pw.value) return showToast('请输入管理员口令', true);
  try {
    await App.api('/api/admin/login', {method: 'POST', body: JSON.stringify({password: pw.value})});
    pw.value = '';
    await refreshAdminSession();
    showToast('管理员登录成功');
  } catch (e) {
    showToast(e.message || '登录失败', true);
  }
}

async function adminLogout() {
  try {
    await App.api('/api/admin/logout', {method: 'POST', body: JSON.stringify({})});
    await refreshAdminSession();
    showToast('已退出管理员');
  } catch (e) {
    showToast(e.message || '登出失败', true);
  }
}

App.refreshAdminSession = refreshAdminSession;

function siteLabel(site) {
  return site === 'heimao' ? '黑猫' : (site === 'xhs' ? '小红书' : site);
}

function updateGlobalStatus(d) {
  const dotB = document.getElementById('dot-browser');
  if (dotB) dotB.className = 'status-dot' + (d.browser_launched ? ' active' : '');
  const dotH = document.getElementById('dot-heimao');
  const dotX = document.getElementById('dot-xhs');
  if (dotH) dotH.className = 'status-dot' + (d.count_heimao > 0 ? ' active' : '');
  if (dotX) dotX.className = 'status-dot' + (d.count_xhs > 0 ? ' active' : '');
  const ch = document.getElementById('count-heimao');
  const cx = document.getElementById('count-xhs');
  if (ch) ch.textContent = d.count_heimao || 0;
  if (cx) cx.textContent = d.count_xhs || 0;
  const ri = document.getElementById('running-info');
  if (ri) {
    ri.textContent = d.running
      ? '运行中: ' + (d.running_type || '') + (d.phase ? ' / ' + d.phase : '')
      : '';
  }
  const banner = document.getElementById('login-wait-banner');
  if (banner) {
    if (d.login_wait && d.phase === 'waiting_login') {
      banner.style.display = 'block';
      const lw = d.login_wait;
      document.getElementById('login-wait-title').textContent = '等待登录 · ' + siteLabel(lw.site || '');
      document.getElementById('login-wait-detail').textContent = lw.detail || '';
    } else {
      banner.style.display = 'none';
    }
  }
  if (typeof renderLogs === 'function' && d.logs) renderLogs(d.logs);
  if (typeof updateUI === 'function') updateUI(d);
}

let pollTimer = null;
function startGlobalPoll() {
  if (pollTimer) return;
  async function tick() {
    try {
      const d = await api('/api/status');
      updateGlobalStatus(d);
    } catch (e) {}
  }
  tick();
  pollTimer = setInterval(tick, 2000);
}

App.startGlobalPoll = startGlobalPoll;

document.addEventListener('DOMContentLoaded', function() {
  initAppNav();
  refreshAdminSession();
  startGlobalPoll();
  if (window.FieldLabels && FieldLabels.load) {
    FieldLabels.load(function() {
      FieldLabels.applyFieldLabels(document);
    });
  }
  if (typeof loadSources === 'function') {
    loadSources().then(function() {
      if (typeof loadPartners === 'function') return loadPartners();
    }).then(function() {
      if (typeof loadTasks === 'function') return loadTasks();
    }).catch(function() {});
  }
  if (typeof reloadConfig === 'function') {
    reloadConfig().then(function() {
      if (typeof refreshAuthStatus === 'function') refreshAuthStatus();
    });
  }
});
