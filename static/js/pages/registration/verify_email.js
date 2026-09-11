// === VERIFY EMAIL ===

document.addEventListener('DOMContentLoaded', function() {
    const inputs = document.querySelectorAll('.code-inputs input');
    const resendButton = document.getElementById('resend-code-button');
    const timerDisplay = document.getElementById('timer-display');
    let timeLeft = 60; // Таймер на 60 секунд

    // Функция для обновления таймера
    function updateTimer() {
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        timerDisplay.textContent = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
        timeLeft--;

        if (timeLeft < 0) {
            clearInterval(timerInterval);
            resendButton.style.display = 'block';
            timerDisplay.style.display = 'none';
        }
    }

    // Запускаем таймер
    const timerInterval = setInterval(updateTimer, 1000);
    updateTimer(); // Обновляем сразу, чтобы не ждать 1 секунду

    // Обработчики для полей ввода
    inputs.forEach((input, index) => {
        input.addEventListener('input', function() {
            if (this.value.length === 1) {
                if (index < inputs.length - 1) {
                    inputs[index + 1].focus();
                }
            }
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' && this.value.length === 0) {
                if (index > 0) {
                    inputs[index - 1].focus();
                }
            }
        });
    });

    // Обработчик для кнопки повторной отправки кода
    resendButton.addEventListener('click', function() {
        fetch('/resend-verification-code/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Код подтверждения был успешно отправлен повторно.');
                // Скрываем кнопку и показываем таймер
                resendButton.style.display = 'none';
                timerDisplay.style.display = 'inline';
                timeLeft = 60; // Сбрасываем таймер
                updateTimer();
            } else {
                alert('Произошла ошибка при отправке кода: ' + data.message);
            }
        })
        .catch(error => {
            alert('Произошла ошибка: ' + error);
        });
    });
});
