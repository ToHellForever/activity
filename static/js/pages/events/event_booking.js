// Отправка заявки на участие в мероприятии через AJAX
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('event-booking-form');
    if (!form) return;

    const errorsBlock = document.getElementById('event-booking-errors');
    const successBlock = document.getElementById('event-booking-success');
    const submitBtn = document.getElementById('event-booking-submit');
    const modal = document.getElementById('eventBookingModal');

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

    function showErrors(messages) {
        errorsBlock.innerHTML = messages.map(function (msg) {
            return '<div>' + msg + '</div>';
        }).join('');
        errorsBlock.classList.remove('d-none');
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        errorsBlock.classList.add('d-none');
        form.querySelectorAll('.is-invalid').forEach(function (el) {
            el.classList.remove('is-invalid');
        });

        // --- Клиентская валидация полей ---
        const errors = [];
        const name = form.querySelector('[name="name"]');
        const phone = form.querySelector('[name="phone"]');
        const email = form.querySelector('[name="email"]');
        const participants = form.querySelector('[name="participants_count"]');

        function markInvalid(el, msg) {
            el.classList.add('is-invalid');
            errors.push(msg);
        }

        if (!name.value.trim()) {
            markInvalid(name, 'Укажите имя.');
        }

        const rawPhone = phone.value.trim();
        const digits = rawPhone.replace(/\D/g, '');
        if (!rawPhone) {
            markInvalid(phone, 'Укажите телефон.');
        } else {
            const validPhone = rawPhone.startsWith('+')
                ? (digits.length >= 10 && digits.length <= 15)
                : (digits.length === 10 || digits.length === 11);
            if (!validPhone) {
                markInvalid(phone, 'Телефон должен содержать 10 или 11 цифр (например, 9996052164, 89996052164 или +79996052164).');
            }
        }

        if (!email.value.trim()) {
            markInvalid(email, 'Укажите e-mail.');
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
            markInvalid(email, 'Укажите корректный e-mail.');
        }

        if (!participants.value || parseInt(participants.value, 10) < 1) {
            markInvalid(participants, 'Укажите количество участников.');
        }

        const consentCheckbox = form.querySelector('[name="personal_data_consent"]');
        if (consentCheckbox && !consentCheckbox.checked) {
            errors.push('Необходимо дать согласие на обработку персональных данных.');
        }

        if (errors.length > 0) {
            showErrors(errors);
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
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (data.success) {
                    form.classList.add('d-none');
                    successBlock.classList.remove('d-none');
                } else {
                    const fieldErrors = data.errors || {};
                    const messages = [];
                    Object.keys(fieldErrors).forEach(function (key) {
                        const value = fieldErrors[key];
                        (Array.isArray(value) ? value : [value]).forEach(function (msg) {
                            messages.push(msg);
                        });
                    });
                    showErrors(messages.length ? messages : ['Произошла ошибка, попробуйте позже.']);
                }
            })
            .catch(function () {
                showErrors(['Произошла ошибка, попробуйте позже.']);
            })
            .finally(function () {
                submitBtn.disabled = false;
            });
    });

    // Сброс состояния модалки при закрытии
    if (modal) {
        modal.addEventListener('hidden.bs.modal', function () {
            form.reset();
            form.classList.remove('d-none');
            form.querySelectorAll('.is-invalid').forEach(function (el) {
                el.classList.remove('is-invalid');
            });
            successBlock.classList.add('d-none');
            errorsBlock.classList.add('d-none');
            const consentCheckbox = form.querySelector('[name="personal_data_consent"]');
            if (consentCheckbox) {
                consentCheckbox.checked = false;
            }
        });
    }
});
