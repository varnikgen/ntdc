/**
 * NCDC admin helpers — offline, no external deps.
 */

function ncdcToast(message, type) {
  type = type || 'success';
  var container = document.getElementById('ncdcToasts');
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
function ncdcTableSearch(inputId, tableId, cols) {
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
    ncdcTableSearch(input.id || input.getAttribute('id'), tableId);
  });
});
