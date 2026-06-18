/* Cookie 实例管理 Tab */
function siteLabelCookie(s) {
  return s === 'heimao' ? '黑猫' : (s === 'xhs' ? '小红书' : s);
}

function diagnoseBadge(inst) {
  const ld = inst.last_diagnose;
  if (!inst.cookies_file_exists) return '<span class="badge badge-red">文件缺失</span>';
  if (!ld) return '<span class="badge">未诊断</span>';
  if (ld.diagnose_ok) return '<span class="badge badge-green">通过</span>';
  return '<span class="badge badge-red">失败</span>';
}

function renderCookieInstances(data) {
  const body = document.getElementById('cookieInstancesBody');
  if (!body) return;
  const list = (data && data.instances) || [];
  if (!list.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty">无 Worker 实例配置</td></tr>';
    return;
  }
  body.innerHTML = list.map(function(inst) {
    const sid = inst.source_id;
    const iid = inst.instance_id;
    const hints = (inst.last_diagnose && inst.last_diagnose.info && inst.last_diagnose.info.hints) || [];
    const hint = hints[0] ? ('<div class="meta">' + hints[0] + '</div>') : '';
    const uploadId = 'cookie-upload-' + sid + '-' + iid.replace(/[^a-z0-9_-]/gi, '_');
    return '<tr>' +
      '<td>' + siteLabelCookie(sid) + '</td>' +
      '<td><code>' + iid + '</code></td>' +
      '<td>' + (inst.cdp_port || '-') + '</td>' +
      '<td><code style="font-size:11px">' + (inst.cookies_file || '-') + '</code></td>' +
      '<td>' + (inst.cookie_count || 0) + '</td>' +
      '<td>' + diagnoseBadge(inst) + hint + '</td>' +
      '<td class="cookie-actions">' +
        '<button class="btn btn-gray btn-sm admin-only-save" onclick="diagnoseCookieInstance(\'' + sid + '\',\'' + iid + '\')">诊断</button> ' +
        '<textarea id="' + uploadId + '" rows="2" placeholder="粘贴 Cookie JSON…" class="admin-only-save" style="width:160px;font-size:11px;margin-top:4px"></textarea> ' +
        '<button class="btn btn-blue btn-sm admin-only-save" onclick="uploadCookieInstance(\'' + sid + '\',\'' + iid + '\',\'' + uploadId + '\')">保存</button>' +
      '</td></tr>';
  }).join('');
}

async function loadCookieInstances() {
  try {
    const d = await App.api('/api/cookie-instances');
    renderCookieInstances(d);
    if (typeof App.refreshCookieBanner === 'function') App.refreshCookieBanner(d);
    return d;
  } catch (e) {
    App.showToast(e.message || '加载失败', true);
  }
}

async function diagnoseCookieInstance(sourceId, instanceId) {
  try {
    App.showToast('正在诊断 ' + sourceId + '…');
    const d = await App.api('/api/cookie-instances/' + sourceId + '/' + instanceId + '/diagnose', { method: 'POST', body: '{}' });
    const ok = d.result && d.result.diagnose_ok;
    App.showToast(ok ? '诊断通过' : '诊断失败', !ok);
    await loadCookieInstances();
  } catch (e) {
    App.showToast(e.message || '诊断失败', true);
  }
}

async function uploadCookieInstance(sourceId, instanceId, textareaId) {
  const el = document.getElementById(textareaId);
  const cookies = el && el.value ? el.value.trim() : '';
  if (!cookies) return App.showToast('请粘贴 Cookie 内容', true);
  try {
    await App.api('/api/cookie-instances/' + sourceId + '/' + instanceId + '/upload', {
      method: 'POST',
      body: JSON.stringify({ cookies: cookies }),
    });
    if (el) el.value = '';
    App.showToast('Cookie 已保存');
    await loadCookieInstances();
  } catch (e) {
    App.showToast(e.message || '保存失败', true);
  }
}

window.loadCookieInstances = loadCookieInstances;
window.diagnoseCookieInstance = diagnoseCookieInstance;
window.uploadCookieInstance = uploadCookieInstance;
