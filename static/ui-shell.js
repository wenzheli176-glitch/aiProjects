/* Modal / Drawer / Toast / Confirm — shared UI shell */
window.UiShell = window.UiShell || {};

(function() {
  var overlayStack = [];

  function ensureRoot() {
    var root = document.getElementById('ui-shell-root');
    if (root) return root;
    root = document.createElement('div');
    root.id = 'ui-shell-root';
    document.body.appendChild(root);
    return root;
  }

  function closeTop() {
    var el = overlayStack.pop();
    if (el && el.parentNode) el.parentNode.removeChild(el);
    document.body.classList.toggle('ui-shell-open', overlayStack.length > 0);
  }

  function onKeydown(e) {
    if (e.key === 'Escape' && overlayStack.length) {
      var top = overlayStack[overlayStack.length - 1];
      if (top && top.dataset.closable !== '0') closeTop();
    }
  }
  document.addEventListener('keydown', onKeydown);

  function openOverlay(className, innerHtml, opts) {
    opts = opts || {};
    var root = ensureRoot();
    var wrap = document.createElement('div');
    wrap.className = 'ui-overlay ' + className;
    wrap.dataset.closable = opts.closable === false ? '0' : '1';
    wrap.innerHTML = innerHtml;
    wrap.addEventListener('click', function(e) {
      if (e.target === wrap && opts.closable !== false) closeTop();
    });
    root.appendChild(wrap);
    overlayStack.push(wrap);
    document.body.classList.add('ui-shell-open');
    return wrap;
  }

  UiShell.close = closeTop;

  UiShell.toast = function(msg, isErr) {
    if (window.App && App.showToast) App.showToast(msg, isErr);
  };

  UiShell.confirm = function(message, title) {
    return new Promise(function(resolve) {
      var html = '<div class="ui-modal-box"><div class="ui-modal-head"><h3>' + esc(title || '确认') + '</h3></div>'
        + '<div class="ui-modal-body"><p>' + esc(message) + '</p></div>'
        + '<div class="ui-modal-foot">'
        + '<button type="button" class="btn btn-gray btn-sm" data-act="cancel">取消</button>'
        + '<button type="button" class="btn btn-primary btn-sm" data-act="ok">确定</button>'
        + '</div></div>';
      var wrap = openOverlay('ui-modal-overlay', html, { closable: false });
      wrap.querySelector('[data-act=cancel]').onclick = function() { closeTop(); resolve(false); };
      wrap.querySelector('[data-act=ok]').onclick = function() { closeTop(); resolve(true); };
    });
  };

  UiShell.modal = function(opts) {
    opts = opts || {};
    var foot = '';
    if (opts.showFooter !== false) {
      foot = '<div class="ui-modal-foot">'
        + (opts.cancelLabel ? '<button type="button" class="btn btn-gray btn-sm" data-act="cancel">' + esc(opts.cancelLabel) + '</button>' : '')
        + (opts.confirmLabel ? '<button type="button" class="btn btn-primary btn-sm" data-act="ok">' + esc(opts.confirmLabel) + '</button>' : '')
        + '</div>';
    }
    var html = '<div class="ui-modal-box' + (opts.wide ? ' ui-modal-wide' : '') + '">'
      + '<div class="ui-modal-head"><h3>' + esc(opts.title || '') + '</h3>'
      + '<button type="button" class="ui-close-btn" data-act="close" aria-label="关闭">&times;</button></div>'
      + '<div class="ui-modal-body">' + (opts.bodyHtml || '') + '</div>' + foot + '</div>';
    var wrap = openOverlay('ui-modal-overlay', html, { closable: opts.closable !== false });
    function doClose() {
      if (opts.onClose) opts.onClose(wrap);
      closeTop();
      if (opts.onClosed) opts.onClosed();
    }
    wrap.querySelector('[data-act=close]').onclick = doClose;
    var cancelBtn = wrap.querySelector('[data-act=cancel]');
    if (cancelBtn) cancelBtn.onclick = function() { if (opts.onCancel) opts.onCancel(); doClose(); };
    var okBtn = wrap.querySelector('[data-act=ok]');
    if (okBtn) okBtn.onclick = function() {
      if (opts.onConfirm) {
        var r = opts.onConfirm(wrap);
        if (r && r.then) r.then(function(v) { if (v !== false) doClose(); });
        else if (r !== false) doClose();
      } else doClose();
    };
    if (opts.onMount) opts.onMount(wrap);
    return wrap;
  };

  UiShell.drawer = function(opts) {
    opts = opts || {};
    var width = opts.width || '720px';
    var html = '<div class="ui-drawer-panel" style="max-width:' + esc(width) + '">'
      + '<div class="ui-drawer-head"><h3>' + esc(opts.title || '') + '</h3>'
      + '<button type="button" class="ui-close-btn" data-act="close">&times;</button></div>'
      + '<div class="ui-drawer-body">' + (opts.bodyHtml || '') + '</div></div>';
    var wrap = openOverlay('ui-drawer-overlay', html);
    wrap.querySelector('[data-act=close]').onclick = function() { closeTop(); if (opts.onClose) opts.onClose(); };
    return wrap;
  };

  UiShell.setDrawerBody = function(wrap, html) {
    if (!wrap) return;
    var body = wrap.querySelector('.ui-drawer-body');
    if (body) body.innerHTML = html;
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  }
})();
