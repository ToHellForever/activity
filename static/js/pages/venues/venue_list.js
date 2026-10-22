// === VENUE LIST ===

// Кнопка "Показать ещё" — AJAX-подгрузка следующих карточек
document.addEventListener('DOMContentLoaded', function() {
    const btn = document.getElementById('showMoreVenuesBtn');
    if (btn) {
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
    }

    const filterForm = document.querySelector('.filters-form');
    if (filterForm) {
        filterForm.addEventListener('change', function(event) {
            const checkbox = event.target;
            if (!(checkbox instanceof HTMLInputElement) ||
                checkbox.type !== 'checkbox' ||
                checkbox.name !== 'equipment') {
                return;
            }

            filterForm.querySelectorAll('input[name="equipment"]').forEach(mirror => {
                if (mirror.value === checkbox.value) {
                    mirror.checked = checkbox.checked;
                }
            });
        });
    }
});
