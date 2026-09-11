// === EVENT FORM EXTRA ===

// Dropdown handler for payment modal
document.addEventListener('DOMContentLoaded', function() {
    // Payment dropdown in buy package modal
    var paymentDisplay = document.getElementById('paymentDisplay');
    var paymentDropdown = document.getElementById('paymentDropdown');
    var paymentInput = document.getElementById('payment-method');
    
    if (paymentDisplay && paymentDropdown) {
        paymentDisplay.addEventListener('click', function() {
            paymentDropdown.classList.toggle('show');
        });
        
        var options = paymentDropdown.querySelectorAll('.dropdown-option');
        options.forEach(function(option) {
            option.addEventListener('click', function() {
                paymentDisplay.value = this.textContent.trim();
                paymentInput.value = this.getAttribute('data-value');
                paymentDropdown.classList.remove('show');
                
                // Update active state
                options.forEach(function(opt) { opt.classList.remove('active'); });
                this.classList.add('active');
                
                // Show/hide admin email field based on payment method
                var invoiceField = document.getElementById('invoice-admin-field');
                var adminEmailInput = document.getElementById('admin-email');
                if (invoiceField) {
                    var isInvoice = this.getAttribute('data-value') === 'invoice';
                    invoiceField.style.display = isInvoice ? 'block' : 'none';
                    if (adminEmailInput) {
                        adminEmailInput.required = isInvoice;
                    }
                }
            });
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.dropdown-container')) {
                paymentDropdown.classList.remove('show');
            }
        });
    }
});

// ============================================================
// TOGGLE SWITCHES — стили через CSS :checked
// ============================================================
function initToggleSwitch(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    // Обработка disabled
    if (input.disabled) {
        input.closest('.toggle-switch').style.opacity = '0.5';
        input.closest('.toggle-switch').style.pointerEvents = 'none';
    }
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
function showToast(message, isError = true) {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;

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

    const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 5000 });
    toast.show();
    toastElement.addEventListener('hidden.bs.toast', function() { toastElement.remove(); });
}

// ============================================================
// PHOTO GALLERY
// ============================================================
const TICKET_PALETTE = ['#4A7CF7','#FF6B6B','#51CF66','#FFD43B','rgba(255, 131, 72, 1)','#845EF7','#20C997','#F06595','#339AF0','#F783AC'];
let photoMaxCount = window.EVENT_FORM_DATA?.photoMaxCount ?? 10;

// Адаптивная сетка галереи: колонок = min(лимит фото + кнопка, 6),
// чтобы максимум фото + кнопка добавления занимали ровно одну строку без пустот
(function initGalleryColumns() {
    const gallery = document.getElementById('photo-gallery');
    if (gallery) {
        const cols = Math.min(photoMaxCount + 1, 6);
        gallery.style.setProperty('--gallery-cols', cols);
    }
})();

// Массив для хранения новых выбранных файлов фото
let newPhotoFiles = [];

function updatePhotoGalleryState() {
    const gallery = document.getElementById('photo-gallery');
    const items = gallery ? gallery.querySelectorAll('.photo-gallery-item') : [];
    const addPlaceholder = gallery ? gallery.querySelector('.add-photo-placeholder') : null;
    const uploadPlaceholder = document.getElementById('photo-upload-placeholder');
    const container = document.getElementById('photo-upload-container');
    
    // Показываем серый квадрат с плюсом ТОЛЬКО если есть хотя бы 1 фото
    if (addPlaceholder) {
        addPlaceholder.style.display = items.length > 0 ? 'flex' : 'none';
    }
    
    // Зона загрузки: показываем если нет фото (как у видео)
    if (uploadPlaceholder) {
        uploadPlaceholder.style.display = items.length === 0 ? 'flex' : 'none';
    }
    
    // Управляем классами на контейнере и галерее
    if (container) {
        if (items.length > 0) {
            container.classList.remove('has-no-photos');
            container.classList.add('has-photos');
        } else {
            container.classList.add('has-no-photos');
            container.classList.remove('has-photos');
        }
    }
    if (gallery) {
        if (items.length > 0) {
            gallery.classList.add('has-photos');
        } else {
            gallery.classList.remove('has-photos');
        }
    }
}

// Синхронизация новых фото-файлов с input file
function syncPhotoFilesToInput() {
    const imagesInput = document.getElementById('id_images');
    if (!imagesInput) return;
    const dt = new DataTransfer();
    newPhotoFiles.forEach(function(file) {
        if (file) dt.items.add(file);
    });
    imagesInput.files = dt.files;
}

function setPrimaryPhoto(item) {
    const gallery = document.getElementById('photo-gallery');
    if (!gallery) return;
    
    // Снимаем is-primary со всех фото и убираем подписи
    gallery.querySelectorAll('.photo-gallery-item').forEach(el => {
        el.classList.remove('is-primary');
        const caption = el.querySelector('.photo-gallery-caption');
        if (caption) caption.remove();
    });
    
    // Ставим is-primary на выбранное и добавляем подпись под фото
    item.classList.add('is-primary');
    const caption = document.createElement('div');
    caption.className = 'photo-gallery-caption';
    caption.textContent = 'ОСНОВНОЕ ФОТО';
    item.appendChild(caption);

    // Определяем ID фото (существующее или индекс нового файла)
    const imageId = item.dataset.imageId || '';
    const isNew = item.dataset.isNew === 'true';
    const fileIndex = item.dataset.fileIndex || '';
    
    // Записываем ID в скрытое поле для существующих фото
    const hiddenField = document.getElementById('primary_image_id');
    if (hiddenField) {
        hiddenField.value = imageId;
    }
    
    // Записываем индекс нового файла, если это загруженное фото
    const newPhotoField = document.getElementById('primary_new_photo_file_index');
    if (newPhotoField) {
        newPhotoField.value = isNew ? fileIndex : '';
    }
}

