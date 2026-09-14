// === PORTFOLIO FORM ===

document.addEventListener('DOMContentLoaded', function() {
    
    var displayInput = document.getElementById('id_event_date_display');
    var hiddenInput = document.getElementById('id_event_date');
    var form = document.getElementById('portfolioForm');

    // 1. Инициализация вашего родного календаря
    if (typeof CustomCalendar !== 'undefined') {
        window.portfolioCalendar = new CustomCalendar(
            'id_event_date_display',
            'eventDateCalendar',
            'id_event_date', // на случай, если календарь это поддерживает
            {
                displayDateFormat: 'dd.mm.yyyy',
                valueDateFormat: 'yyyy-mm-dd',
                allowPastDates: true
            }
        );
    } else {
        console.error("Скрипт CustomCalendar не загружен!");
    }

    // Функция конвертации ДД.ММ.ГГГГ -> ГГГГ-ММ-ДД
    function convertToServerFormat(dateStr) {
        if (!dateStr) return '';
        // Убираем лишние пробелы
        dateStr = dateStr.trim();
        // Проверяем формат ДД.ММ.ГГГГ
        var parts = dateStr.split('.');
        if (parts.length === 3) {
            var day = parts[0].padStart(2, '0');
            var month = parts[1].padStart(2, '0');
            var year = parts[2];
            return year + '-' + month + '-' + day;
        }
        return dateStr; // если формат уже другой
    }

    // 2. Синхронизация: при любом изменении видимого поля обновляем скрытое
    if (displayInput && hiddenInput) {
        // Отслеживаем изменения (календарь меняет value видимого поля)
        displayInput.addEventListener('change', function() {
            hiddenInput.value = convertToServerFormat(displayInput.value);
        });
        
        // На всякий случай отслеживаем клики по календарю
        var calendarPopup = document.getElementById('eventDateCalendar');
        if (calendarPopup) {
            calendarPopup.addEventListener('click', function() {
                setTimeout(function() {
                    hiddenInput.value = convertToServerFormat(displayInput.value);
                }, 50);
            });
        }
    }

    // 3. ГЛАВНОЕ: Синхронизация перед отправкой формы
    if (form && displayInput && hiddenInput) {
        form.addEventListener('submit', function(e) {
            hiddenInput.value = convertToServerFormat(displayInput.value);
        });
    }

    // ---------- Дальше идёт ваш остальной код без изменений ----------

    // CSRF-токен берётся из формы (статический JS не обрабатывается шаблонизатором)
    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input) return input.value;
        const match = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[2]) : '';
    }

    // Мгновенное удаление кейса (кнопка "УДАЛИТЬ КЕЙС")
    document.querySelectorAll('.btn-portfolio-delete[data-delete-url]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            var url = this.dataset.deleteUrl;
            var listUrl = this.dataset.listUrl || '/partner/portfolio/';
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }).then(function(response) {
                if (response.ok || response.redirected) {
                    window.location.href = listUrl;
                }
            });
        });
    });

    // Счётчик символов для названия
    var titleInput = document.getElementById('id_title');
    var titleCounter = document.getElementById('titleCounter');
    if (titleInput && titleCounter) {
        titleInput.addEventListener('input', function() {
            titleCounter.textContent = this.value.length + '/100';
        });
        titleCounter.textContent = titleInput.value.length + '/100';
    }

    // Счётчик символов для описания
    var descInput = document.getElementById('id_description');
    var descCounter = document.getElementById('descCounter');
    if (descInput && descCounter) {
        descInput.addEventListener('input', function() {
            descCounter.textContent = this.value.length + '/1500';
        });
        descCounter.textContent = descInput.value.length + '/1500';
    }

    // Предпросмотр новых фотографий
    var photoInput = document.getElementById('id_images');
    var photoPreview = document.getElementById('photoPreview');

    // Массив накопленных (ещё не сохранённых) новых фото — чтобы повторный выбор добавлял, а не заменял
    window.selectedPortfolioPhotos = [];

    // Синхронизация массива файлов с input file (чтобы на сервер ушло всё накопленное)
    window.syncPortfolioPhotosToInput = function() {
        if (!photoInput) return;
        var dt = new DataTransfer();
        window.selectedPortfolioPhotos.forEach(function(file) {
            if (file) dt.items.add(file);
        });
        photoInput.files = dt.files;
    };

    // Перерисовка превью из массива накопленных фото
    window.renderPortfolioPreviews = function() {
        if (!photoPreview) return;
        photoPreview.innerHTML = '';
        window.selectedPortfolioPhotos.forEach(function(file, index) {
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function(e) {
                var div = document.createElement('div');
                div.className = 'photo-preview-item';
                div.setAttribute('data-index', index);
                div.innerHTML = '<img src="' + e.target.result + '" alt="Preview">' +
                    '<span class="photo-remove" data-index="' + index + '" onclick="removePreview(this)">✕</span>';
                // Вставляем превью перед кнопкой «+», если она внутри контейнера
                var addBtn = document.getElementById('portfolioAddPhotoBtn');
                if (addBtn && addBtn.parentElement === photoPreview) {
                    photoPreview.insertBefore(div, addBtn);
                } else {
                    photoPreview.appendChild(div);
                }
                updatePlaceholderVisibility();
            };
            reader.readAsDataURL(file);
        });
        updatePlaceholderVisibility();
    }

    if (photoInput && photoPreview) {
        photoInput.addEventListener('change', function() {
            var incoming = Array.prototype.slice.call(this.files);
            if (!incoming.length) return;

            var currentCount = document.querySelectorAll('.existing-photo-item').length;
            var selectedCount = window.selectedPortfolioPhotos.filter(function(f) { return f; }).length;
            var maxAllowed = 5 - currentCount - selectedCount;

            if (incoming.length > maxAllowed) {
                alert('Нельзя добавить ' + incoming.length + ' фото. Доступно только ' + Math.max(maxAllowed, 0) + ' (лимит 5).');
                if (maxAllowed > 0) {
                    incoming = incoming.slice(0, maxAllowed);
                } else {
                    window.syncPortfolioPhotosToInput(); // восстанавливаем прежний набор
                    return;
                }
            }

            // ДОБАВЛЯЕМ новые файлы к уже выбранным (не заменяем)
            incoming.forEach(function(file) {
                window.selectedPortfolioPhotos.push(file);
            });

            window.syncPortfolioPhotosToInput();
            window.renderPortfolioPreviews();
        });
    }

    updatePlaceholderVisibility();
});

