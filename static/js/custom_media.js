// Функция для проверки длительности видео
async function checkVideoDuration(file) {
    return new Promise((resolve) => {
        const video = document.createElement('video');
        video.preload = 'metadata';
        const videoUrl = URL.createObjectURL(file);
        video.src = videoUrl;

        video.onloadedmetadata = function() {
            // Удаляем объект URL после загрузки метаданных
            URL.revokeObjectURL(videoUrl);

            // Длительность видео в секундах
            const duration = video.duration;
            // Максимальная длительность - 5 минут (300 секунд)
            const maxDuration = 310;

            if (duration > maxDuration) {
                resolve(false);
            } else {
                resolve(true);
            }
        };

        video.onerror = function() {
            console.error('Ошибка при загрузке метаданных видео');
            // Удаляем объект URL в случае ошибки
            URL.revokeObjectURL(videoUrl);
            // Если не удалось проверить длительность, разрешаем загрузку
            resolve(true);
        };
    });
}

// Флаг для отслеживания инициализации обработчиков
let mediaHandlersInitialized = false;

// Функция для инициализации обработчиков медиафайлов
function initMediaHandlers() {
    // Если обработчики уже инициализированы, выходим
    if (mediaHandlersInitialized) {
        return;
    }

    // Устанавливаем флаг, что обработчики инициализированы
    mediaHandlersInitialized = true;

    // Обработчики для кнопок удаления медиафайлов
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('remove-media-btn')) {
            const button = e.target;
            const mediaId = button.getAttribute('data-media-id');
            const eventId = button.getAttribute('data-media-id');
            const mediaType = button.getAttribute('data-media-type');
            const mediaContainer = button.closest('.media-preview');

            console.log('Удаление медиа:', { mediaId, eventId, mediaType });

            // Если это новый файл, который ещё не загружен на сервер, просто удаляем превью
            if (mediaId === 'new' || !eventId) {
                mediaContainer.remove();
                const hiddenInput = document.querySelector(`#id_${mediaType}`);
                if (hiddenInput) {
                    hiddenInput.value = '';
                }
                return;
            }

            // Удаление через AJAX
            let url = '';
            if (mediaType === 'program_file') {
                url = `/partner/remove_media/program_file/${eventId}/`;
            } else if (mediaType === 'video_url') {
                url = `/partner/remove_media/video_url/${eventId}/`;
            } else if (mediaType === 'image') {
                // Для дополнительных изображений используем другой URL
                const imageId = button.getAttribute('data-image-id');
                if (imageId) {
                    url = `/partner/remove_event_image/${imageId}/`;
                } else {
                    url = `/partner/remove_media/image/${eventId}/`;
                }
            }

            if (!url) {
                console.error('Не удалось определить URL для удаления');
                return;
            }

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: new URLSearchParams({
                    'csrfmiddlewaretoken': document.querySelector('[name=csrfmiddlewaretoken]').value
                })
            })
            .then(response => {
                console.log('Ответ сервера:', response.status, response.statusText);
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Ошибка при удалении файла: HTTP ' + response.status);
                }
            })
            .then(data => {
                console.log('Данные от сервера:', data);
                if (data.status === 'success') {
                    // Удаляем контейнер с превью
                    mediaContainer.remove();
                    // Обновляем скрытое поле, чтобы удалить ссылку на файл
                    const hiddenInput = document.querySelector(`#id_${mediaType}`);
                    if (hiddenInput) {
                        hiddenInput.value = '';
                    }
                    console.log('Медиа успешно удалено:', mediaType);
                } else {
                    showToast('Ошибка при удалении файла: ' + data.message, true);
                }
            })
            .catch(error => {
                console.error('Ошибка при удалении медиа:', error);
                showToast('Ошибка при удалении файла: ' + error.message, true);
            });
        }
    });

    // Обработчики для кнопок загрузки новых файлов
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('custom-media-upload-btn')) {
            const button = e.target;
            const mediaType = button.getAttribute('data-media-type');
            const fileInput = document.querySelector(`#id_${mediaType}`);
            if (fileInput) {
                fileInput.click();
            }
        }
    });

    // Обработчики для изменения файлов
    document.addEventListener('change', async function(e) {
        if (e.target && e.target.classList.contains('custom-media-input')) {
            const input = e.target;
            const mediaType = input.getAttribute('data-media-type');
            const previewContainer = document.querySelector(`#${mediaType}-preview-container`);

            // Очищаем предыдущие ошибки
            const errorContainer = document.querySelector(`#${mediaType}-error-container`);
            if (errorContainer) {
                errorContainer.innerHTML = '';
            }

            // Валидация файла перед показом превью
            if (input.files && input.files[0]) {
                const file = input.files[0];
                let isValid = true;
                let errorMessage = '';

                // Валидация в зависимости от типа медиа
                if (mediaType === 'video_url') {
                    // Видео: разрешены только MP4, MOV, AVI
                    const validVideoTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo'];
                    const validVideoExtensions = ['.mp4', '.mov', '.avi'];
                    const fileName = file.name.toLowerCase();

                    const isValidType = validVideoTypes.includes(file.type);
                    const isValidExtension = validVideoExtensions.some(ext => fileName.endsWith(ext));

                    if (!isValidType && !isValidExtension) {
                        isValid = false;
                        errorMessage = 'Неверный формат видео. Разрешены только файлы MP4, MOV, AVI';
                    } else {
                        // Добавляем проверку длительности видео
                        isValid = await checkVideoDuration(file);
                        if (!isValid) {
                            errorMessage = 'Длительность видео превышает 5 минут. Пожалуйста, загрузите видео не длиннее 5 минут.';
                        }
                    }
                }
                else if (mediaType === 'program_file') {
                    // Программа: разрешен только PDF
                    const fileName = file.name.toLowerCase();
                    if (!fileName.endsWith('.pdf')) {
                        isValid = false;
                        errorMessage = 'Неверный формат файла. Разрешены только PDF файлы';
                    }
                }
                else if (mediaType === 'image' || mediaType === 'images') {
                    // Изображения: разрешены только изображения
                    const validImageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
                    const validImageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];
                    const fileName = file.name.toLowerCase();

                    const isValidType = validImageTypes.includes(file.type);
                    const isValidExtension = validImageExtensions.some(ext => fileName.endsWith(ext));

                    if (!isValidType && !isValidExtension) {
                        isValid = false;
                        errorMessage = 'Неверный формат изображения. Разрешены только JPG, PNG, GIF, WEBP';
                    }
                }

                // Если файл не прошел валидацию
                if (!isValid) {
                    showToast(errorMessage, true);
                    input.value = ''; // Очищаем поле

                    // Показываем ошибку под полем
                    if (errorContainer) {
                        errorContainer.innerHTML = `
                            <div class="alert alert-danger mt-1 p-2">
                                ${errorMessage}
                            </div>
                        `;
                    }
                    return;
                }

                // Если валидация пройдена, показываем превью
                if (previewContainer) {
                    if (mediaType === 'image') {
                        // Для основного изображения показываем превью картинки
                        const reader = new FileReader();
                        reader.onload = function(e) {
                            previewContainer.innerHTML = `
                                <div class="media-preview position-relative">
                                    <img src="${e.target.result}" alt="Preview" style="max-width: 200px; max-height: 200px; border-radius: 4px;" class="mr-2">
                                    <button type="button" class="btn btn-danger btn-sm remove-media-btn" data-media-type="${mediaType}" data-media-id="new">
                                        ×
                                    </button>
                                </div>
                            `;
                        };
                        reader.readAsDataURL(file);
                    }
                    else if (mediaType === 'images') {
                        // Для дополнительных изображений показываем превью картинок
                        const files = input.files;
                        previewContainer.innerHTML = ''; // Очищаем предыдущие превью

                        for (let i = 0; i < files.length; i++) {
                            const file = files[i];
                            const reader = new FileReader();

                            reader.onload = function(e) {
                                const previewDiv = document.createElement('div');
                                previewDiv.className = 'media-preview position-relative';
                                previewDiv.dataset.preview = 'true';

                                const img = document.createElement('img');
                                img.src = e.target.result;
                                img.style.maxWidth = '150px';
                                img.style.maxHeight = '150px';
                                img.style.borderRadius = '4px';

                                // Кнопка удаления для превью
                                const removeBtn = document.createElement('button');
                                removeBtn.type = 'button';
                                removeBtn.className = 'btn btn-danger btn-sm position-absolute top-0 end-0 m-1';
                                removeBtn.style.width = '24px';
                                removeBtn.style.height = '24px';
                                removeBtn.style.padding = '0';
                                removeBtn.style.lineHeight = '1';
                                removeBtn.textContent = '×';
                                removeBtn.dataset.preview = 'true';
                                removeBtn.dataset.mediaType = mediaType;
                                removeBtn.dataset.mediaId = 'new';

                                previewDiv.appendChild(img);
                                previewDiv.appendChild(removeBtn);
                                previewContainer.appendChild(previewDiv);
                            };
                            reader.readAsDataURL(file);
                        }
                    }
                    else if (mediaType === 'video_url') {
                        // Для видео показываем превью с видео-плеером
                        const reader = new FileReader();
                        reader.onload = function(e) {
                            previewContainer.innerHTML = `
                                <div class="media-preview">
                                    <video controls style="max-width: 300px;" class="mr-2">
                                        <source src="${e.target.result}" type="${file.type}">
                                        Ваш браузер не поддерживает видео.
                                    </video>
                                    <button type="button" class="btn btn-danger btn-sm remove-media-btn" data-media-type="${mediaType}" data-media-id="new">
                                        ×
                                    </button>
                                </div>
                            `;
                        };
                        reader.readAsDataURL(file);
                    }
                    else if (mediaType === 'program_file') {
                        // Для PDF показываем просто имя файла
                        previewContainer.innerHTML = `
                            <div class="media-preview">
                                <span>${file.name}</span>
                                <button type="button" class="btn btn-danger btn-sm remove-media-btn" data-media-type="${mediaType}" data-media-id="new">
                                    ×
                                </button>
                            </div>
                        `;
                    }
                }
            } else {
                // Если файл не выбран, очищаем превью
                if (previewContainer) {
                    previewContainer.innerHTML = '';
                }
            }
        }
    });
}