function addNewPhotoPreview(file) {
    let gallery = document.getElementById('photo-gallery');
    
    // Если галереи нет — создаём её
    if (!gallery) {
        const container = document.getElementById('photo-upload-container');
        gallery = document.createElement('div');
        gallery.className = 'photo-gallery';
        gallery.id = 'photo-gallery';
        gallery.style.setProperty('--gallery-cols', Math.min(photoMaxCount + 1, 6));
        const placeholder = document.getElementById('photo-upload-placeholder');
        if (placeholder) placeholder.style.display = 'none';
        container.insertBefore(gallery, placeholder);
        
        // Добавляем placeholder для добавления фото в новую галерею
        const addPlaceholder = document.createElement('div');
        addPlaceholder.className = 'add-photo-placeholder';
        addPlaceholder.id = 'add-photo-placeholder';
        addPlaceholder.title = 'Добавить фото';
        addPlaceholder.innerHTML = '<span class="plus-icon">+</span>';
        gallery.appendChild(addPlaceholder);
    }

    const fileIndex = newPhotoFiles.length;
    const reader = new FileReader();
    reader.onload = function(e) {
        const item = document.createElement('div');
        const existingItems = gallery.querySelectorAll('.photo-gallery-item');
        const isOnlyPhoto = existingItems.length === 0;
        item.className = 'photo-gallery-item' + (isOnlyPhoto ? ' is-primary' : '');
        item.dataset.isNew = 'true';
        // Сохраняем индекс в массиве newPhotoFiles
        item.dataset.fileIndex = fileIndex;
        // Для новых фото imageId пустой (ID ещё нет на сервере)
        item.dataset.imageId = '';

        const img = document.createElement('img');
        img.src = e.target.result;
        img.alt = 'Новое фото';
        item.appendChild(img);

        // Кнопка удаления — корзина
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'remove-btn';
        removeBtn.title = 'Удалить';
        removeBtn.innerHTML = '<img src="/media/icon/trash.svg" alt="Удалить" class="card-check-box">';
        removeBtn.addEventListener('click', function(ev) {
            ev.stopPropagation();
            // Удаляем файл из массива (помечаем как null)
            newPhotoFiles[parseInt(item.dataset.fileIndex, 10)] = null;
            item.remove();
            // Пересобираем files в input
            syncPhotoFilesToInput();
            updatePhotoGalleryState();
        });
        item.appendChild(removeBtn);

        // Клик по фото = сделать основным
        item.addEventListener('click', function() {
            setPrimaryPhoto(item);
        });

        // Вставляем перед add-photo-placeholder
        const existingPlaceholder = gallery.querySelector('.add-photo-placeholder');
        if (existingPlaceholder) {
            gallery.insertBefore(item, existingPlaceholder);
        } else {
            gallery.appendChild(item);
        }
        updatePhotoGalleryState();
    };
    reader.readAsDataURL(file);
}

function removeExistingPhoto(imageId, item) {
    if (!imageId) {
        // Это Event.image (старое поле) — помечаем к удалению, удалится после сохранения формы
        const flag = document.getElementById('delete_main_image');
        if (flag) flag.value = '1';
        item.remove();
        updatePhotoGalleryState();
        return;
    }
    // Отложенное удаление: фото скрывается и помечается в deleted_image_ids,
    // реально удаляется на сервере только после нажатия «Отправить на модерацию»
    const deletedInput = document.getElementById('deleted_image_ids');
    if (deletedInput) {
        const ids = deletedInput.value.split(',').filter(function(v) { return v && v !== imageId; });
        ids.push(imageId);
        deletedInput.value = ids.join(',');
    }
    // Если удалили основное фото — сбрасываем выбор, чтобы сервер назначил новое из оставшихся
    const primaryField = document.getElementById('primary_image_id');
    if (primaryField && primaryField.value === imageId) {
        primaryField.value = '';
    }
    item.remove();
    updatePhotoGalleryState();
}

// ============================================================
// SOLD COUNTS — данные о проданных билетах (только для change request)
// ============================================================
const ticketSoldCounts = window.EVENT_FORM_DATA?.ticketSoldCounts || {};

// TICKET TABLE
// ============================================================
function getRandomColor() {
    return TICKET_PALETTE[Math.floor(Math.random() * TICKET_PALETTE.length)];
}

function addTicketRow() {
    const tbody = document.getElementById('ticket-tbody');
    const rows = tbody.querySelectorAll('tr');

    // Ограничение: не больше 3 типов билетов
    if (rows.length >= 3) {
        alert('Максимум 3 типа билетов для вашего пакета.');
        return;
    }

    const tr = document.createElement('tr');

    const color = getRandomColor();

    tr.innerHTML =
        '<td class="color-cell"><div class="ticket-color-preview" style="background:' + color + ';"></div></td>' +
        '<td><input type="text" name="ticket_name[]" class="form-control" required></td>' +
        '<td><input type="text" name="ticket_price[]" class="form-control" required></td>' +
        '<td><input type="number" name="ticket_quantity[]" min="1" class="form-control" required></td>' +
        '<td><input type="text" name="ticket_description[]" class="form-control" maxlength="100" required></td>' +
        '<td class="min-qty-cell"><input type="number" name="ticket_min_quantity[]" value="1" min="1" class="form-control min-qty-input"></td>' +
        '<input type="checkbox" name="ticket_is_per_person[]" class="per-person-hidden" value="on" style="display:none;">' +
        '<td class="actions-cell"><button type="button" class="remove-ticket-btn">✕</button><button type="button" class="remove-ticket-btn-mobile">Удалить</button></td>';

    tbody.appendChild(tr);
    
    // Принудительно обновляем состояние чекбокса для новой строки
    const minInput = tr.querySelector('.min-qty-input');
    const perPersonCb = tr.querySelector('.per-person-hidden');
    if (minInput && perPersonCb) {
        perPersonCb.checked = (parseInt(minInput.value, 10) > 1);
    }
}

