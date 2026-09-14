// === PARTNER EVENT LIST ===

// === Toast ===
function showToast(message, isError = true) {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;

    const toastElement = document.createElement('div');
    toastElement.className = `toast align-items-center text-white ${isError ? 'bg-danger' : 'bg-success'}`;
    toastElement.setAttribute('role', 'alert');
    toastElement.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>`;
    toastContainer.appendChild(toastElement);
    const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 5000 });
    toast.show();
    toastElement.addEventListener('hidden.bs.toast', () => toastElement.remove());
}

document.addEventListener('DOMContentLoaded', function() {
    const checkboxes = document.querySelectorAll('.event-checkbox');

    checkboxes.forEach(cb => {
        cb.addEventListener('change', function() {
            this.checked = false;
        });
    });
});

// === Entry Control Logic ===
let currentEventId = null;

document.querySelectorAll('.btn-entry-control').forEach(btn => {
    btn.addEventListener('click', function() {
        currentEventId = this.dataset.eventId;
        loadEntryControlStatus(currentEventId);
    });
});

function loadEntryControlStatus(eventId) {
    fetch(`/partner/entry-control/${eventId}/status/`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                renderEntryControl(data);
            }
        })
        .catch(err => {
            document.getElementById('entryControlBody').innerHTML = 
                '<div class="entry-control-error"><i class="bi bi-exclamation-triangle-fill" style="font-size:2rem;color:#dc3545;margin-bottom:8px;display:block;"></i>Ошибка загрузки</div>';
        });
}

function renderEntryControl(data) {
    const body = document.getElementById('entryControlBody');
    
    let linksHtml = '';
    if (data.links && data.links.length > 0) {
        data.links.forEach(link => {
            const statusBadge = link.is_active 
                ? '<span class="entry-control-status-badge entry-control-status-badge--active"><i class="bi bi-check-circle-fill"></i> Активен</span>' 
                : '<span class="entry-control-status-badge entry-control-status-badge--inactive"><i class="bi bi-pause-circle"></i> Отключён</span>';
            const btnAction = link.is_active
                ? `<button class="entry-control-btn entry-control-btn--toggle" onclick="toggleLink(${link.id})"><i class="bi bi-pause-circle"></i> Отключить</button>
                   <button class="entry-control-btn entry-control-btn--delete" onclick="deleteLink(${link.id})"><i class="bi bi-trash"></i> Удалить</button>`
                : `<button class="entry-control-btn entry-control-btn--activate" onclick="toggleLink(${link.id})"><i class="bi bi-play-circle"></i> Включить</button>
                   <button class="entry-control-btn entry-control-btn--delete" onclick="deleteLink(${link.id})"><i class="bi bi-trash"></i> Удалить</button>`;
            
            linksHtml += `
                <div class="entry-control-link-card">
                    <div class="entry-control-link-body">
                        <div class="entry-control-link-info">
                            <div class="entry-control-link-name">
                                ${link.name || 'Контролёр'} ${statusBadge}
                            </div>
                            <div class="entry-control-link-meta">
                                Код: <code>${link.access_code}</code>
                                | Отсканировано: <strong>${link.scanned_count}</strong>
                            </div>
                        </div>
                        <div class="entry-control-link-actions">
                            <button class="entry-control-btn entry-control-btn--copy" onclick="copyUrl('${link.scanner_url}')">
                                <i class="bi bi-clipboard"></i> Копировать
                            </button>
                            ${btnAction}
                        </div>
                    </div>
                </div>
            `;
        });
    }
    
    const createBtnClass = data.active_count >= 2 
        ? 'entry-control-create-btn entry-control-create-btn--disabled' 
        : 'entry-control-create-btn entry-control-create-btn--success';
    const createBtnDisabled = data.active_count >= 2 ? 'disabled' : '';
    const createBtnText = data.active_count >= 2 ? '(Лимит достигнут)' : '';
    
    body.innerHTML = `
        <div class="entry-control-stats">
            <div class="entry-control-stats-total">
                <i class="bi bi-people"></i> Всего отсканировано: <strong>${data.total_scanned}</strong>
            </div>
            <span class="entry-control-stats-badge">
                <i class="bi bi-link-45deg"></i> ${data.active_count || 0} / 2 активных
            </span>
        </div>
        
        <div class="entry-control-create-zone">
            <label class="entry-control-create-label">Имя контролёра (необязательно):</label>
            <input type="text" class="entry-control-name-input" id="controllerName" placeholder="Например: Алексей — вход №1">
            <button class="${createBtnClass}" 
                    onclick="createLink()" 
                    ${createBtnDisabled}>
                <i class="bi bi-plus-circle"></i> Создать код доступа ${createBtnText}
            </button>
        </div>
        
        <div class="entry-control-links-section">
            <h6 class="entry-control-links-title">
                <i class="bi bi-link-45deg"></i> Активные ссылки (${data.links ? data.links.length : 0})
            </h6>
            <div id="linksList">${linksHtml}</div>
        </div>
    `;
}

function createLink() {
    const name = document.getElementById('controllerName').value.trim();
    const body = document.getElementById('entryControlBody');
    
    body.innerHTML = `
        <div class="entry-control-spinner entry-control-spinner--success">
            <i class="bi bi-gear-spin"></i>
            <p class="entry-control-spinner-text">Создаю код доступа...</p>
        </div>
    `;
    
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
    if (name) formData.append('name', name);
    
    fetch(`/partner/entry-control/${currentEventId}/enable/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast('Код доступа создан!', false);
            loadEntryControlStatus(currentEventId);
        } else {
            body.innerHTML = `<div class="text-center py-4 text-danger">${data.message}</div>`;
        }
    })
    .catch(err => {
        body.innerHTML = '<div class="entry-control-error"><i class="bi bi-exclamation-triangle-fill" style="font-size:2rem;color:#dc3545;margin-bottom:8px;display:block;"></i>Ошибка создания кода</div>';
    });
}