// Функция скрытия/показа квадрата с камерой и кнопки «+»
function getAddPhotoButton() {
    // Восстанавливаем кнопку, если она была удалена вместе с очисткой контейнера превью
    var addBtn = document.getElementById('portfolioAddPhotoBtn');
    if (!addBtn) {
        addBtn = document.createElement('div');
        addBtn.className = 'portfolio-add-photo-placeholder';
        addBtn.id = 'portfolioAddPhotoBtn';
        addBtn.title = 'Добавить фото';
        addBtn.innerHTML = '<span class="plus-icon">+</span>';
        addBtn.addEventListener('click', function() {
            document.getElementById('id_images').click();
        });
    }
    return addBtn;
}

function updatePlaceholderVisibility() {
    var placeholder = document.getElementById('photoUploadPlaceholder');
    var photoInput = document.getElementById('id_images');
    var existingGrid = document.querySelector('.existing-photos-grid');
    var previewContainer = document.getElementById('photoPreview');

    var newFilesCount = (photoInput && photoInput.files) ? photoInput.files.length : 0;
    var existingPhotosCount = document.querySelectorAll('.existing-photo-item').length;
    var previewCount = previewContainer ? previewContainer.querySelectorAll('.photo-preview-item').length : 0;
    var totalPhotos = newFilesCount + existingPhotosCount;

    // Камера видна только пока фото нет совсем
    if (placeholder) {
        placeholder.style.display = totalPhotos > 0 ? 'none' : 'flex';
    }

    // Кнопка «+» — если есть хотя бы 1 фото (существующее или добавленное)
    if (totalPhotos > 0) {
        var addBtn = getAddPhotoButton();
        // Перемещаем кнопку так, чтобы она стояла справа от последнего фото
        if (previewContainer && previewCount > 0) {
            previewContainer.appendChild(addBtn);
        } else if (existingGrid) {
            existingGrid.appendChild(addBtn);
        }
        addBtn.style.display = 'flex';
    } else {
        var addBtn = document.getElementById('portfolioAddPhotoBtn');
        if (addBtn) addBtn.style.display = 'none';
    }
}

// Удаление выбранного preview (нового) фото — из накопленного массива
function removePreview(btn) {
    var index = parseInt(btn.getAttribute('data-index'), 10);
    var photoInput = document.getElementById('id_images');

    // Помечаем файл удалённым в накопленном массиве
    if (window.selectedPortfolioPhotos && window.selectedPortfolioPhotos[index]) {
        window.selectedPortfolioPhotos[index] = null;
    }

    // Синхронизируем input file с массивом
    if (photoInput) {
        var dt = new DataTransfer();
        window.selectedPortfolioPhotos.forEach(function(file) {
            if (file) dt.items.add(file);
        });
        photoInput.files = dt.files;
    }

    // Перерисовываем превью
    if (typeof renderPortfolioPreviews === 'function') {
        renderPortfolioPreviews();
    } else {
        var item = btn.closest('.photo-preview-item');
        if (item) item.remove();
    }

    setTimeout(updatePlaceholderVisibility, 50);
}

// Получение CSRF-токена из cookie
function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Отложенное удаление ранее сохранённых фото:
// фото скрывается и помечается в deleted_image_ids, реально удалится после нажатия «Сохранить»
function markPhotoForDelete(btn) {
    var photoItem = btn.closest('.existing-photo-item');
    if (!photoItem) return;

    var imageId = photoItem.dataset.imageId;
    if (imageId) {
        var deletedInput = document.getElementById('deleted_image_ids');
        if (deletedInput) {
            var ids = deletedInput.value.split(',').filter(function(v) { return v && v !== imageId; });
            ids.push(imageId);
            deletedInput.value = ids.join(',');
        }
    }

    photoItem.remove();
    updatePlaceholderVisibility();
}