// Ограничитель: хотя бы один заполненный билет обязателен
document.querySelector('form[method="post"][enctype="multipart/form-data"]').addEventListener('submit', function(e) {
    const tbody = document.getElementById('ticket-tbody');
    if (!tbody) return;
    const rows = tbody.querySelectorAll('tr');
    let hasValidTicket = false;
    rows.forEach(function(tr) {
        const name = tr.querySelector('input[name="ticket_name[]"]');
        const price = tr.querySelector('input[name="ticket_price[]"]');
        const qty = tr.querySelector('input[name="ticket_quantity[]"]');
        if (name && price && qty && name.value.trim() && price.value.trim() && qty.value && parseInt(qty.value, 10) > 0) {
            hasValidTicket = true;
        }
    });
    if (!hasValidTicket) {
        e.preventDefault();
        if (typeof showToast === 'function') {
            showToast('Добавьте хотя бы один билет — мероприятие не может существовать без билетов.', true);
        } else {
            alert('Добавьте хотя бы один билет — мероприятие не может существовать без билетов.');
        }
        return;
    }

    // Описание обязательно для каждого заполненного билета
    let missingDescription = false;
    rows.forEach(function(tr) {
        const name = tr.querySelector('input[name="ticket_name[]"]');
        const price = tr.querySelector('input[name="ticket_price[]"]');
        const qty = tr.querySelector('input[name="ticket_quantity[]"]');
        const desc = tr.querySelector('input[name="ticket_description[]"]');
        const isFilledRow = name && price && qty && name.value.trim() && price.value.trim() && qty.value && parseInt(qty.value, 10) > 0;
        if (isFilledRow && desc && !desc.value.trim()) {
            missingDescription = true;
            desc.classList.add('is-invalid');
        }
    });
    if (missingDescription) {
        e.preventDefault();
        if (typeof showToast === 'function') {
            showToast('Заполните описание для каждого билета — это обязательное поле.', true);
        } else {
            alert('Заполните описание для каждого билета — это обязательное поле.');
        }
    }
});

// Ограничение на сервере: максимум 3 типа билетов — проверяем при submit
document.querySelector('form[method="post"][enctype="multipart/form-data"]').addEventListener('submit', function(e) {
    const tbody = document.getElementById('ticket-tbody');
    if (!tbody) return;
    const rows = tbody.querySelectorAll('tr');
    if (rows.length > 3) {
        e.preventDefault();
        if (typeof showToast === 'function') {
            showToast('Максимум 3 типа билетов для вашего пакета.', true);
        } else {
            alert('Максимум 3 типа билетов для вашего пакета.');
        }
    }
});

// ============================================================
// TAGS
// ============================================================
function initTags() {
    const searchInput = document.getElementById('tag-search');
    const suggestionsContainer = document.getElementById('tags-suggestions');
    const maxTags = 5;
    
    // Создаём контейнер для hidden inputs
    const hiddenContainer = document.getElementById('tags-hidden-container');
    if (hiddenContainer) hiddenContainer.innerHTML = '';

    // Фильтр по поиску
    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase();
        suggestionsContainer.querySelectorAll('.tag-suggestion-chip').forEach(function(chip) {
            const text = chip.textContent.toLowerCase();
            chip.style.display = text.includes(query) ? '' : 'none';
        });
    });

    // Клик по чипсу — переключение selected
    suggestionsContainer.querySelectorAll('.tag-suggestion-chip').forEach(function(chip) {
        chip.addEventListener('click', function(e) {
            e.stopPropagation();
            const tagId = this.dataset.tagId;
            const isSelected = this.classList.contains('selected');

            // Если уже выбран — снимаем (toggle)
            if (isSelected) {
                this.classList.remove('selected');
                updateTagsInputs();
                return;
            }

            // Проверяем лимит
            const selectedCount = document.querySelectorAll('.tag-suggestion-chip.selected').length;
            if (selectedCount >= maxTags) {
                alert('Можно выбрать не больше ' + maxTags + ' тегов.');
                return;
            }

            // Добавляем selected
            this.classList.add('selected');
            updateTagsInputs();
        });
    });

    // Клик по заголовку группы — раскрыть/закрыть
    suggestionsContainer.querySelectorAll('.tag-group-header').forEach(function(header) {
        header.addEventListener('click', function() {
            const group = this.closest('.tag-group');
            group.classList.toggle('open');
        });
    });

    function updateTagsInputs() {
        if (!hiddenContainer) return;
        hiddenContainer.innerHTML = '';
        document.querySelectorAll('.tag-suggestion-chip.selected').forEach(function(chip) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'tags';
            input.value = chip.dataset.tagId;
            hiddenContainer.appendChild(input);
        });
    }

    // Инициализируем при загрузке
    updateTagsInputs();
}

