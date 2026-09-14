// Отправка заявки на бронирование площадки через AJAX
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('booking-form');
    if (!form) return;

    const errorsBlock = document.getElementById('booking-errors');
    const successBlock = document.getElementById('booking-success');
    const successContacts = document.getElementById('booking-success-contacts');
    const contactsText = document.getElementById('booking-contacts-text');
    const submitBtn = document.getElementById('booking-submit');

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        errorsBlock.classList.add('d-none');

        // --- Клиентская валидация полей ---
        const errors = [];

        const name = form.querySelector('[name="name"]');
        const phone = form.querySelector('[name="phone"]');
        const email = form.querySelector('[name="email"]');
        const eventDate = document.getElementById('booking_event_date');
        const participants = form.querySelector('[name="participants_count"]');
        const eventFormat = document.getElementById('booking_event_format');

        // Сброс подсветки
        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

        function markInvalid(el, msg) {
            el.classList.add('is-invalid');
            errors.push(msg);
        }

        if (!name.value.trim()) {
            markInvalid(name, 'Укажите имя.');
        }
        if (!phone.value.trim()) {
            markInvalid(phone, 'Укажите телефон.');
        } else {
            // Проверка формата телефона: +7XXXXXXXXXX или 11 цифр, начинающихся с 7/8
            const cleaned = phone.value.replace(/\D/g, '');
            const validPhone = (phone.value.startsWith('+') && cleaned.length === 12) ||
                               (!phone.value.startsWith('+') && cleaned.length === 11 && (cleaned[0] === '7' || cleaned[0] === '8'));
            if (!validPhone) {
                markInvalid(phone, 'Телефон должен быть в формате +7XXXXXXXXXX (11 цифр).');
            }
        }
        if (email.value.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
            markInvalid(email, 'Укажите корректный e-mail.');
        }
        if (!eventDate.value) {
            errors.push('Выберите дату и время мероприятия (не ранее завтрашнего дня).');
        }
        if (!participants.value || parseInt(participants.value, 10) < 1) {
            markInvalid(participants, 'Укажите количество участников.');
        }
        if (!eventFormat.value) {
            errors.push('Выберите формат мероприятия.');
        }

        if (errors.length > 0) {
            errorsBlock.innerHTML = errors.map(msg => '<div>' + msg + '</div>').join('');
            errorsBlock.classList.remove('d-none');
            return;
        }

        submitBtn.disabled = true;

        fetch(form.action, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: new FormData(form)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                form.classList.add('d-none');
                successBlock.classList.remove('d-none');
                // Для тарифа Standard контакты показываем после отправки заявки
                if (data.contacts) {
                    contactsText.textContent = data.contacts;
                    successContacts.classList.remove('d-none');
                }
            } else {
                let html = '';
                const errors = data.errors || {};
                for (const key in errors) {
                    const msgs = Array.isArray(errors[key]) ? errors[key] : [errors[key]];
                    msgs.forEach(msg => { html += '<div>' + msg + '</div>'; });
                }
                errorsBlock.innerHTML = html || 'Произошла ошибка, попробуйте позже.';
                errorsBlock.classList.remove('d-none');
            }
        })
        .catch(() => {
            errorsBlock.textContent = 'Произошла ошибка, попробуйте позже.';
            errorsBlock.classList.remove('d-none');
        })
        .finally(() => {
            submitBtn.disabled = false;
        });
    });

    // Сброс состояния модалки при закрытии
    const modal = document.getElementById('bookingModal');
    if (modal) {
        modal.addEventListener('hidden.bs.modal', function() {
            form.reset();
            form.classList.remove('d-none');
            form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
            successBlock.classList.add('d-none');
            successContacts.classList.add('d-none');
            errorsBlock.classList.add('d-none');
            // Сброс календаря и формата
            if (window.bookingCalendar) {
                window.bookingCalendar.clear();
            }
            const formatInput = document.getElementById('bookingFormatInput');
            if (formatInput) {
                formatInput.value = '';
            }
            const eventFormat = document.getElementById('booking_event_format');
            if (eventFormat) {
                eventFormat.value = '';
            }
        });
    }
});
