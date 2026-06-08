// Функция для инициализации обработчиков медиафайлов
function initMediaHandlers() {
// Обработчики для кнопок удаления медиафайлов
    document.querySelectorAll('.remove-media-btn').forEach(button => {
        button.addEventListener('click', function() {
            const mediaId = this.getAttribute('data-media-id');
            const mediaType = this.getAttribute('data-media-type');
            const mediaContainer = this.closest('.media-preview');

            // Если это новый файл, который ещё не загружен на сервер, просто удаляем превью
            if (mediaId === 'new') {
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
                url = `/partner/remove_event_program_file/${mediaId}/`;
            } else if (mediaType === 'video_url') {
                url = `/partner/remove_event_video/${mediaId}/`;
            } else if (mediaType === 'image') {
                // Для дополнительных изображений используем другой URL
                const imageId = this.getAttribute('data-image-id');
                if (imageId) {
                    url = `/partner/remove_event_image/${imageId}/`;
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
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Ошибка при удалении файла');
                }
            })
            .then(data => {
                if (data.status === 'success') {
                    // Удаляем контейнер с превью
                    mediaContainer.remove();
                    // Обновляем скрытое поле, чтобы удалить ссылку на файл
                    const hiddenInput = document.querySelector(`#id_${mediaType}`);
                    if (hiddenInput) {
                        hiddenInput.value = '';
                    }
                } else {
                    alert('Ошибка при удалении файла: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
                alert('Ошибка при удалении файла: ' + error.message);
            });
        });
    });
    
    // Обработчики для кнопок загрузки новых файлов
    document.querySelectorAll('.custom-media-upload-btn').forEach(button => {
        button.addEventListener('click', function() {
            const mediaType = this.getAttribute('data-media-type');
            const fileInput = document.querySelector(`#id_${mediaType}`);
            fileInput.click();
        });
    });
    
    // Обработчики для изменения файлов
    document.querySelectorAll('.custom-media-input').forEach(input => {
        input.addEventListener('change', function() {
            const mediaType = this.getAttribute('data-media-type');
            const previewContainer = document.querySelector(`#${mediaType}-preview-container`);
            
            // Показываем имя выбранного файла
            if (this.files && this.files[0]) {
                const fileName = this.files[0].name;
                if (previewContainer) {
                    previewContainer.innerHTML = `
                        <div class="media-preview">
                            <span>${fileName}</span>
                            <button type="button" class="btn btn-danger btn-sm remove-media-btn" data-media-type="${mediaType}" data-media-id="new">
                                ×
                            </button>
                        </div>
                    `;
                    // Добавляем обработчик для новой кнопки удаления
                    initMediaHandlers();
                }
            }
        });
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initMediaHandlers();
});