// ============================================================
// DOMContentLoaded — инициализация
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    // Устанавливаем начальное состояние контейнера фото
    const photoContainer = document.getElementById('photo-upload-container');
    const photoGallery = document.getElementById('photo-gallery');
    if (photoContainer && photoGallery) {
        const hasPhotos = photoGallery.querySelectorAll('.photo-gallery-item').length > 0;
        if (!hasPhotos) {
            photoContainer.classList.add('has-no-photos');
        }
    } else if (photoContainer) {
        // Галереи нет — значит фото нет
        photoContainer.classList.add('has-no-photos');
    }
    
    // Toggles
     initToggleSwitch('id_allow_platform_requests');
     initToggleSwitch('id_allow_booking_without_payment');

     // Получаем минимальную дату/время из data-атрибута (серверное время + 24ч)
     const layout = document.querySelector('.partner-layout');
     const minDateTimeStr = layout ? layout.dataset.minDateTime : '';
     let minDateTime = minDateTimeStr ? new Date(minDateTimeStr) : null;

     // События формы — синхронизация hidden input date_time
     const eventFormDateInput = document.getElementById('eventFormDateInput');
     const formTimeHours = document.getElementById('formTimeHours');
     const formTimeMinutes = document.getElementById('formTimeMinutes');
     const idDateTime = document.getElementById('id_date_time');

     function syncEventFormDateTime() {
         if (!eventFormDateInput || !idDateTime) return;
         const dateVal = eventFormDateInput.value;
         if (!dateVal || dateVal === '') return;
         const parts = dateVal.split('.');
         if (parts.length !== 3) return;
         const day = parts[0].padStart(2, '0');
         const month = parts[1].padStart(2, '0');
         const year = parts[2];
         const hours = (formTimeHours && formTimeHours.value) ? String(parseInt(formTimeHours.value, 10)).padStart(2, '0') : '12';
         const minutes = (formTimeMinutes && formTimeMinutes.value) ? String(parseInt(formTimeMinutes.value, 10)).padStart(2, '0') : '00';
         idDateTime.value = `${year}-${month}-${day}T${hours}:${minutes}`;
     }

     // При изменении полей времени в календаре — обновляем hidden input
     if (formTimeHours) formTimeHours.addEventListener('input', syncEventFormDateTime);
     if (formTimeMinutes) formTimeMinutes.addEventListener('input', syncEventFormDateTime);

     // Блокировка времени: если выбрана дата равная minDateTime, время не может быть меньше
     function enforceMinTime() {
         if (!minDateTime || !eventFormDateInput || !idDateTime) return;
         const dateVal = eventFormDateInput.value;
         if (!dateVal) return;
         const parts = dateVal.split('.');
         if (parts.length !== 3) return;
         const day = parts[0].padStart(2, '0');
         const month = parts[1].padStart(2, '0');
         const year = parts[2];
         const selectedDate = new Date(`${year}-${month}-${day}T00:00:00`);
         const minDateOnly = new Date(minDateTime.getFullYear(), minDateTime.getMonth(), minDateTime.getDate());
         
         // Если выбрана та же дата, что и minDateTime — проверяем время
         if (selectedDate.getTime() === minDateOnly.getTime()) {
             const selectedH = parseInt(formTimeHours?.value || 0, 10);
             const selectedM = parseInt(formTimeMinutes?.value || 0, 10);
             const minH = minDateTime.getHours();
             const minM = minDateTime.getMinutes();
             
             if (selectedH < minH || (selectedH === minH && selectedM < minM)) {
                 // Устанавливаем минимальное время
                 formTimeHours.value = String(minH).padStart(2, '0');
                 formTimeMinutes.value = String(minM).padStart(2, '0');
                 syncEventFormDateTime();
             }
         }
     }

     if (formTimeHours) formTimeHours.addEventListener('change', enforceMinTime);
     if (formTimeMinutes) formTimeMinutes.addEventListener('change', enforceMinTime);

     // Tags
     initTags();

    // Photo gallery — click on placeholder to upload
    const photoPlaceholder = document.getElementById('photo-upload-placeholder');
    const imagesInput = document.getElementById('id_images');
    if (photoPlaceholder && imagesInput) {
        photoPlaceholder.addEventListener('click', function() {
            imagesInput.click();
        });
    }
    if (imagesInput) {
        imagesInput.addEventListener('change', function(e) {
            const files = Array.from(e.target.files);
            const gallery = document.getElementById('photo-gallery');
            const currentCount = gallery ? gallery.querySelectorAll('.photo-gallery-item').length : 0;
            const currentNewCount = newPhotoFiles.filter(f => f !== null).length;
            const remaining = photoMaxCount - currentCount - currentNewCount;
            if (files.length > remaining) {
                alert('Можно загрузить ещё не более ' + remaining + ' фото.');
            }
            let added = 0;
            for (let i = 0; i < files.length && added < remaining; i++) {
                const file = files[i];
                if (file) {
                    newPhotoFiles.push(file);
                    addNewPhotoPreview(file);
                    added++;
                }
            }
            // Записываем все новые файлы в input через DataTransfer
            syncPhotoFilesToInput();
        });
    }

    // Photo gallery — remove existing photos (объединённый селектор)
    document.querySelectorAll('.remove-gallery-photo, .remove-main-photo').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const item = this.closest('.photo-gallery-item');
            const imageId = this.dataset.imageId;
            removeExistingPhoto(imageId, item);
        });
    });

    // Photo gallery — click on item to set primary (delegation)
    document.getElementById('photo-upload-container')?.addEventListener('click', function(e) {
        const item = e.target.closest('.photo-gallery-item');
        if (item && !e.target.classList.contains('remove-btn') && !e.target.classList.contains('remove-btn-mobile')) {
            setPrimaryPhoto(item);
        }
    });

    updatePhotoGalleryState();

    // Инициализация имени файла программы (для уже загруженного файла)
    if (window.EVENT_FORM_DATA?.hasProgramFile) {
        (function() {
            var display = document.getElementById('program-file-display');
            var placeholder = document.getElementById('program-upload-placeholder');
            var container = document.getElementById('program-upload-container');
            var fileNameSpan = document.getElementById('program-file-name');
            if (display) {
                display.style.display = 'flex';
                var url = window.EVENT_FORM_DATA.programFileUrl;
                display.querySelectorAll('a').forEach(function(link) { link.href = url; });
            }
            if (placeholder) placeholder.style.display = 'none';
            if (container) {
                container.classList.remove('has-no-photos');
                container.classList.add('has-photos');
            }
            if (fileNameSpan) {
                var name = window.EVENT_FORM_DATA.programFileName || '';
                var base = name.replace(/.*[\/]/, '');
                var short = base.length > 40 ? base.substring(0, 37) + '...' : base;
                fileNameSpan.textContent = short;
            }
        })();
    } else {
        (function() {
            var container = document.getElementById('program-upload-container');
            if (container) {
                container.classList.add('has-no-photos');
            }
        })();
    }

    // Ticket table
    const addBtn = document.getElementById('addTicketRow');
    if (addBtn) {
        addBtn.addEventListener('click', function() {
            addTicketRow();
        });
    }

    // Remove ticket row (delegation)
    document.getElementById('ticket-tbody').addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-ticket-btn') || e.target.classList.contains('remove-ticket-btn-mobile')) {
            const tr = e.target.closest('tr');
            const ticketId = tr.dataset.ticketId;

            // Если это заявка на изменение и билет продан — блокируем удаление
            if (window.EVENT_FORM_DATA?.isChangeRequest && ticketId && ticketSoldCounts[ticketId] > 0) {
                const sold = ticketSoldCounts[ticketId];
                alert('Нельзя удалить этот билет — на него уже куплено ' + sold + ' ' + (sold === 1 ? 'билет' : (sold < 5 ? 'билета' : 'билетов')) + '. Билет останется без изменений.');
                return;
            }

            tr.remove();
        }
    });

    // Add photo placeholder click (delegation — внутри photo-upload-container)
    document.getElementById('photo-upload-container')?.addEventListener('click', function(e) {
        const placeholder = e.target.closest('.add-photo-placeholder');
        if (placeholder && imagesInput) {
            imagesInput.click();
        }
    });

    // Program file upload — переключение placeholder / отображение файла
    const programFileInput = document.getElementById('id_program_file');
    if (programFileInput) {
        programFileInput.addEventListener('change', function() {
            const file = this.files && this.files[0];
            const display = document.getElementById('program-file-display');
            const placeholder = document.getElementById('program-upload-placeholder');
            const container = document.getElementById('program-upload-container');
            const fileNameSpan = document.getElementById('program-file-name');
            // Выбран новый файл — он ещё не в БД, удаление будет только клиентским
            newProgramSelected = !!file;
            if (file) {
                // Краткое имя файла — только basename без расширения
                const name = file.name || '';
                const base = name.replace(/.*[\/]/, ''); // убираем путь
                const short = base.length > 40 ? base.substring(0, 37) + '...' : base;
                if (fileNameSpan) fileNameSpan.textContent = short;

                // Обновляем ссылки на скачивание (превью)
                const dummyUrl = URL.createObjectURL(file);
                const downloadLinks = display?.querySelectorAll('a');
                if (downloadLinks) {
                    downloadLinks.forEach(function(link) {
                        link.href = dummyUrl;
                    });
                }
                // Скрываем placeholder, показываем display
                if (placeholder) placeholder.style.display = 'none';
                if (display) display.style.display = 'flex';
                // Контейнер: есть файл
                if (container) {
                    container.classList.remove('has-no-photos');
                    container.classList.add('has-photos');
                }
            } else {
                // Файл снят — показываем placeholder
                if (display) display.style.display = 'none';
                if (placeholder) placeholder.style.display = 'flex';
                // Контейнер: нет файла
                if (container) {
                    container.classList.remove('has-photos');
                    container.classList.add('has-no-photos');
                }
            }
        });
    }

    // Video file upload — переключение placeholder / отображение видео
    const videoFileInput = document.getElementById('id_video_url');
    if (videoFileInput) {
        videoFileInput.addEventListener('change', function() {
            const file = this.files && this.files[0];
            const display = document.getElementById('video-file-display');
            const placeholder = document.getElementById('video-upload-placeholder');
            const container = document.getElementById('video-upload-container');
            const fileNameSpan = document.getElementById('video-file-name');
            // Выбран новый файл — он ещё не в БД, удаление будет только клиентским
            newVideoSelected = !!file;
            if (file) {
                const name = file.name || '';
                const base = name.replace(/.*[\/]/, '');
                const short = base.length > 40 ? base.substring(0, 37) + '...' : base;
                if (fileNameSpan) fileNameSpan.textContent = short;

                // Создаём URL для превью видео
                const videoEl = display?.querySelector('video');
                if (videoEl) {
                    // Удаляем старые <source> и создаём новый
                    while (videoEl.firstChild) videoEl.removeChild(videoEl.firstChild);
                    var source = document.createElement('source');
                    source.src = URL.createObjectURL(file);
                    source.type = 'video/mp4';
                    videoEl.appendChild(source);
                    videoEl.load();
                }
                if (placeholder) placeholder.style.display = 'none';
                if (display) display.style.display = 'flex';
                if (container) {
                    container.classList.remove('has-no-photos');
                    container.classList.add('has-photos');
                }
            } else {
                if (display) display.style.display = 'none';
                if (placeholder) placeholder.style.display = 'block';
                if (container) {
                    container.classList.remove('has-photos');
                    container.classList.add('has-no-photos');
                }
            }
        });
    }

    // Min quantity → auto-toggle per-person checkbox (delegation)
    document.getElementById('ticket-tbody').addEventListener('input', function(e) {
        if (e.target.classList.contains('min-qty-input')) {
            const tr = e.target.closest('tr');
            const perPersonCb = tr.querySelector('.per-person-hidden');
            if (perPersonCb) {
                const val = parseInt(e.target.value, 10);
                // Если больше 1, ставим скрытую галочку, иначе снимаем
                perPersonCb.checked = (val > 1);
            }
        }
    });

    // Sync existing rows on load
    document.querySelectorAll('.min-qty-input').forEach(function(input) {
        const tr = input.closest('tr');
        const perPersonCb = tr.querySelector('.per-person-hidden');
        if (perPersonCb) {
            const val = parseInt(input.value, 10);
            perPersonCb.checked = (val > 1);
        }
    });

    // Duration picker popup
    initDurationPicker();

    // Map
    let placeAdditionalInfoInput = document.getElementById('id_additional_adress');
    let placeDataInput = document.getElementById('id_place_data');
    const addressDisplayInput = document.getElementById('id_place_address');
    let savedPlaceDataValue = '';

    // Сохраняем значение place_data до очистки контейнера карты
    if (placeDataInput) {
        savedPlaceDataValue = placeDataInput.value;
    }

    function loadYandexMapsAPI() {
        if (window.ymaps && window.ymaps.ready) {
            initMapWithData();
            return;
        }
        const script = document.createElement('script');
        // API-ключ передаётся шаблоном через data-атрибут .partner-layout
        const layoutEl = document.querySelector('.partner-layout');
        const apiKey = layoutEl ? (layoutEl.dataset.yandexMapsApiKey || '') : '';
        script.src = 'https://api-maps.yandex.ru/2.1/?apikey=' + encodeURIComponent(apiKey) + '&lang=ru_RU';
        script.onload = function() {
            ymaps.ready(function() { initMapWithData(); });
        };
        script.onerror = function() {
            document.getElementById('map').innerHTML = '<p class="text-danger">Не удалось загрузить карту.</p>';
        };
        document.head.appendChild(script);
    }

    // Восстанавливаем сохранённые данные места из data-атрибутов шаблона
    // (JS-файл статический и не обрабатывается Django-шаблонизатором)
    function getSavedPlaceData() {
        const layoutEl = document.querySelector('.partner-layout');
        const raw = layoutEl ? layoutEl.dataset.savedPlaceData : '';
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch (e) {
            console.warn('[Map] Invalid saved place_data:', e);
            return null;
        }
    }

    function initMapWithData() {
        initMap();
        var savedData = getSavedPlaceData();
        if (savedData && savedData.coordinates) {
            updateMapFromData(savedData);
            if (savedData.additional_info && placeAdditionalInfoInput) placeAdditionalInfoInput.value = savedData.additional_info;
        }
    }

    function initMap() {
        var mapContainer = document.getElementById('map');
        mapContainer.classList.remove('map-loading');
        mapContainer.innerHTML = '';
        window.eventMap = new ymaps.Map("map", {
            center: [55.030204, 82.920430], zoom: 10, controls: ['zoomControl']
        }, { suppressMapOpenBlock: true });
        window.eventMap.events.add('click', function(e) {
            placePlacemark(e.get('coords'));
        });
        
        // Восстанавливаем скрытое поле place_data после очистки контейнера
        if (savedPlaceDataValue !== '') {
            var hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.id = 'id_place_data';
            hiddenInput.name = 'place_data';
            hiddenInput.value = savedPlaceDataValue;
            mapContainer.appendChild(hiddenInput);
            placeDataInput = hiddenInput;
        }
    }

    function placePlacemark(coords) {
        var additionalInfo = placeAdditionalInfoInput.value;
        window.eventMap.geoObjects.removeAll();
        var placemark = new ymaps.Placemark(coords, {
            hintContent: 'Выбранное место', balloonContent: 'Выбранное место'
        }, { preset: 'islands#blueStretchyIcon' });
        window.eventMap.geoObjects.add(placemark);
        window.eventMap.setCenter(coords, 15);
        
        console.log('[Map] Click on coords:', coords);
        
        // Сначала пробуем геокодер с kind: 'house' для точного адреса
        ymaps.geocode(coords, { results: 1, kind: 'house' }).then(function(res) {
            var firstGeoObject = res.geoObjects.get(0);
            var address = '';
            var placeData = {};
            
            if (firstGeoObject) {
                console.log('[Map] GeoObject props:', firstGeoObject.properties._prefixedValues);
                
                // Собираем адрес из компонентов
                var streetName = firstGeoObject.properties.get('Premise');
                var houseNumber = firstGeoObject.properties.get('HouseNumber');
                var district = firstGeoObject.properties.get('District');
                var locality = firstGeoObject.properties.get('Locality');
                var adminDistrict = firstGeoObject.properties.get('AdminDistrict');
                
                // Полный адрес из getAddressLine()
                var fullAddressLine = firstGeoObject.getAddressLine();
                console.log('[Map] fullAddressLine:', fullAddressLine);
                
                // Собираем адрес — используем Premise + HouseNumber если есть
                if (streetName && houseNumber) {
                    address = streetName + ', ' + houseNumber;
                } else if (streetName) {
                    address = streetName;
                } else {
                    address = fullAddressLine;
                }
                
                // Город: сначала пытаемся получить из свойств, если нет — парсим из fullAddressLine
                var city = locality || adminDistrict;
                if (!city) {
                    // Парсим город из fullAddressLine: "Новосибирск, улица Никитина, 15"
                    var parts = fullAddressLine.split(',').map(function(p) { return p.trim(); });
                    if (parts.length > 0) {
                        city = parts[0]; // Первый элемент — обычно город
                    }
                }
                
                // Заполняем placeData
                placeData.coordinates = coords;
                placeData.address = address;
                placeData.additional_info = additionalInfo;
                placeData.latitude = coords[0];
                placeData.longitude = coords[1];
                
                if (city) placeData.city = city;
                if (district) placeData.district = district;
                
                console.log('[Map] placeData before metro:', JSON.stringify(placeData));
                
                // Ищем ближайшие станции метро
                var bounds = firstGeoObject.properties.get('boundedBy');
                if (bounds) {
                    ymaps.geocode(bounds, { results: 10, kind: 'metro' }).then(function(metroRes) {
                        var metroObjects = metroRes.geoObjects;
                        if (metroObjects.getLength() > 0) {
                            var nearestMetro = metroObjects.get(0);
                            var metro = nearestMetro.getAddressLine();
                            placeData.metro = metro;
                            console.log('[Map] Metro found:', metro);
                        }
                        console.log('[Map] Final place_data:', JSON.stringify(placeData));
                        if (placeDataInput) {
                            placeDataInput.value = JSON.stringify(placeData);
                        }
                    }).catch(function(err) {
                        console.log('[Map] Metro search failed:', err);
                        console.log('[Map] Final place_data (no metro):', JSON.stringify(placeData));
                        if (placeDataInput) {
                            placeDataInput.value = JSON.stringify(placeData);
                        }
                    });
                } else {
                    console.log('[Map] Final place_data (no bounds):', JSON.stringify(placeData));
                    if (placeDataInput) {
                        placeDataInput.value = JSON.stringify(placeData);
                    }
                }
            } else {
                // Геокодер не вернул результат — используем координаты
                address = coords.join(', ');
                placeData.coordinates = coords;
                placeData.address = address;
                placeData.additional_info = additionalInfo;
                placeData.latitude = coords[0];
                placeData.longitude = coords[1];
                
                console.log('[Map] No geocode result, saved coords:', JSON.stringify(placeData));
                if (placeDataInput) {
                    placeDataInput.value = JSON.stringify(placeData);
                }
            }
            
            addressDisplayInput.value = address;
            placemark.properties.set({
                balloonContent: address + (additionalInfo ? '<br>Дополнительно: ' + additionalInfo : '')
            });
            
            console.log('[Map] Address set:', address);
        }).catch(function(err) {
            console.error('[Map] Geocode error:', err);
            // При ошибке сохраняем хотя бы координаты
            var fallbackData = {
                coordinates: coords,
                address: coords.join(', '),
                additional_info: additionalInfo,
                latitude: coords[0],
                longitude: coords[1]
            };
            addressDisplayInput.value = fallbackData.address;
            if (placeDataInput) {
                placeDataInput.value = JSON.stringify(fallbackData);
            }
        });
    }

    function updateMapFromData(data) {
        if (data.coordinates && data.coordinates.length === 2) {
            var coords = data.coordinates;
            placeAdditionalInfoInput.value = data.additional_info || '';
            addressDisplayInput.value = data.address || '';
            window.eventMap.setCenter(coords, 15);
            var placemark = new ymaps.Placemark(coords, {
                balloonContent: data.address + (data.additional_info ? '<br>Доп: ' + data.additional_info : '')
            }, { preset: 'islands#blueStretchyIcon' });
            window.eventMap.geoObjects.add(placemark);
            
            // Сохраняем place_data при загрузке существующих данных
            if (placeDataInput) {
                placeDataInput.value = JSON.stringify({
                    coordinates: coords,
                    address: data.address || '',
                    additional_info: data.additional_info || ''
                });
            }
        }
    }

    loadYandexMapsAPI();

    // Toast on form errors
    // Ошибки формы передаются шаблоном через data-form-errors на .partner-layout
    (function showFormErrorToasts() {
        const layoutEl = document.querySelector('.partner-layout');
        const raw = layoutEl ? layoutEl.dataset.formErrors : '';
        if (!raw) return;
        let errors;
        try {
            errors = JSON.parse(raw);
        } catch (e) {
            return;
        }
        Object.keys(errors).forEach(function (field) {
            const messages = errors[field];
            (Array.isArray(messages) ? messages : [messages]).forEach(function (msg) {
                showToast(msg, true);
            });
        });
    })();


    // Флаги: пользователь выбрал новый файл, но форма ещё не сохранена —
    // файла нет в БД, удалять на сервере нечего, чистим только превью.
    let newVideoSelected = false;
    let newProgramSelected = false;

    // Remove program/video file button (крестик — удаление файла, включая видео)
    document.querySelectorAll('.program-remove-btn, .video-delete-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const mediaType = this.dataset.mediaType;
            const mediaId = this.dataset.mediaId || '';

            // Определяем, к какому контейнеру относится кнопка
            const isVideo = mediaType === 'video_url';
            const display = document.getElementById(isVideo ? 'video-file-display' : 'program-file-display');
            const placeholder = document.getElementById(isVideo ? 'video-upload-placeholder' : 'program-upload-placeholder');
            const container = document.getElementById(isVideo ? 'video-upload-container' : 'program-upload-container');
            const fileNameSpan = document.getElementById(isVideo ? 'video-file-name' : 'program-file-name');

            function setFileState(hasFile) {
                if (display) display.style.display = hasFile ? 'flex' : 'none';
                if (placeholder) placeholder.style.display = hasFile ? 'none' : 'block';
                if (container) {
                    container.classList.toggle('has-photos', hasFile);
                    container.classList.toggle('has-no-photos', !hasFile);
                }
            }

            function clearFileInput() {
                // Очищаем input файла, чтобы при повторном выборе того же файла сработало change
                const fileInput = document.getElementById(isVideo ? 'id_video_url' : 'id_program_file');
                if (fileInput) fileInput.value = '';
            }

            // Файл выбран, но форма не сохранена — на сервере его нет
            const isNewFile = isVideo ? newVideoSelected : newProgramSelected;
            if (isNewFile) {
                if (isVideo) newVideoSelected = false; else newProgramSelected = false;
                setFileState(false);
                clearFileInput();
                return;
            }

            // Если это новый файл (ещё не на сервере) — просто скрываем превью
            if (!mediaId) {
                setFileState(false);
                return;
            }

            // === В режиме заявки на изменение — просто скрываем и отмечаем флаг очистки ===
            // Файл будет удалён при одобрении заявки (clear_image/clear_video_url/clear_program_file)
            // или останется в мероприятии при отклонении
            // Режим заявки на изменение передаётся шаблоном через data-is-change-request
            const layoutEl = document.querySelector('.partner-layout');
            const isChangeRequest = layoutEl && layoutEl.dataset.isChangeRequest === 'true';
            if (isChangeRequest) {
                // Отмечаем флаг очистки
                if (mediaType === 'video_url') {
                    const vf = document.getElementById('clear_video_url');
                    if (vf) vf.value = '1';
                } else if (mediaType === 'program_file') {
                    const pf = document.getElementById('clear_program_file');
                    if (pf) pf.value = '1';
                } else if (mediaType === 'image') {
                    const df = document.getElementById('delete_main_image');
                    if (df) df.value = '1';
                }
                setFileState(false);
                clearFileInput();
                return;
            }

            fetch('/partner/remove_media/' + mediaType + '/' + mediaId + '/', {
                method: 'POST',
                headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    setFileState(false);
                    clearFileInput();
                } else {
                    showToast('Ошибка удаления', true);
                }
            })
            .catch(err => showToast('Ошибка: ' + err.message, true));
        });
    });

    // Replace video button (заменить видео — иконка загрузки)
    document.querySelectorAll('.video-upload-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const fileInput = document.getElementById('id_video_url');
            if (fileInput) fileInput.click();
        });
    });

    // Replace media button (замена файла/видео)
    document.querySelectorAll('.media-program-button').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const mediaType = this.dataset.mediaType;
            const fileInputId = mediaType === 'video_url' ? 'id_video_url' : 'id_program_file';
            const fileInput = document.getElementById(fileInputId);
            if (fileInput) {
                fileInput.click();
            }
        });
    });

    // Remove media buttons (video и др.)
    document.querySelectorAll('.remove-media-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const mediaType = this.dataset.mediaType;
            const mediaId = this.dataset.mediaId || '';
            if (!mediaType) return;

            fetch('/partner/remove_media/' + mediaType + '/' + mediaId + '/', {
                method: 'POST',
                headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') location.reload();
                else showToast('Ошибка удаления', true);
            })
            .catch(err => showToast('Ошибка: ' + err.message, true));
        });
    });
});

