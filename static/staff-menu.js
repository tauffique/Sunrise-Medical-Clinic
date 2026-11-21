// Close the staff dropdown when clicking outside it, or after choosing an item.
(function () {
  var menu = document.querySelector('.staff-menu');
  if (!menu) return;
  document.addEventListener('click', function (e) {
    if (!menu.open) return;
    var pickedItem = e.target.closest('.staff-menu-panel a, .staff-menu-panel button');
    if (pickedItem || !menu.contains(e.target)) {
      menu.open = false;
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') menu.open = false;
  });
})();
