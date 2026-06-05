document.addEventListener('DOMContentLoaded', function() {
    // Функция для управления видимостью поля причины отклонения
    function updateRejectionReasonVisibility() {
        const statusField = document.getElementById('id_status');
        // Используем стандартный класс Django для полей
        const rejectionReasonField = document.querySelector('.field-rejection_reason');

        if (!statusField || !rejectionReasonField) {
            return;
        }

        const selectedStatus = statusField.value;
        const isRejected = selectedStatus === 'rejected';

        // Показываем или скрываем поле в зависимости от статуса
        rejectionReasonField.style.display = isRejected ? 'block' : 'none';

        // Устанавливаем readonly и стили в зависимости от статуса
        const rejectionReasonInput = document.getElementById('id_rejection_reason');
        if (rejectionReasonInput) {
            rejectionReasonInput.readOnly = !isRejected;
            rejectionReasonInput.style.backgroundColor = isRejected ? '#fff' : '#f0f0f0';
            rejectionReasonInput.style.color = isRejected ? '#000' : '#000';
        }
    }

    // Находим поле статуса
    const statusField = document.getElementById('id_status');

    if (statusField) {
        // Добавляем обработчик на изменение статуса
        statusField.addEventListener('change', updateRejectionReasonVisibility);

        // Вызываем функцию при загрузке страницы
        updateRejectionReasonVisibility();
    }
});
