// === MODAL QUESTION ===

document.addEventListener('DOMContentLoaded', function() {
    // Счётчик символов
    const questionText = document.getElementById('questionText');
    const charCount = document.getElementById('charCount');

    if (questionText && charCount) {
        questionText.addEventListener('input', function() {
            charCount.textContent = questionText.value.length;
        });
    }

    // Обработка отправки вопроса
    const sendQuestionBtn = document.getElementById('sendQuestionBtn');
    if (sendQuestionBtn) {
        sendQuestionBtn.addEventListener('click', function() {
            const question = questionText.value.trim();
            const emailInput = document.getElementById('userEmail');
            const email = emailInput ? emailInput.value.trim() : '';
            const nameInput = document.getElementById('userName');
            const name = nameInput ? nameInput.value.trim() : '';

            if (!question) {
                alert('Пожалуйста, введите ваш вопрос');
                return;
            }

            // Проверяем email только для неавторизованных пользователей
            const emailFieldContainer = document.getElementById('emailFieldContainer');
            if (emailFieldContainer && !email) {
                alert('Пожалуйста, введите ваш email');
                return;
            }

            if (question.length > 1000) {
                alert('Вопрос не должен превышать 1000 символов');
                return;
            }

            // Отключаем кнопку на время отправки
            sendQuestionBtn.disabled = true;
            sendQuestionBtn.textContent = 'Отправка...';

            // Собираем данные формы
            const formData = new FormData();
            formData.append('question', question);
            formData.append('email', email);
            formData.append('first_name', name);

            // Получаем event_id из data-атрибута кнопки "Задать вопрос"
            const questionLink = document.querySelector('.question-organizator');
            const eventId = questionLink ? questionLink.getAttribute('data-event-id') : null;

            if (!eventId) {
                alert('Ошибка: не удалось определить мероприятие');
                sendQuestionBtn.disabled = false;
                sendQuestionBtn.textContent = 'ОТПРАВИТЬ ЗАПРОС';
                return;
            }

            // Отправляем AJAX-запрос
            fetch('/send-event-request/' + eventId + '/', {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Ваш вопрос успешно отправлен организатору!');
                    const modal = bootstrap.Modal.getInstance(document.getElementById('questionModal'));
                    modal.hide();
                    document.getElementById('questionForm').reset();
                    charCount.textContent = '0';
                } else {
                    alert(data.message || 'Произошла ошибка при отправке заявки.');
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
                alert('Произошла ошибка при отправке заявки. Пожалуйста, попробуйте еще раз.');
            })
            .finally(() => {
                sendQuestionBtn.disabled = false;
                sendQuestionBtn.textContent = 'ОТПРАВИТЬ ЗАПРОС';
            });
        });
    }
});
