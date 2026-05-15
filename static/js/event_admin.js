document.addEventListener('DOMContentLoaded', function() {
    console.log("Event Admin JS loaded");
    
    // Функция для управления видимостью поля причины отклонения
    function updateRejectionReasonVisibility() {
        console.log("updateRejectionReasonVisibility called");
        
        const statusField = document.getElementById('id_status');
        // Используем стандартный класс Django для полей
        const rejectionReasonField = document.querySelector('.field-rejection_reason');
        
        console.log("Status field:", statusField);
        console.log("Rejection reason field:", rejectionReasonField);
        
        if (!statusField || !rejectionReasonField) {
            console.log("Fields not found, exiting");
            return;
        }

        const selectedStatus = statusField.value;
        const isRejected = selectedStatus === 'rejected';

        console.log("Selected status:", selectedStatus);
        console.log("Is rejected:", isRejected);

        // Показываем или скрываем поле в зависимости от статуса
        rejectionReasonField.style.display = isRejected ? 'block' : 'none';
        console.log("Field display set to:", isRejected ? 'block' : 'none');

        // Устанавливаем readonly и стили в зависимости от статуса
        const rejectionReasonInput = document.getElementById('id_rejection_reason');
        if (rejectionReasonInput) {
            rejectionReasonInput.readOnly = !isRejected;
            rejectionReasonInput.style.backgroundColor = isRejected ? '#fff' : '#f0f0f0';
            rejectionReasonInput.style.color = isRejected ? '#000' : '#000';
            console.log("Input readonly set to:", !isRejected);
            console.log("Input background color set to:", isRejected ? '#fff' : '#f0f0f0');
            console.log("Input text color set to:", 'black');
        }
    }

    // Находим поле статуса
    const statusField = document.getElementById('id_status');
    console.log("Initial status field:", statusField);
    
    if (statusField) {
        // Добавляем обработчик на изменение статуса
        statusField.addEventListener('change', updateRejectionReasonVisibility);
        console.log("Event listener added to status field");
        
        // Вызываем функцию при загрузке страницы
        updateRejectionReasonVisibility();
    } else {
        console.log("Status field not found");
    }
});