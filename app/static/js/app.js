/**
 * NTDC admin helpers — offline, no external deps.
 */

function ntdcToast(message, type) {
  type = type || 'success';
  var container = document.getElementById('ntdcToasts');
  if (!container) return;
  var el = document.createElement('div');
  var bg = type === 'danger' ? 'text-bg-danger' : (type === 'warning' ? 'text-bg-warning' : 'text-bg-success');
  el.className = 'toast align-items-center ' + bg + ' border-0 show';
  el.setAttribute('role', 'alert');
  el.innerHTML =
    '<div class="d-flex">' +
    '<div class="toast-body">' + (message || '') + '</div>' +
    '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>' +
    '</div>';
  container.appendChild(el);
  setTimeout(function () {
    el.classList.remove('show');
    setTimeout(function () { el.remove(); }, 300);
  }, 3500);
  var closeBtn = el.querySelector('.btn-close');
  if (closeBtn) closeBtn.addEventListener('click', function () { el.remove(); });
}

/**
 * Client-side table filter.
 * @param {string} inputId  - search input element id
 * @param {string} tableId  - table element id
 * @param {number[]} [cols] - column indexes to search (0-based); default all
 */
function ntdcTableSearch(inputId, tableId, cols) {
  var input = document.getElementById(inputId);
  var table = document.getElementById(tableId);
  if (!input || !table) return;

  var tbody = table.tBodies[0];
  if (!tbody) return;

  input.addEventListener('input', function () {
    var q = (input.value || '').trim().toLowerCase();
    var rows = tbody.querySelectorAll('tr[data-searchable]');
    var visible = 0;
    rows.forEach(function (row) {
      var text;
      if (cols && cols.length) {
        text = cols.map(function (i) {
          var cell = row.cells[i];
          return cell ? cell.textContent : '';
        }).join(' ');
      } else {
        text = row.getAttribute('data-search') || row.textContent;
      }
      var show = !q || text.toLowerCase().indexOf(q) !== -1;
      row.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    var empty = tbody.querySelector('tr.search-empty');
    if (empty) {
      empty.style.display = (visible === 0 && q) ? '' : 'none';
    }
  });
}

document.addEventListener('DOMContentLoaded', function () {
  // Auto-wire any [data-table-search] inputs
  document.querySelectorAll('[data-table-search]').forEach(function (input) {
    var tableId = input.getAttribute('data-table-search');
    ntdcTableSearch(input.id || input.getAttribute('id'), tableId);
  });
});

/**
 * Click-to-sort on tables with thead th[data-sort].
 * Optional data-sort-type="ip" | "number" | "text" (default text).
 */
function ntdcInitSortableTables() {
  document.querySelectorAll('table.ntdc-sortable').forEach(function (table) {
    var headers = table.querySelectorAll('thead th[data-sort]');
    headers.forEach(function (th, idx) {
      th.style.cursor = 'pointer';
      th.title = th.title || 'Сортировать';
      if (!th.querySelector('.sort-ind')) {
        var ind = document.createElement('span');
        ind.className = 'sort-ind text-muted ms-1';
        ind.textContent = '⇅';
        th.appendChild(ind);
      }
      th.addEventListener('click', function () {
        var col = parseInt(th.getAttribute('data-sort'), 10);
        if (isNaN(col)) col = idx;
        var type = th.getAttribute('data-sort-type') || 'text';
        var tbody = table.tBodies[0];
        if (!tbody) return;
        var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr[data-searchable]'));
        var dir = th.getAttribute('data-dir') === 'asc' ? 'desc' : 'asc';
        headers.forEach(function (h) {
          h.setAttribute('data-dir', '');
          var i = h.querySelector('.sort-ind');
          if (i) i.textContent = '⇅';
        });
        th.setAttribute('data-dir', dir);
        var ind = th.querySelector('.sort-ind');
        if (ind) ind.textContent = dir === 'asc' ? '▲' : '▼';

        function cellVal(row) {
          var cell = row.cells[col];
          if (!cell) return '';
          var raw = cell.getAttribute('data-sort-value');
          if (raw === null || raw === undefined) raw = (cell.textContent || '').trim();
          return raw;
        }
        function cmp(a, b) {
          var va = cellVal(a);
          var vb = cellVal(b);
          var r = 0;
          if (type === 'number') {
            r = (parseFloat(va) || 0) - (parseFloat(vb) || 0);
          } else if (type === 'ip') {
            function ipNum(s) {
              var p = String(s).split('.');
              if (p.length !== 4) return -1;
              var n = 0;
              for (var i = 0; i < 4; i++) n = n * 256 + (parseInt(p[i], 10) || 0);
              return n;
            }
            r = ipNum(va) - ipNum(vb);
          } else {
            r = String(va).localeCompare(String(vb), 'ru', { numeric: true, sensitivity: 'base' });
          }
          return dir === 'asc' ? r : -r;
        }
        rows.sort(cmp);
        rows.forEach(function (row) { tbody.appendChild(row); });
      });
    });
  });
}

document.addEventListener('DOMContentLoaded', function () {
  ntdcInitSortableTables();
});
