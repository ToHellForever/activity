/* ===== "Показать ещё" — догрузка карточек по 6 штук =====
   Использование: initShowMore('containerId') — прячет карточки сверх
   первых 6 и добавляет кнопку "Показать ещё" на всю ширину.
   Каждое нажатие открывает ещё 6 карточек, до конца списка. */

(function () {
  var STEP = 6;

  function initShowMore(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;

    var items = Array.prototype.slice.call(container.children);
    if (items.length <= STEP) return;

    var shown = STEP;

    function applyVisibility() {
      items.forEach(function (item, index) {
        item.style.display = index < shown ? '' : 'none';
      });
    }

    // Кнопка на всю ширину под контейнером
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'show-more-btn';
    btn.textContent = 'Показать ещё';

    btn.addEventListener('click', function () {
      shown += STEP;
      applyVisibility();
      if (shown >= items.length) {
        btn.remove();
      }
    });

    applyVisibility();
    container.insertAdjacentElement('afterend', btn);
  }

  window.initShowMore = initShowMore;
})();
