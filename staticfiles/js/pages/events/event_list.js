// === EVENT LIST ===

// Кнопка "Показать ещё" — AJAX-подгрузка следующих карточек
document.addEventListener('DOMContentLoaded', function() {
    const btn = document.getElementById('showMoreEventsBtn');
    if (!btn) return;

    const container = document.getElementById('eventsCardsContainer');
    const wrapper = document.getElementById('showMoreEventsWrapper');
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

document.addEventListener('DOMContentLoaded', function() {
    const tagsContainer = document.getElementById('tags-filters');
    const hiddenInput = document.getElementById('tags-hidden-input');
    if (!tagsContainer || !hiddenInput) return;

    const urlParams = new URLSearchParams(window.location.search);
    const selectedTags = urlParams.getAll('tags');

    tagsContainer.querySelectorAll('.tag-filter-chip').forEach(function(chip) {
        const tagId = chip.dataset.tagId;

        if (selectedTags.includes(tagId)) {
            chip.classList.add('active');
        }

        chip.addEventListener('click', function() {
            chip.classList.toggle('active');
            updateHiddenInput();
        });
    });

    function updateHiddenInput() {
        const selected = [];
        tagsContainer.querySelectorAll('.tag-filter-chip.active').forEach(function(chip) {
            selected.push(chip.dataset.tagId);
        });
        hiddenInput.value = selected.join(',');
    }
});
