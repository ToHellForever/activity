document.addEventListener('click', function(event) {
    const target = event.target;
    const favoriteLink = target && target.closest
        ? target.closest('.favourites-link')
        : null;

    if (!favoriteLink) return;
    event.preventDefault();

    // На странице может быть несколько кнопок для одного мероприятия
    // (например, разные варианты карточек под разрешения экрана) —
    // синхронизируем их состояние.
    const eventId = favoriteLink.dataset.eventId;
    const favoriteLinks = eventId
        ? document.querySelectorAll('.favourites-link[data-event-id="' + eventId + '"]')
        : [favoriteLink];

    const isPending = function() {
        return Array.prototype.some.call(favoriteLinks, function(link) {
            return link.dataset.pending === 'true';
        });
    };

    const setPending = function(pending) {
        Array.prototype.forEach.call(favoriteLinks, function(link) {
            if (pending) {
                link.dataset.pending = 'true';
            } else {
                delete link.dataset.pending;
            }
        });
    };

    const setActive = function(active) {
        Array.prototype.forEach.call(favoriteLinks, function(link) {
            link.classList.toggle('is-favorite', active);
            link.setAttribute('aria-label', active ? 'Удалить из избранного' : 'Добавить в избранное');
            link.title = active ? 'Удалить из избранного' : 'Добавить в избранное';
        });
    };

    if (isPending()) return;

    const showToast = function(message, isError) {
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'position-fixed top-0 end-0 p-3';
            container.style.zIndex = '1100';
            document.body.appendChild(container);
        }

        const toastElement = document.createElement('div');
        toastElement.className = `toast align-items-center text-white ${isError ? 'bg-danger' : 'bg-success'}`;
        toastElement.setAttribute('role', 'alert');
        toastElement.setAttribute('aria-live', 'assertive');
        toastElement.setAttribute('aria-atomic', 'true');
        toastElement.innerHTML = `
            <div class="d-flex">
                <div class="toast-body"></div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>`;
        toastElement.querySelector('.toast-body').textContent = message;
        container.appendChild(toastElement);

        const toast = new bootstrap.Toast(toastElement, {autohide: true, delay: 5000});
        toast.show();
        toastElement.addEventListener('hidden.bs.toast', function() {
            toastElement.remove();
        });
    };

    const redirectToLogin = function() {
        showToast('Для добавления в избранное нужно войти в аккаунт. Перенаправляем...', true);
        window.setTimeout(function() {
            window.location.href = favoriteLink.dataset.loginUrl || '/login/';
        }, 2000);
    };

    if (favoriteLink.dataset.isPartner === 'true' || window.IS_PARTNER === true) {
        showToast('Для партнёров эта функция недоступна', true);
        return;
    }

    const getCookie = function(name) {
        const cookie = document.cookie
            .split('; ')
            .find(function(item) {
                return item.startsWith(name + '=');
            });
        return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
    };

    setPending(true);
    fetch(favoriteLink.href, {
        method: 'POST',
        headers: {
            'X-CSRFToken': favoriteLink.dataset.csrfToken || getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(function(response) {
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json') || response.status >= 400) {
            redirectToLogin();
            return null;
        }
        return response.json();
    })
    .then(function(data) {
        if (!data) return;

        if (data.status === 'added') {
            setActive(true);
            showToast('Добавлено в избранное', false);
        } else if (data.status === 'removed') {
            setActive(false);
            showToast('Удалено из избранного', false);
        } else {
            showToast(data.message || 'Не удалось изменить избранное', true);
        }
    })
    .catch(function(error) {
        console.error('Favorite error:', error);
        redirectToLogin();
    })
    .finally(function() {
        setPending(false);
    });
});
