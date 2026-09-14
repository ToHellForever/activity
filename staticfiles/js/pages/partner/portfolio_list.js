// === PORTFOLIO LIST ===

document.addEventListener('DOMContentLoaded', function() {
    // CSRF-токен берётся из скрытого поля формы на странице (см. portfolio_list.html)
    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input) return input.value;
        const match = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[2]) : '';
    }

    // Мгновенное удаление кейса
    document.querySelectorAll('.action-btn--delete[data-delete-url]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            var url = this.dataset.deleteUrl;
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }).then(function(response) {
                if (response.ok || response.redirected) {
                    var card = btn.closest('.portfolio-card');
                    if (card) card.remove();
                    // Если карточек не осталось — обновить страницу
                    var cards = document.querySelectorAll('.portfolio-card');
                    if (cards.length === 0) location.reload();
                }
            });
        });
    });

    // На мобильных (≤578px) кнопки редактирования/удаления скрыты —
    // переход к редактированию выполняется по клику на саму карточку
    document.querySelectorAll('.portfolio-card[data-edit-url]').forEach(function(card) {
        card.addEventListener('click', function(e) {
            if (window.matchMedia('(max-width: 578px)').matches) {
                window.location.href = card.dataset.editUrl;
            }
        });
    });
});