function toggleLink(linkId) {
    fetch(`/partner/entry-control/${linkId}/toggle/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, data.is_active);
            loadEntryControlStatus(currentEventId);
        } else {
            showToast(data.message, true);
        }
    });
}

function deleteLink(linkId) {
    if (!confirm('Удалить этот код навсегда?')) return;
    
    fetch(`/partner/entry-control/${linkId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast('Код удалён');
            loadEntryControlStatus(currentEventId);
        } else {
            showToast(data.message);
        }
    });
}

function copyUrl(url) {
    navigator.clipboard.writeText(url).then(() => {
        showToast('Ссылка скопирована!', false);
    }).catch(() => {
        // Fallback
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        showToast('Ссылка скопирована!', false);
    });
}

function getCookie(name) {
    let cookieValue = null;
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', function() {
    var displayInput = document.getElementById('id_date_display');
    var hiddenInput = document.getElementById('id_date');
    var filtersForm = document.querySelector('.filters-panel');

    // 1. Инициализация календаря
    if (typeof CustomCalendar !== 'undefined') {
        window.filterDateCalendar = new CustomCalendar(
            'id_date_display',
            'dateCalendar',
            'id_date',
            {
                displayDateFormat: 'dd.mm.yyyy',
                valueDateFormat: 'yyyy-mm-dd',
                allowPastDates: true
            }
        );
    } else {
        console.error("Скрипт CustomCalendar не загружен!");
    }

    // 2. Функция конвертации ДД.ММ.ГГГГ -> ГГГГ-ММ-ДД
    function convertToServerFormat(dateStr) {
        if (!dateStr) return '';
        dateStr = dateStr.trim();
        var parts = dateStr.split('.');
        if (parts.length === 3) {
            var day = parts[0].padStart(2, '0');
            var month = parts[1].padStart(2, '0');
            var year = parts[2];
            return year + '-' + month + '-' + day;
        }
        return dateStr;
    }

    // 3. Синхронизация: при любом изменении видимого поля обновляем скрытое
    if (displayInput && hiddenInput) {
        displayInput.addEventListener('change', function() {
            hiddenInput.value = convertToServerFormat(displayInput.value);
        });

        var calendarPopup = document.getElementById('dateCalendar');
        if (calendarPopup) {
            calendarPopup.addEventListener('click', function() {
                setTimeout(function() {
                    hiddenInput.value = convertToServerFormat(displayInput.value);
                }, 50);
            });
        }
    }

    // 4. Синхронизация перед отправкой формы
    if (filtersForm && displayInput && hiddenInput) {
        filtersForm.addEventListener('submit', function(e) {
            hiddenInput.value = convertToServerFormat(displayInput.value);
        });
    }
});
