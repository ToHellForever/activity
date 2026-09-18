(function () {
    const modal = document.getElementById('venue-request-modal');
    const form = document.getElementById('venue-request-form');

    if (!modal || !form) {
        return;
    }

    const result = modal.querySelector('[data-venue-request-result]');
    const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;

    function clearErrors() {
        modal.querySelectorAll('.venue-request-field-error').forEach((element) => {
            element.textContent = '';
        });
        result.textContent = '';
        result.classList.remove('is-visible');
    }

    function closeModal() {
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('venue-request-modal-open');
    }

    function openModal(event) {
        event.preventDefault();
        clearErrors();
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('venue-request-modal-open');
        modal.querySelector('input:not([type=hidden])').focus();
    }

    document.querySelectorAll('[data-open-venue-request]').forEach((trigger) => {
        trigger.addEventListener('click', openModal);
    });

    modal.querySelectorAll('[data-close-venue-request]').forEach((trigger) => {
        trigger.addEventListener('click', closeModal);
    });

    modal.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal.classList.contains('is-open')) {
            closeModal();
        }
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearErrors();

        const submitButton = form.querySelector('.venue-request-modal__submit');
        submitButton.disabled = true;
        submitButton.textContent = 'Отправляем...';

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                Object.entries(data.errors || {}).forEach(([field, errors]) => {
                    const errorElement = modal.querySelector(`[data-error-for="${field}"]`);
                    if (errorElement) {
                        errorElement.textContent = errors.join(' ');
                    }
                });
                return;
            }

            form.reset();
            result.textContent = 'Заявка отправлена. Администратор свяжется с вами по указанным контактам.';
            result.classList.add('is-visible');
        } catch (error) {
            result.textContent = 'Не удалось отправить заявку. Попробуйте ещё раз.';
            result.classList.add('is-visible');
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = 'Отправить заявку';
        }
    });
})();