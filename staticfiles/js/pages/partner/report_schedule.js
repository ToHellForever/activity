// === REPORT SCHEDULE ===

document.addEventListener('DOMContentLoaded', function() {
    // Стандартные id полей Django-формы: id_frequency, id_period_type
    const frequencyField = document.getElementById('id_frequency');
    const periodTypeField = document.getElementById('id_period_type');
    if (!frequencyField || !periodTypeField) return;
    
    // Показываем/скрываем карточки в зависимости от выбранных значений
    function updateVisibility() {
        const frequency = frequencyField.value;
        const periodType = periodTypeField.value;
        
        // Скрываем все карточки с дополнительными настройками
        document.getElementById('dayOfWeekCard').style.display = 'none';
        document.getElementById('dayOfMonthCard').style.display = 'none';
        document.getElementById('customPeriodCard').style.display = 'none';
        
        // Показываем нужные карточки
        if (frequency === 'weekly') {
            document.getElementById('dayOfWeekCard').style.display = 'block';
        } else if (frequency === 'monthly') {
            document.getElementById('dayOfMonthCard').style.display = 'block';
        }
        
        if (periodType === 'custom') {
            document.getElementById('customPeriodCard').style.display = 'block';
        }
    }
    
    // Обновляем видимость при загрузке страницы
    updateVisibility();
    
    // Обновляем видимость при изменении значений
    frequencyField.addEventListener('change', updateVisibility);
    periodTypeField.addEventListener('change', updateVisibility);
    
    // Обработка отправки формы
    document.getElementById('reportScheduleForm').addEventListener('submit', function(e) {
        // Показываем индикатор загрузки
        const saveButton = document.getElementById('saveButton');
        saveButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Сохранение...';
        saveButton.disabled = true;
    });
});
