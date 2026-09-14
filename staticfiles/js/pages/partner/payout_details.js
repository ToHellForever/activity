// === PAYOUT DETAILS ===

// CSRF-токен берётся из скрытого поля формы или cookie
// (статические JS-файлы не обрабатываются Django-шаблонизатором)
function getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input) return input.value;
    const match = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[2]) : '';
}

// === ГЛОБАЛЬНЫЕ ФУНКЦИИ (доступны из HTML onclick) ===
let deleteDetailId = null;

window.openDeleteModal = function(id) {
    deleteDetailId = id;
    const modal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    modal.show();
};

function showError(fieldId, msg) {
    const input = document.getElementById(fieldId);
    const error = document.getElementById(fieldId + '_error');
    if (input) input.classList.add('is-invalid');
    if (input) input.classList.remove('is-valid');
    if (error) {
        error.textContent = msg;
        error.classList.add('show');
    }
}

function clearError(fieldId) {
    const input = document.getElementById(fieldId);
    const error = document.getElementById(fieldId + '_error');
    if (input) {
        input.classList.remove('is-invalid');
        if (input.value.trim()) input.classList.add('is-valid');
    }
    if (error) {
        error.textContent = '';
        error.classList.remove('show');
    }
}

function validateField(fieldId) {
    const input = document.getElementById(fieldId);
    if (!input) return true;
    const val = input.value;
    const validators = {
        account_number: function(v) {
            const cv = v.replace(/\s/g, '');
            if (!cv) return 'Введите номер счёта или карты.';
            if (!/^\d+$/.test(cv)) return 'Номер должен содержать только цифры.';
            if (cv.length === 20) {
                if (!cv.startsWith('40817')) return 'Номер расчётного счёта должен начинаться с 40817.';
            } else if (cv.length === 16) {
                // Карта OK
            } else {
                return 'Номер счёта: 20 цифр или карта: 16 цифр.';
            }
            return '';
        },
        account_holder: function(v) {
            if (!v.trim()) return 'Введите ФИО владельца.';
            if (v.trim().length < 3) return 'ФИО должно содержать минимум 3 символа.';
            if (!/^[\w\s\-'\u0401\u0451а-яА-ЯёЁ]+$/.test(v.trim())) {
                return 'ФИО может содержать только буквы и дефис.';
            }
            return '';
        },
        bik: function(v) {
            if (!v.trim()) return '';
            const cv = v.replace(/\s/g, '');
            if (!/^\d+$/.test(cv)) return 'БИК должен содержать только цифры.';
            if (cv.length !== 9) return 'БИК: 9 цифр.';
            return '';
        }
    };
    const validator = validators[fieldId];
    if (!validator) return true;
    const msg = validator(val);
    if (msg) {
        showError(fieldId, msg);
        return false;
    }
    clearError(fieldId);
    return true;
}

window.openEditModal = function(id, bank, account, holder, bik) {
    // Очистить стили валидации
    ['edit_bank_name', 'edit_account_number', 'edit_account_holder', 'edit_bik'].forEach(clearError);

    // Установить значения
    document.getElementById('edit_detail_id').value = id;
    document.getElementById('editBankNameInput').value = {sberbank:'Сбербанк',tinkoff:'Тинькофф',vtb:'ВТБ',alfabank:'Альфа-Банк',other:'Другой банк'}[bank] || '';
    document.getElementById('editBankNameHidden').value = bank;
    document.getElementById('edit_account_number').value = account;
    document.getElementById('edit_account_holder').value = holder;
    document.getElementById('edit_bik').value = bik;

    // Показать модалку
    const modal = new bootstrap.Modal(document.getElementById('editPayoutModal'));
    modal.show();
    setTimeout(function() {
        document.getElementById('editBankNameInput').focus();
    }, 200);
};

// === ИНИЦИАЛИЗАЦИЯ при загрузке ===
document.addEventListener('DOMContentLoaded', function() {

    // Live-валидация при потере фокуса
    ['account_number', 'account_holder', 'bik'].forEach(function(fieldId) {
        const input = document.getElementById(fieldId);
        if (input) {
            input.addEventListener('blur', function() { validateField(fieldId); });
            input.addEventListener('input', function() {
                if (input.classList.contains('is-invalid')) validateField(fieldId);
            });
        }
    });

    // Маска для номера счёта — только цифры
    ['account_number', 'bik'].forEach(function(fieldId) {
        const input = document.getElementById(fieldId);
        if (input) {
            input.addEventListener('keydown', function(e) {
                const allowed = [8, 9, 13, 27, 46, 110, 188, 190, 37, 39];
                if (allowed.includes(e.keyCode)) return;
                if ((e.ctrlKey || e.metaKey) && [65, 67, 86, 88].includes(e.keyCode)) return;
                if ((e.keyCode >= 48 && e.keyCode <= 57) || e.keyCode >= 96) return;
                e.preventDefault();
            });
        }
    });

    // === ДОБАВЛЕНИЕ ===
    document.getElementById('addPayoutForm').addEventListener('submit', function(e) {
        e.preventDefault();

        // Валидация
        let valid = true;
        if (!document.getElementById('bankNameHidden').value) { showError('bank_name', 'Выберите банк'); valid = false; }
        else { clearError('bank_name'); }
        if (!validateField('account_number')) valid = false;
        if (!validateField('account_holder')) valid = false;
        if (!validateField('bik')) valid = false;
        if (!valid) return;

        const btn = document.getElementById('addPayoutBtn');
        btn.disabled = true;
        btn.textContent = 'Сохранение...';

        const formData = new URLSearchParams(new FormData(this));
        fetch('/partner/payout-details/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
            body: formData
        })
        .then(function() { window.location.reload(); })
        .catch(function() {
            showToast('Ошибка при сохранении.', 'error');
            btn.disabled = false;
            btn.textContent = 'Сохранить реквизиты';
        });
    });

    // === РЕДАКТИРОВАНИЕ ===
    document.getElementById('editPayoutBtn').addEventListener('click', function() {
        let valid = true;
        if (!document.getElementById('editBankNameHidden').value) { showError('edit_bank_name', 'Выберите банк'); valid = false; }
        else { clearError('edit_bank_name'); }
        if (!validateField('edit_account_number')) valid = false;
        if (!validateField('edit_account_holder')) valid = false;
        if (!validateField('edit_bik')) valid = false;
        if (!valid) return;

        const btn = this;
        btn.disabled = true;
        btn.textContent = 'Сохранение...';

        const formData = new URLSearchParams(new FormData(document.getElementById('editPayoutForm')));
        fetch('/partner/payout-details/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
            body: formData
        })
        .then(function() {
            const modal = bootstrap.Modal.getInstance(document.getElementById('editPayoutModal'));
            modal.hide();
            showToast('Реквизиты обновлены!', 'success');
            setTimeout(function() { window.location.reload(); }, 800);
        })
        .catch(function(xhr) {
            var msg = 'Ошибка';
            if (xhr.responseJSON && xhr.responseJSON.message) msg = xhr.responseJSON.message;
            showToast(msg, 'error');
            btn.disabled = false;
            btn.textContent = 'Сохранить';
        });
    });

    // === УДАЛЕНИЕ ===
    document.getElementById('confirmDeleteBtn').addEventListener('click', function() {
        if (!deleteDetailId) return;
        fetch('/partner/payout-details/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
            body: new URLSearchParams({
                action: 'delete',
                detail_id: deleteDetailId,
                csrfmiddlewaretoken: getCsrfToken()
            })
        })
        .then(function() {
            const modal = bootstrap.Modal.getInstance(document.getElementById('deleteConfirmModal'));
            modal.hide();
            showToast('Реквизиты удалены.', 'success');
            setTimeout(function() { window.location.reload(); }, 800);
        })
        .catch(function() {
            showToast('Ошибка при удалении.', 'error');
        });
    });

    // === УТИЛИТЫ ===
    function showToast(text, type) {
        const toast = document.getElementById('payoutToast');
        toast.className = 'payout-toast ' + type;
        toast.querySelector('.payout-toast-text').textContent = text;
        toast.querySelector('.payout-toast-icon').textContent = type === 'success' ? '✓' : '✕';
        toast.classList.add('show');
        setTimeout(function() { toast.classList.remove('show'); }, 3000);
    }

    // === Кастомные dropdown для select-ов ===
    function initDropdown(container) {
        if (!container) return;
        const input = container.querySelector('.filter-input-dropdown');
        const button = container.querySelector('.dropdown-toggle-btn');
        const dropdown = container.querySelector('.dropdown-menu-custom');
        const hiddenInput = container.querySelector('input[type="hidden"]');
        if (!input || !dropdown) return;

        function openDropdown() {
            const rect = input.getBoundingClientRect();
            dropdown.style.top = (rect.bottom + 4) + 'px';
            dropdown.style.left = rect.left + 'px';
            dropdown.style.width = rect.width + 'px';
            dropdown.classList.add('active');
            container.classList.add('open');
        }

        function closeDropdown() {
            dropdown.classList.remove('active');
            container.classList.remove('open');
        }

        button.addEventListener('click', function(e) {
            e.stopPropagation();
            if (dropdown.classList.contains('active')) closeDropdown();
            else openDropdown();
        });

        input.addEventListener('click', function(e) {
            e.stopPropagation();
            if (dropdown.classList.contains('active')) closeDropdown();
            else openDropdown();
        });

        dropdown.querySelectorAll('.dropdown-option').forEach(function(option) {
            option.addEventListener('click', function() {
                const value = this.getAttribute('data-value');
                const text = this.textContent.trim();
                input.value = text;
                if (hiddenInput) hiddenInput.value = value;

                dropdown.querySelectorAll('.dropdown-option').forEach(function(o) {
                    o.classList.remove('active');
                });
                this.classList.add('active');

                closeDropdown();
            });
        });

        document.addEventListener('click', function(e) {
            if (!container.contains(e.target)) {
                closeDropdown();
            }
        });
    }

    // Инициализация всех dropdown-ов
    document.querySelectorAll('.dropdown-container').forEach(function(container) {
        initDropdown(container);
    });
});
