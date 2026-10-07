/**
 * Логотип в ЛК партнёра.
 *
 * - При клике на аватар/логотип (элементы с data-logo-trigger) открывается
    выбор файла через скрытый #partner-logo-input.
 * - При выборе файла файл загружается через /partner/save_field/?action=upload_logo.
 * - При клике на крестик (.logo-remove-btn) логотип удаляется
    через /partner/save_field/?action=delete_logo.
 * - После успешной загрузки/удаления страница перезагружается.
 *
 * Скрытый input рендерится в includes/sidebar.html и присутствует на всех
    страницах ЛК. На странице редактирования профиля есть отдельный #id_logo —
    его обрабатывает custom_media.js, здесь он не затрагивается.
 */
document.addEventListener('DOMContentLoaded', function () {
    var logoInput = document.getElementById('partner-logo-input');
    var csrfForm = document.getElementById('partner-logo-csrf');

    function getCsrf() {
        var inputs = csrfForm ? csrfForm.querySelectorAll('input[name=csrfmiddlewaretoken]') : [];
        return inputs.length ? inputs[0].value : '';
    }

    // Открыть диалог выбора файла при клике на аватар/логотип
    document.querySelectorAll('[data-logo-trigger]').forEach(function (trigger) {
        trigger.addEventListener('click', function (e) {
            // Крестик — не открываем диалог, он обрабатывается отдельно
            if (e.target.closest('.logo-remove-btn')) return;
            if (!logoInput) return;
            logoInput.click();
        });
    });

    // Защита от двойной инициализации, если скрипт подключён дважды
    if (window.__partnerLogoInitialized || !logoInput) {
        return;
    }
    window.__partnerLogoInitialized = true;

    // Загрузка нового логотипа
    if (logoInput) {
        logoInput.addEventListener('change', function () {
            var file = this.files[0];
            if (!file) return;

            var url = logoInput.dataset.url;
            if (!url) return;

            var formData = new FormData();
            formData.append('logo', file);
            formData.append('csrfmiddlewaretoken', getCsrf());

            // Подсветим, что идёт загрузка
            var saveBtn = document.querySelector('input[name="_save"]');
            if (saveBtn) saveBtn.disabled = true;

            fetch(url + '?action=upload_logo', {
                method: 'POST',
                body: formData
            })
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    if (data.status === 'success') {
                        showNotification('Логотип обновлён');
                        setTimeout(function () { location.reload(); }, 1000);
                    } else {
                        showNotification(data.message || 'Ошибка загрузки логотипа', true);
                        logoInput.value = '';
                    }
                })
                .catch(function () {
                    showNotification('Ошибка сети', true);
                    logoInput.value = '';
                })
                .finally(function () {
                    if (saveBtn) saveBtn.disabled = false;
                });
        });
    }

    // Удаление логотипа (делегирование — кнопка есть и в сайдбаре, и в шапке профиля)
    document.addEventListener('click', function (e) {
        var btn = e.target.closest ? e.target.closest('.logo-remove-btn') : null;
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();

        var url = logoInput ? logoInput.dataset.url : '';
        if (!url) return;

        var formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrf());

        fetch(url + '?action=delete_logo', {
            method: 'POST',
            body: formData
        })
            .then(function (resp) { return resp.json(); })
            .then(function (data) {
                if (data.status === 'success') {
                    showNotification('Логотип удалён');
                    setTimeout(function () { location.reload(); }, 1000);
                } else {
                    showNotification(data.message || 'Ошибка удаления логотипа', true);
                }
            })
            .catch(function () {
                showNotification('Ошибка сети', true);
            });
    });

    // Всплывающее уведомление
    function showNotification(text, isError) {
        var existing = document.getElementById('logo-notification');
        if (existing) existing.remove();

        var notif = document.createElement('div');
        notif.id = 'logo-notification';
        notif.textContent = text;
        notif.style.cssText =
            'position:fixed;top:20px;right:20px;padding:10px 20px;border-radius:8px;' +
            'color:#fff;font-size:13px;z-index:9999;opacity:1;transition:opacity 0.3s;' +
            'background:' + (isError ? '#f44336' : '#4caf50');
        document.body.appendChild(notif);
        setTimeout(function () {
            notif.style.opacity = '0';
            setTimeout(function () { notif.remove(); }, 300);
        }, 2000);
    }
});
