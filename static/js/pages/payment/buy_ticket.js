// === BUY TICKET ===

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