// ============================================================
// CLOSE ALL DROPDOWNS
// ============================================================
function closeAllDropdowns() {
    // Закрываем все dropdown
    document.querySelectorAll('.dropdown-menu-custom').forEach(d => d.classList.remove('active'));
    document.querySelectorAll('.dropdown-container').forEach(c => c.classList.remove('open'));
    document.querySelectorAll('.calendar-popup').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.date-container').forEach(c => c.classList.remove('open'));
    document.querySelectorAll('.duration-popup').forEach(d => d.classList.remove('active'));
    document.querySelectorAll('.duration-container').forEach(c => c.classList.remove('open'));
}

// ============================================================
// DURATION PICKER POPUP
// ============================================================
function adjustDuration(field, delta) {
    const hoursInput = document.getElementById('durationHours');
    const minutesInput = document.getElementById('durationMinutes');
    
    if (field === 'hours') {
        let val = parseInt(hoursInput.value || '0', 10) + delta;
        val = Math.max(0, Math.min(23, val));
        hoursInput.value = val;
    } else if (field === 'minutes') {
        let val = parseInt(minutesInput.value || '0', 10) + delta;
        val = Math.max(0, Math.min(59, val));
        minutesInput.value = val;
    }
    
    syncDurationToHidden();
}

function syncDurationToHidden() {
    const hoursInput = document.getElementById('durationHours');
    const minutesInput = document.getElementById('durationMinutes');
    const hiddenInput = document.getElementById('id_duration');
    const durationInput = document.getElementById('durationInput');
    
    const hours = String(hoursInput.value || '0').padStart(2, '0');
    const minutes = String(minutesInput.value || '0').padStart(2, '0');
    const value = hours + ':' + minutes;
    
    if (hiddenInput) hiddenInput.value = value;
    if (durationInput) durationInput.value = value;
}

