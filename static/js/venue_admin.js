document.addEventListener('DOMContentLoaded', function() {
    // Ищем форму площадки
    const venueForm = document.getElementById('venue_form');
    if (!venueForm) return;

    // Ищем поле тарифа
    const tariffField = document.querySelector('#id_tariff');
    if (!tariffField) return;

    // Создаём контейнер для динамических ограничений
    const limitsContainer = document.createElement('div');
    limitsContainer.id = 'tariff_limits_container';
    limitsContainer.style.marginBottom = '20px';
    limitsContainer.style.padding = '15px';
    limitsContainer.style.backgroundColor = '#f8f9fa';
    limitsContainer.style.borderRadius = '5px';
    limitsContainer.style.border = '1px solid #dee2e6';

    // Вставляем контейнер после поля тарифа
    tariffField.closest('.form-group').after(limitsContainer);

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

    // Функция для обновления ограничений
    function updateTariffLimits() {
        const selectedTariff = tariffField.value;
        const limits = tariffLimits[selectedTariff] || tariffLimits.free;

        // Формируем HTML с ограничениями
        let html = `<h4>Ограничения для тарифа ${tariffField.options[tariffField.selectedIndex].text}:</h4>
                    <ul style="margin-bottom: 0;">`;

        html += `<li><strong>Количество фото:</strong> до ${limits.max_photos} ${getDeclension(limits.max_photos, ['фото', 'фото', 'фото'])}</li>`;
        html += `<li><strong>Видео:</strong> ${limits.has_video ? 'доступно' : 'недоступно'}</li>`;
        html += `<li><strong>Описание:</strong> до ${limits.description_limit} символов</li>`;
        html += `<li><strong>Бейдж:</strong> ${limits.show_badge ? 'есть' : 'нет'}</li>`;
        html += `<li><strong>Подборки:</strong> ${limits.show_in_collections ? 'показывается' : 'не показывается'}</li>`;
        html += `<li><strong>Приоритет:</strong> ${limits.priority} (чем выше, тем лучше позиция в выдаче)</li>`;
        
        html += `</ul>`;
        
        // Обновляем контейнер
        limitsContainer.innerHTML = html;
        
        // Обновляем валидацию полей
        updateFieldValidation(limits);
    }

    // Функция для склонения слов
    function getDeclension(number, titles) {
        const cases = [2, 0, 1, 1, 1, 2];
        return titles[(number % 100 > 4 && number % 100 < 20) ? 2 : cases[(number % 10 < 5) ? number % 10 : 5]];
    }

    // Функция для динамической валидации полей
    function updateFieldValidation(limits) {
        // Находим поле видео
        const videoField = document.querySelector('#id_video');
        if (videoField) {
            const videoGroup = videoField.closest('.form-group');
            if (!limits.has_video) {
                videoField.setAttribute('disabled', 'disabled');
                if (videoGroup) {
                    videoGroup.style.opacity = '0.5';
                    videoGroup.style.position = 'relative';
                    
                    // Добавляем подсказку
                    let hint = videoGroup.querySelector('.tariff-hint');
                    if (!hint) {
                        hint = document.createElement('div');
                        hint.className = 'tariff-hint';
                        hint.style.marginTop = '5px';
                        hint.style.fontSize = '0.8em';
                        hint.style.color = '#6c757d';
                        hint.innerHTML = '🔒 Видео доступно только в Premium тарифе';
                        videoGroup.appendChild(hint);
                    }
                }
            } else {
                videoField.removeAttribute('disabled');
                if (videoGroup) {
                    videoGroup.style.opacity = '1';
                    const hint = videoGroup.querySelector('.tariff-hint');
                    if (hint) hint.remove();
                }
            }
        }

        // Находим поле фото (предполагаем, что это поле images)
        const imagesField = document.querySelector('#id_images');
        if (imagesField) {
            const imagesGroup = imagesField.closest('.form-group');
            if (imagesGroup) {
                // Добавляем/обновляем подсказку о количестве фото
                let hint = imagesGroup.querySelector('.tariff-hint');
                if (!hint) {
                    hint = document.createElement('div');
                    hint.className = 'tariff-hint';
                    hint.style.marginTop = '5px';
                    hint.style.fontSize = '0.8em';
                    hint.style.color = '#6c757d';
                    imagesGroup.appendChild(hint);
                }
                hint.innerHTML = `📷 Максимум ${limits.max_photos} ${getDeclension(limits.max_photos, ['фото', 'фото', 'фото'])}`;
            }
        }

        // Находим поле описания
        const descriptionField = document.querySelector('#id_full_description');
        if (descriptionField) {
            const maxLength = limits.description_limit;
            descriptionField.setAttribute('maxlength', maxLength);
            
            // Добавляем счётчик символов с подсказкой
            let counter = descriptionField.parentNode.querySelector('.char-counter');
            if (!counter) {
                counter = document.createElement('div');
                counter.className = 'char-counter';
                counter.style.fontSize = '0.8em';
                counter.style.marginTop = '5px';
                descriptionField.parentNode.appendChild(counter);
            }
            
            // Обновляем счётчик с подсказкой
            function updateCounter() {
                const current = this.value.length;
                counter.innerHTML = `✏️ ${current}/${maxLength} символов (макс. для этого тарифа)`;
                if (current > maxLength * 0.9) {
                    counter.style.color = current >= maxLength ? '#dc3545' : '#ffc107';
                } else {
                    counter.style.color = '#6c757d';
                }
            }
            
            descriptionField.addEventListener('input', updateCounter);
            updateCounter.call(descriptionField);
        }
    }

    // Инициализируем при загрузке
    updateTariffLimits();

    // Обновляем при изменении тарифа
    tariffField.addEventListener('change', updateTariffLimits);

    // Добавляем стили для блокировки полей и подсказок
    const style = document.createElement('style');
    style.textContent = `
        .tariff-lock {
            cursor: not-allowed;
            font-size: 1.2em;
        }
        .tariff-hint {
            margin-top: 5px;
            font-size: 0.8em;
            color: #6c757d;
        }
        .char-counter {
            text-align: right;
        }
    `;
    document.head.appendChild(style);
});
