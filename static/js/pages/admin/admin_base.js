// === ADMIN BASE ===

// API-ключ Яндекс.Карт: берём из meta-тега (добавлен в templates/admin/base.html),
// т.к. статические JS-файлы не обрабатываются Django-шаблонизатором
(function() {
    const meta = document.querySelector('meta[name="yandex-maps-api-key"]');
    window.YANDEX_MAPS_API_KEY = meta ? (meta.content || '') : '';
})();