function initDurationPicker() {
    const durationInput = document.getElementById('durationInput');
    const durationDropdown = document.getElementById('durationDropdown');
    const durationContainer = durationInput?.closest('.duration-container');
    
    if (!durationInput || !durationDropdown) return;
    
    // Если есть сохранённое значение — разобьём на часы/минуты
    const savedDuration = document.getElementById('id_duration')?.value;
    if (savedDuration && savedDuration.includes(':')) {
        const parts = savedDuration.split(':');
        document.getElementById('durationHours').value = parseInt(parts[0], 10) || 0;
        document.getElementById('durationMinutes').value = parseInt(parts[1], 10) || 0;
    }
    
    // Открытие/закрытие popup
    durationInput.addEventListener('click', function(e) {
        e.stopPropagation();
        const isActive = durationDropdown.classList.contains('active');
        
        // Закрываем все dropdown
        closeAllDropdowns();
        
        if (!isActive) {
            durationDropdown.classList.add('active');
            durationContainer?.classList.add('open');
        }
    });
    
    // Кнопка-стрелка
    const toggleBtn = durationContainer?.querySelector('.dropdown-toggle-btn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const isActive = durationDropdown.classList.contains('active');
            
            closeAllDropdowns();
            
            if (!isActive) {
                durationDropdown.classList.add('active');
                durationContainer.classList.add('open');
            }
        });
    }
    
    // Кнопка "Закрыть"
    const closeBtn = durationDropdown.querySelector('.duration-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            durationDropdown.classList.remove('active');
            durationContainer?.classList.remove('open');
        });
    }
    
    // Закрытие по клику вне
    document.addEventListener('click', function(e) {
        if (!durationContainer?.contains(e.target)) {
            durationDropdown.classList.remove('active');
            durationContainer?.classList.remove('open');
        }
    });
    
    // Синхронизация при ручном вводе
    document.getElementById('durationHours')?.addEventListener('input', syncDurationToHidden);
    document.getElementById('durationMinutes')?.addEventListener('input', syncDurationToHidden);
}

// Автоматическая проверка статуса обработки видео
// Данные передаются шаблоном через data-атрибуты .partner-layout:
// data-video-processing-status, data-event-id
document.addEventListener('DOMContentLoaded', function() {
    const layoutEl = document.querySelector('.partner-layout');
    if (!layoutEl) return;
    const status = layoutEl.dataset.videoProcessingStatus || '';
    const eventId = parseInt(layoutEl.dataset.eventId || '0', 10);
    if (!eventId || (status !== 'pending' && status !== 'processing')) return;
    const statusElement = document.getElementById('video-processing-status');

    function checkVideoProcessingStatus() {
        fetch(`/partner/check_video_status/${eventId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'completed') {
                    location.reload();
                } else if (data.status === 'pending' || data.status === 'processing') {
                    if (statusElement) statusElement.textContent = data.status_display;
                    setTimeout(checkVideoProcessingStatus, 5000);
                } else {
                    if (statusElement) statusElement.textContent = 'Ошибка обработки';
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
                setTimeout(checkVideoProcessingStatus, 10000);
            });
    }
    setTimeout(checkVideoProcessingStatus, 5000);
});
