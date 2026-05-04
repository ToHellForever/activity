document.addEventListener('DOMContentLoaded', function() {
    // Ищем форму площадки
    const venueForm = document.getElementById('venue_form');
    if (!venueForm) return;

    // Ищем поле тарифа
    const tariffField = document.querySelector('#id_tariff');
    if (!tariffField) return;

    // Определяем ограничения для каждого тарифа
    const tariffLimits = {
        free: {
            max_photos: 1,
            has_video: false,
            description_limit: 500,
            show_badge: false,
            show_in_collections: false,
            priority: 1
        },
        standard: {
            max_photos: 10,
            has_video: false,
            description_limit: 2000,
            show_badge: true,
            show_in_collections: true,
            priority: 2
        },
        premium: {
            max_photos: 25,
            has_video: true,
            description_limit: 5000,
            show_badge: true,
            show_in_collections: true,
            priority: 3
        }
    };

    // Функция для обновления валидации полей
    function updateFieldValidation() {
        const selectedTariff = tariffField.value;
        const limits = tariffLimits[selectedTariff] || tariffLimits.free;

        // Находим поле видео
        const videoField = document.querySelector('#id_video');
        if (videoField) {
            if (!limits.has_video) {
                videoField.setAttribute('disabled', 'disabled');
            } else {
                videoField.removeAttribute('disabled');
            }
        }

        // Находим поле описания
        const descriptionField = document.querySelector('#id_full_description');
        if (descriptionField) {
            const maxLength = limits.description_limit;
            descriptionField.setAttribute('maxlength', maxLength);
        }
    }

    // Инициализируем при загрузке
    updateFieldValidation();

    // Обновляем при изменении тарифа
    tariffField.addEventListener('change', updateFieldValidation);
});