// Функция для проверки валидности файлов перед отправкой формы
function validateMediaFilesBeforeSubmit() {
    // Проверяем все поля с медиафайлами
    const mediaInputs = document.querySelectorAll('.custom-media-input');
    let hasInvalidFiles = false;

    mediaInputs.forEach(input => {
        if (input.files && input.files.length > 0) {
            const mediaType = input.getAttribute('data-media-type');
            const files = mediaType === 'images' ? input.files : [input.files[0]];

            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                let isValid = true;
                let errorMessage = '';

                // Валидация в зависимости от типа медиа
                if (mediaType === 'video_url') {
                    // Видео: разрешены только MP4, MOV, AVI
                    const validVideoTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo'];
                    const validVideoExtensions = ['.mp4', '.mov', '.avi'];
                    const fileName = file.name.toLowerCase();

                    const isValidType = validVideoTypes.includes(file.type);
                    const isValidExtension = validVideoExtensions.some(ext => fileName.endsWith(ext));

                    if (!isValidType && !isValidExtension) {
                        isValid = false;
                        errorMessage = 'Неверный формат видео. Разрешены только файлы MP4, MOV, AVI';
                    }
                }
                else if (mediaType === 'program_file') {
                    // Программа: разрешен только PDF
                    const fileName = file.name.toLowerCase();
                    if (!fileName.endsWith('.pdf')) {
                        isValid = false;
                        errorMessage = 'Неверный формат файла. Разрешены только PDF файлы';
                    }
                }
                else if (mediaType === 'image' || mediaType === 'images') {
                    // Изображения: разрешены только изображения
                    const validImageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
                    const validImageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];
                    const fileName = file.name.toLowerCase();

                    const isValidType = validImageTypes.includes(file.type);
                    const isValidExtension = validImageExtensions.some(ext => fileName.endsWith(ext));

                    if (!isValidType && !isValidExtension) {
                        isValid = false;
                        errorMessage = 'Неверный формат изображения. Разрешены только JPG, PNG, GIF, WEBP';
                    }
                }

                if (!isValid) {
                    hasInvalidFiles = true;
                    showToast(errorMessage, true);

                    // Показываем ошибку под полем
                    const errorContainer = document.querySelector(`#${mediaType}-error-container`);
                    if (errorContainer) {
                        errorContainer.innerHTML = `
                            <div class="alert alert-danger mt-1 p-2">
                                ${errorMessage}
                            </div>
                        `;
                    }
                }
            }
        }
    });

    return !hasInvalidFiles;
}

