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

App.DISPLAY_TZ = 'Asia/Shanghai';

App.fmtTime = function(s) {
  if (!s) return '-';
  var t = String(s).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
  if (/Z$/i.test(t) || /[+-]\d{2}:\d{2}$/.test(t)) {
    var d = new Date(t);
    if (isNaN(d.getTime())) return t.replace('T', ' ').slice(0, 16) || '-';
    return d.toLocaleString('sv-SE', { timeZone: App.DISPLAY_TZ, hour12: false }).slice(0, 16);
  }
  if (/^\d{4}-\d{2}-\d{2}[T ]/.test(t)) return t.replace('T', ' ').slice(0, 16);
  return t.replace('T', ' ').slice(0, 16) || '-';
};

function fmtTime(s) { return App.fmtTime(s); }

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

App.navigatePartnerDetail = function(partnerId, opts) {
  opts = opts || {};
  const patch = {
    tab: 'partners',
    partner_id: partnerId,
    partner_tab: opts.partner_tab || 'intel',
    intel_id: null,
    raw_id: null,
  };
  if (opts.partner_tab === 'raw') {
    if (opts.task_id != null && opts.task_id !== '') patch.task_id = opts.task_id;
  } else {
    patch.task_id = null;
  }
  App.setQuery(patch);
  App.switchAppTab('partners');
};

App.navigateTaskDetail = function(taskId, opts) {
  opts = opts || {};
  App.setQuery({
    tab: 'tasks',
    monitor_task_id: taskId,
    task_tab: opts.task_tab || 'overview',
    run_id: null,
  });
  App.switchAppTab('tasks');
};

App.SETTINGS_TABS = ['sources', 'cookies', 'crawl', 'system', 'analysis'];
App.DEFAULT_SETTINGS_TAB = 'system';

App.isSettingsTab = function(tab) {
  return App.SETTINGS_TABS.indexOf(tab) >= 0;
};

