/* 列表分页：源数据 / 情报中心共用 */
var LIST_PAGE_SIZE_DEFAULT = 20;
var LIST_PAGE_SIZE_MAX = 200;
var LIST_PAGE_SIZE_OPTIONS = [20, 50, 100, 200];

function clampListPageSize(n) {
  var v = parseInt(n, 10);
  if (!v || v < 1) v = LIST_PAGE_SIZE_DEFAULT;
  return Math.min(LIST_PAGE_SIZE_MAX, v);
}

function listPageCount(total, pageSize) {
  var t = parseInt(total, 10) || 0;
  var ps = clampListPageSize(pageSize);
  return Math.max(1, Math.ceil(t / ps) || 1);
}

function listPageRange(page, pageSize, total) {
  var t = parseInt(total, 10) || 0;
  if (t <= 0) return { start: 0, end: 0 };
  var ps = clampListPageSize(pageSize);
  var p = Math.max(1, parseInt(page, 10) || 1);
  var start = (p - 1) * ps + 1;
  var end = Math.min(t, p * ps);
  return { start: start, end: end };
}

function formatListCountMeta(total, page, pageSize) {
  var t = parseInt(total, 10) || 0;
  if (t <= 0) return '共 0 条';
  var range = listPageRange(page, pageSize, t);
  return '共 ' + t + ' 条 · 第 ' + range.start + '–' + range.end + ' 条';
}

function renderListPagination(mountId, opts) {
  var el = document.getElementById(mountId);
  if (!el) return;
  var page = Math.max(1, parseInt(opts.page, 10) || 1);
  var pageSize = clampListPageSize(opts.pageSize);
  var total = parseInt(opts.total, 10) || 0;
  var pages = listPageCount(total, pageSize);
  if (page > pages) page = pages;

  if (total <= 0) {
    el.innerHTML = '';
    el.style.display = 'none';
    return;
  }
  el.style.display = '';

  var sizeOpts = LIST_PAGE_SIZE_OPTIONS.map(function(n) {
    return '<option value="' + n + '"' + (n === pageSize ? ' selected' : '') + '>' + n + ' 条/页</option>';
  }).join('');

  el.innerHTML =
    '<div class="list-pagination-inner">'
    + '<div class="list-pagination-range">第 ' + page + ' / ' + pages + ' 页</div>'
    + '<div class="list-pagination-actions">'
    + '<button type="button" class="btn btn-gray btn-sm"' + (page <= 1 ? ' disabled' : '')
    + ' data-page="' + (page - 1) + '">上一页</button>'
    + '<button type="button" class="btn btn-gray btn-sm"' + (page >= pages ? ' disabled' : '')
    + ' data-page="' + (page + 1) + '">下一页</button>'
    + '</div>'
    + '<label class="list-pagination-size">每页'
    + '<select class="list-page-size-select">' + sizeOpts + '</select>'
    + '</label>'
    + '</div>';

  el.querySelectorAll('button[data-page]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      if (btn.disabled) return;
      var next = parseInt(btn.getAttribute('data-page'), 10);
      if (opts.onPageChange) opts.onPageChange(next);
    });
  });
  var sel = el.querySelector('.list-page-size-select');
  if (sel) {
    sel.addEventListener('change', function() {
      if (opts.onPageSizeChange) opts.onPageSizeChange(clampListPageSize(sel.value));
    });
  }
}
