// === BUY TICKET ===

// Лимит бронирования без оплаты: не более 3 билетов на мероприятие.
// Дублирует серверную проверку в payment/views.py (create_payment).
const MAX_RESERVED_TICKETS = 3;

// Toast-уведомление (bootstrap подключён глобально в base.html)
function showToast(message, isError) {
    const container = document.getElementById('toastContainer') || (function() {
        const c = document.createElement('div');
        c.id = 'toastContainer';
        c.className = 'toast-container position-fixed end-0 top-0 p-3';
        c.style.zIndex = '1080';
        document.body.appendChild(c);
        return c;
    })();

    const el = document.createElement('div');
    el.className = 'toast align-items-center text-white ' + (isError === false ? 'bg-success' : 'bg-danger');
    el.setAttribute('role', 'alert');
    el.setAttribute('aria-live', 'assertive');
    el.setAttribute('aria-atomic', 'true');
    el.innerHTML = '<div class="d-flex">' +
        '<div class="toast-body"></div>' +
        '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
        '</div>';
    el.querySelector('.toast-body').textContent = message;
    container.appendChild(el);

    const toast = new bootstrap.Toast(el, { autohide: true, delay: 5000 });
    toast.show();
    el.addEventListener('hidden.bs.toast', function() { el.remove(); });
}

// Ограничение количества при включённом бронировании без оплаты
(function initReservedLimit() {
    const quantityInput = document.getElementById('quantity');
    const reserveCheckbox = document.getElementById('reserve_without_payment');
    if (!quantityInput || !reserveCheckbox) return;

    const baseMax = parseInt(quantityInput.max) || 99;

    function applyLimit(showNotice) {
        if (reserveCheckbox.checked) {
            quantityInput.max = Math.min(baseMax, MAX_RESERVED_TICKETS);
            const val = parseInt(quantityInput.value) || 0;
            if (val > MAX_RESERVED_TICKETS) {
                quantityInput.value = MAX_RESERVED_TICKETS;
                if (showNotice !== false) {
                    showToast('При бронировании без оплаты можно выбрать не более ' +
                        MAX_RESERVED_TICKETS + ' билетов на мероприятие.', true);
                }
            }
        } else {
            quantityInput.max = baseMax;
        }
    }

    reserveCheckbox.addEventListener('change', function() {
        applyLimit(this.checked);
    });

    quantityInput.addEventListener('input', function() {
        const val = parseInt(this.value) || 0;
        if (reserveCheckbox.checked && val > MAX_RESERVED_TICKETS) {
            this.value = MAX_RESERVED_TICKETS;
            showToast('При бронировании без оплаты можно выбрать не более ' +
                MAX_RESERVED_TICKETS + ' билетов на мероприятие.', true);
        }
    });

    applyLimit(false);
})();

document.getElementById('request_to_organizer').addEventListener('change', function() {
    const isChecked = this.checked;
    const quantityInput = document.getElementById('quantity');
    const reserveCheckbox = document.getElementById('reserve_without_payment');
    const submitButton = document.querySelector('#ticketForm button[type="submit"]');
    const organizerQuestionGroup = document.getElementById('organizerQuestionGroup');

    if (isChecked) {
        quantityInput.disabled = true;
        if (reserveCheckbox) reserveCheckbox.disabled = true;
        submitButton.textContent = 'Оставить заявку';
        organizerQuestionGroup.style.display = 'block';
    } else {
        quantityInput.disabled = false;
        if (reserveCheckbox) reserveCheckbox.disabled = false;
        submitButton.textContent = 'Продолжить';
        organizerQuestionGroup.style.display = 'none';
    }
});

document.getElementById('ticketForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const isRequestToOrganizer = formData.get('request_to_organizer') === 'on';

    fetch(this.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (response.redirected) {
            window.location.href = response.url;
            return;
        }
        return response.json();
    })
    .then(data => {
        if (data && data.payment_url) {
            window.location.href = data.payment_url;
        } else if (data && data.success) {
            if (isRequestToOrganizer) {
                alert('Ваша заявка отправлена организатору!');
            } else {
                alert('Ваш билет забронирован! На вашу почту отправлено письмо с ссылкой для оплаты.');
            }
            window.location.href = data.redirect_url || '/';
        } else if (data && data.error) {
            alert('Ошибка: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Произошла ошибка при обработке платежа');
    });
});