App.openSettings = function(subTab) {
  const tab = App.isSettingsTab(subTab) ? subTab : App.DEFAULT_SETTINGS_TAB;
  const q = App.readQuery();
  q.set('tab', tab);
  history.replaceState(null, '', '/?' + q.toString());
  App.switchAppTab(tab);
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

function syncNavActiveState(tab) {
  document.querySelectorAll('.app-nav a[data-tab]').forEach(function(a) {
    a.classList.toggle('active', a.dataset.tab === tab);
  });
  const group = document.getElementById('navGroupSettings');
  const toggle = document.getElementById('navSettingsToggle');
  if (!group) return;
  const inSettings = App.isSettingsTab(tab);
  group.classList.toggle('is-active', inSettings);
  if (inSettings) group.classList.add('is-expanded');
  if (toggle) toggle.setAttribute('aria-expanded', group.classList.contains('is-expanded') ? 'true' : 'false');
}

function switchAppTab(tab, linkEl) {
  syncNavActiveState(tab);
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
  if (tab === 'partners' && typeof onPartnersTabActivate === 'function') onPartnersTabActivate();
  if (tab === 'tasks' && typeof onTasksTabActivate === 'function') onTasksTabActivate();
  if (tab === 'analysis' && typeof loadAnalysisConfig === 'function') loadAnalysisConfig();
  if (tab === 'analysis' && typeof startAiLogPoll === 'function') startAiLogPoll();
  if (tab !== 'analysis' && typeof stopAiLogPoll === 'function') stopAiLogPoll();
  if (tab === 'sources' && typeof loadSourcesPanel === 'function') loadSourcesPanel();
  if (tab === 'cookies' && typeof loadCookieInstances === 'function') loadCookieInstances();
  if (window.FieldLabels && FieldLabels.applyFieldLabels) FieldLabels.applyFieldLabels(document);
  if (tab === 'system') {
    if (typeof loadMonitorDefaultsForm === 'function') loadMonitorDefaultsForm();
    if (typeof reloadConfig === 'function') reloadConfig();
  }
}

App.switchAppTab = switchAppTab;

function initAppNav() {
  document.querySelectorAll('.app-nav a[data-tab]').forEach(function(a) {
    a.addEventListener('click', function(e) {
      e.preventDefault();
      navigateAppTab(a.dataset.tab, a);
    });
  });
  const settingsToggle = document.getElementById('navSettingsToggle');
  const settingsGroup = document.getElementById('navGroupSettings');
  if (settingsToggle && settingsGroup) {
    settingsToggle.addEventListener('click', function() {
      const expanded = settingsGroup.classList.toggle('is-expanded');
      settingsToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    });
  }
  switchAppTab(getTabFromUrl());
}

function navigateAppTab(tab, linkEl) {
  const q = App.readQuery();
  q.set('tab', tab);
  if (tab !== 'intel') q.delete('intel_id');
  if (tab !== 'raw') q.delete('raw_id');
  if (tab !== 'tasks') {
    q.delete('run_id');
    q.delete('monitor_task_id');
    q.delete('task_tab');
  }
  if (tab !== 'partners') {
    q.delete('partner_id');
    q.delete('partner_tab');
  }
  history.replaceState(null, '', '/?' + q.toString());
  switchAppTab(tab, linkEl);
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
    if (d.login_wait) {
      banner.style.display = 'block';
      const lw = d.login_wait;
      if (lw.workers && lw.workers.length > 1) {
        document.getElementById('login-wait-title').textContent = '等待登录 · 多 Worker（' + lw.workers.length + '）';
        const lines = lw.workers.map(function(w) {
          const site = siteLabel(w.site || w.source_id || '');
          const inst = w.instance_id ? ('/' + w.instance_id) : '';
          const el = w.elapsed_sec != null ? (' ' + w.elapsed_sec + 's') : '';
          return site + inst + el;
        }).join(' · ');
        document.getElementById('login-wait-detail').textContent = lines;
      } else {
        const site = lw.site || (lw.workers && lw.workers[0] && (lw.workers[0].site || lw.workers[0].source_id)) || '';
        const inst = lw.instance_id || (lw.workers && lw.workers[0] && lw.workers[0].instance_id);
        const title = '等待登录 · ' + siteLabel(site) + (inst ? (' / ' + inst) : '');
        document.getElementById('login-wait-title').textContent = title;
        const detail = lw.message || lw.detail || (lw.workers && lw.workers[0] && lw.workers[0].message) || '';
        const elapsedSec = lw.elapsed_sec != null ? lw.elapsed_sec : (lw.workers && lw.workers[0] && lw.workers[0].elapsed_sec);
        const elapsed = elapsedSec != null ? ('（已等待 ' + elapsedSec + ' 秒）') : '';
        document.getElementById('login-wait-detail').textContent = detail + elapsed;
      }
    } else {
      banner.style.display = 'none';
    }
  }
  if (typeof renderLogs === 'function' && d.logs) renderLogs(d.logs);
  if (typeof updateUI === 'function') updateUI(d);
}

let pollTimer = null;
let cookiePollCounter = 0;

App.refreshCookieBanner = function(data) {
  const banner = document.getElementById('cookie-diagnose-banner');
  if (!banner) return;
  const hasFail = data && data.has_diagnose_failures;
  banner.style.display = hasFail ? 'block' : 'none';
  if (hasFail && data.instances) {
    const bad = data.instances.filter(function(i) {
      return !i.cookies_file_exists || (i.last_diagnose && i.last_diagnose.diagnose_ok === false);
    });
    const names = bad.slice(0, 3).map(function(i) { return siteLabel(i.source_id) + '/' + i.instance_id; }).join('、');
    document.getElementById('cookie-diagnose-detail').textContent = names ? ('：' + names) : '';
  }
};

async function refreshCookieBannerFromApi() {
  try {
    const d = await api('/api/cookie-instances');
    App.refreshCookieBanner(d);
  } catch (e) {}
}

function startGlobalPoll() {
  if (pollTimer) return;
  async function tick() {
    try {
      const d = await api('/api/status');
      updateGlobalStatus(d);
    } catch (e) {}
    cookiePollCounter += 1;
    if (cookiePollCounter % 15 === 1) refreshCookieBannerFromApi();
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
