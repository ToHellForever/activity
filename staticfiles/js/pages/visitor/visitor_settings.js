// === VISITOR SETTINGS ===

document.addEventListener('DOMContentLoaded', function() {
    // === Toggle password visibility ===
    document.querySelectorAll('.password-field .password-toggle').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var input = this.closest('.password-field').querySelector('input');
            var isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            this.innerHTML = isPassword
                ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>'
                : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
        });
    });

    // === Modal password ===
    const modal = document.getElementById('password-modal');
    const openBtn = document.getElementById('open-password-modal');
    const closeBtn = document.getElementById('close-password-modal');

    openBtn.addEventListener('click', function() {
        modal.style.display = 'flex';
    });

    closeBtn.addEventListener('click', function() {
        modal.style.display = 'none';
    });

    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });

    // === Editable fields (same as dashboard) ===
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const editIcons = document.querySelectorAll('.editable-field .edit-icon');

    editIcons.forEach(function(icon) {
        let isEditing = false;

        icon.addEventListener('click', function(e) {
            // Skip if icon is disabled
            if (this.style.opacity === '0.5') return;

            e.preventDefault();
            const field = this.closest('.editable-field');
            const input = field.querySelector('input');
            const field_name = input.name;

            if (!isEditing) {
                // === Activate editing ===
                isEditing = true;

                // Change icon to checkmark
                this.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
                this.style.color = '#4caf50';

                // Activate field
                field.classList.add('editable-field--active');
                input.removeAttribute('readonly');
                input.focus();
                input.select();

                // === Блокировка букв для телефона ===
                if (field_name === 'phone') {
                    input.addEventListener('keydown', function(e) {
                        // Разрешить: Backspace, Delete, Tab, Enter, стрелки
                        if ([8, 9, 13, 46, 37, 38, 39, 40].indexOf(e.keyCode) !== -1) {
                            return;
                        }
                        // Разрешить: Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
                        if ((e.ctrlKey || e.metaKey) && [65, 67, 86, 88].indexOf(e.keyCode) !== -1) {
                            return;
                        }
                        // Разрешить только цифры, +, -, скобки, пробел
                        const allowedKeys = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, // 0-9
                                           96, 97, 98, 99, 100, 101, 102, 103, 104, 105, // Numpad 0-9
                                           187, 189, // + и - (в зависимости от раскладки)
                                           107, 109, // Numpad + и -
                                           32]; // пробел
                        if (allowedKeys.indexOf(e.keyCode) !== -1) {
                            return;
                        }
                        e.preventDefault();
                    });

                    // Блокировка вставки нежелательных символов
                    input.addEventListener('paste', function(e) {
                        e.preventDefault();
                        const pasted = (e.clipboardData || window.clipboardData).getData('text');
                        const cleaned = pasted.replace(/[^0-9\+\-\(\)\s]/g, '');
                        document.execCommand('insertText', false, cleaned);
                    });
                }
            } else {
                // === Save ===
                let field_value = input.value;

                // Валидация телефона
                if (field_name === 'phone') {
                    // Пустое значение = "не указан" — разрешаем
                    if (field_value.trim() === '') {
                        field_value = '';
                    } else {
                        const digitsOnly = field_value.replace(/\D/g, '');
                        if (digitsOnly.length < 10) {
                            showNotification('Введите корректный номер телефона (минимум 10 цифр)', true);
                            isEditing = false;
                            input.setAttribute('readonly', '');
                            this.innerHTML = '<img src="/media/icon/edit.svg" alt="">';
                            field.classList.remove('editable-field--active');
                            return;
                        }
                    }
                }

                // Reset icon
                this.innerHTML = '<img src="/media/icon/edit.svg" alt="">';
                this.style.color = '';

                // Deactivate field
                field.classList.remove('editable-field--active');
                input.setAttribute('readonly', '');
                isEditing = false;

                // AJAX save
                // URL сохранения поля задаётся шаблоном через data-save-field-url на .visitor-layout
        const layoutEl = document.querySelector('.visitor-layout');
        const saveFieldUrl = (layoutEl && layoutEl.dataset.saveFieldUrl) || '/visitor/save_field/';
        fetch(saveFieldUrl, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: 'field_name=' + encodeURIComponent(field_name) + '&field_value=' + encodeURIComponent(field_value)
                })
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    if (data.status === 'success') {
                        showNotification('Сохранено');
                    } else {
                        showNotification('Ошибка сохранения', true);
                    }
                })
                .catch(function(err) {
                    showNotification('Ошибка сети', true);
                });
            }
        });
    });

    function showNotification(text, isError) {
        let notif = document.getElementById('save-notification');
        if (!notif) {
            notif = document.createElement('div');
            notif.id = 'save-notification';
            notif.style.cssText = 'position:fixed;top:20px;right:20px;padding:10px 20px;border-radius:8px;color:#fff;font-size:13px;z-index:9999;transition:opacity 0.3s;font-family:Verdana,sans-serif;';
            document.body.appendChild(notif);
        }
        notif.textContent = text;
        notif.style.background = isError ? '#f44336' : '#4caf50';
        notif.style.opacity = '1';
        setTimeout(function() { notif.style.opacity = '0'; }, 2000);
    }
});
