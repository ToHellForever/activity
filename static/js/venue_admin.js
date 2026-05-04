document.addEventListener('DOMContentLoaded', function() {
    // Ищем форму площадки
    const venueForm = document.getElementById('venue_form');
    if (!venueForm) return;

    // Ищем поле тарифа
    const tariffField = document.querySelector('#id_tariff');
    if (!tariffField) return;

    // Определяем ограничения и подсказки для каждого тарифа
        const tariffInfo = {
            free: {
                limits: {
                    max_photos: 1,
                    has_video: false,
                    description_limit: 500,
                    show_badge: false,
                    show_in_collections: false,
                    priority: 1
                },
                hints: {
                    photos: "В бесплатном тарифе можно загрузить только 1 фото.",
                    video: "Видео недоступно в бесплатном тарифе.",
                    description: "Максимальная длина описания: 500 символов.",
                    badge: 'Значок "Партнер" недоступен в бесплатном тарифе.',
                    collections: "Площадка не будет показана в подборках.",
                    priority: "Низкий приоритет в поисковой выдаче."
                }
            },
            standard: {
                limits: {
                    max_photos: 10,
                    has_video: false,
                    description_limit: 2000,
                    show_badge: true,
                    show_in_collections: true,
                    priority: 2
                },
                hints: {
                    photos: "В стандартном тарифе можно загрузить до 10 фото.",
                    video: "Видео недоступно в стандартном тарифе.",
                    description: "Максимальная длина описания: 2000 символов.",
                    badge: 'Значок "Партнер" будет отображаться.',
                    collections: "Площадка будет показана в подборках.",
                    priority: "Средний приоритет в поисковой выдаче."
                }
            },
            premium: {
                limits: {
                    max_photos: 25,
                    has_video: true,
                    description_limit: 5000,
                    show_badge: true,
                    show_in_collections: true,
                    priority: 3
                },
                hints: {
                    photos: "В премиум тарифе можно загрузить до 25 фото.",
                    video: "Видео доступно в премиум тарифе.",
                    description: "Максимальная длина описания: 5000 символов.",
                    badge: 'Значок "Партнер" будет отображаться.',
                    collections: "Площадка будет показана в подборках.",
                    priority: "Высокий приоритет в поисковой выдаче."
                }
            }
        };

    // Функция для обновления валидации полей и подсказок
    function updateFieldValidation() {
        const selectedTariff = tariffField.value;
        const tariff = tariffInfo[selectedTariff] || tariffInfo.free;
        const limits = tariff.limits;
        const hints = tariff.hints;

        // Функция для создания или обновления подсказки
        function updateHint(fieldId, hintText) {
            const field = document.querySelector(fieldId);
            if (!field) return;

            // Ищем существующую подсказку
            let hintElement = field.nextElementSibling;
            while (hintElement && !hintElement.classList.contains('tariff-hint')) {
                hintElement = hintElement.nextElementSibling;
            }

            // Если подсказки нет, создаем ее
            if (!hintElement) {
                hintElement = document.createElement('div');
                hintElement.className = 'tariff-hint';
                field.parentNode.insertBefore(hintElement, field.nextSibling);
            }

            // Обновляем текст подсказки
            hintElement.textContent = hintText;
            hintElement.style.color = '#666';
            hintElement.style.fontSize = '0.8em';
            hintElement.style.marginTop = '4px';
        }

        // Находим поле видео
        const videoField = document.querySelector('#id_video');
        if (videoField) {
            if (!limits.has_video) {
                videoField.setAttribute('disabled', 'disabled');
            } else {
                videoField.removeAttribute('disabled');
            }
            updateHint('#id_video', hints.video);
        }

        // Находим поле описания
        const descriptionField = document.querySelector('#id_full_description');
        if (descriptionField) {
            const maxLength = limits.description_limit;
            descriptionField.setAttribute('maxlength', maxLength);
            updateHint('#id_full_description', hints.description);
        }

        // Находим поле фото
        const photosField = document.querySelector('#id_images');
        if (photosField) {
            updateHint('#id_images', hints.photos);
        }

        // Находим поле значка партнера
        const badgeField = document.querySelector('#id_show_badge');
        if (badgeField) {
            updateHint('#id_show_badge', hints.badge);
        }

        // Находим поле участия в подборках
        const collectionsField = document.querySelector('#id_show_in_collections');
        if (collectionsField) {
            updateHint('#id_show_in_collections', hints.collections);
        }
    }

    // Инициализируем при загрузке
    updateFieldValidation();

    // Обновляем при изменении тарифа
    tariffField.addEventListener('change', updateFieldValidation);
});