// Функция для отображения toast-уведомлений
function showToast(message, isError = true) {
    const toastContainer = document.getElementById('toastContainer');

    if (!toastContainer) {
        console.error('Toast container not found');
        return;
    }

    const toastElement = document.createElement('div');
    toastElement.className = `toast align-items-center text-white ${isError ? 'bg-danger' : 'bg-success'}`;
    toastElement.setAttribute('role', 'alert');
    toastElement.setAttribute('aria-live', 'assertive');
    toastElement.setAttribute('aria-atomic', 'true');

    const toastBody = document.createElement('div');
    toastBody.className = 'd-flex';

    const toastMessage = document.createElement('div');
    toastMessage.className = 'toast-body';
    toastMessage.textContent = message;

    const toastClose = document.createElement('button');
    toastClose.type = 'button';
    toastClose.className = 'btn-close btn-close-white me-2 m-auto';
    toastClose.setAttribute('data-bs-dismiss', 'toast');
    toastClose.setAttribute('aria-label', 'Close');

    toastBody.appendChild(toastMessage);
    toastBody.appendChild(toastClose);
    toastElement.appendChild(toastBody);

    toastContainer.appendChild(toastElement);

    // Инициализируем и показываем toast
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 5000
    });
    toast.show();

    // Удаляем toast после закрытия
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initMediaHandlers();

    // Добавляем валидацию перед отправкой формы
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            if (!validateMediaFilesBeforeSubmit()) {
                e.preventDefault(); // Блокируем отправку формы
                return false;
            }
        });
    }
});