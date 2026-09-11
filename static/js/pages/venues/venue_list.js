// === VENUE LIST ===

// Кнопка "Показать ещё" — AJAX-подгрузка следующих карточек
document.addEventListener('DOMContentLoaded', function() {
    const btn = document.getElementById('showMoreVenuesBtn');
    if (!btn) return;

    const container = document.getElementById('venuesCardsContainer');
    const wrapper = document.getElementById('showMoreVenuesWrapper');
    const currentUrl = new URL(window.location.href);
    let loading = false;

    btn.addEventListener('click', function() {
        if (loading) return;
        loading = true;
        btn.textContent = 'Загрузка...';

        const nextPage = btn.dataset.nextPage;
        currentUrl.searchParams.set('page', nextPage);
        currentUrl.searchParams.set('ajax', '1');

        fetch(currentUrl.toString(), {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(resp => resp.json())
        .then(data => {
            container.insertAdjacentHTML('beforeend', data.html);
            if (data.next_page) {
                btn.dataset.nextPage = data.next_page;
                btn.textContent = 'Показать ещё';
            } else {
                wrapper.remove();
            }
        })
        .catch(() => {
            btn.textContent = 'Ошибка, попробуйте ещё раз';
        })
        .finally(() => {
            loading = false;
        });
    });
});
