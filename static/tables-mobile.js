// Copies each column heading onto its cells so tables can become cards on phones.
document.querySelectorAll('table').forEach(function (table) {
  var heads = Array.from(table.querySelectorAll('thead th')).map(function (th) {
    return th.textContent.trim();
  });
  table.querySelectorAll('tbody tr').forEach(function (tr) {
    Array.from(tr.children).forEach(function (cell, i) {
      if (cell.tagName === 'TD' && heads[i] && !cell.hasAttribute('colspan')) {
        cell.setAttribute('data-label', heads[i]);
      }
    });
  });
});
