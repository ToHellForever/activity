// === PARTNER DASHBOARD EXTRA ===

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
                if (invoiceField) {
                    invoiceField.style.display = this.getAttribute('data-value') === 'invoice' ? 'block' : 'none';
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

// Inline save script
document.addEventListener('DOMContentLoaded', function() {
    // URL эндпоинтов задаются шаблоном через meta-теги (см. dashboard.html)
    function metaContent(name) {
        const meta = document.querySelector('meta[name="' + name + '"]');
        return meta ? meta.content : '';
    }
    const saveFieldUrl = metaContent('save-field-url') || '/partner/save_field/';
    const changePasswordUrl = metaContent('change-password-url') || '/partner/change-password/';
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const editIcons = document.querySelectorAll('.edit-icon');

    editIcons.forEach(function(icon) {
        let isEditing = false;

        icon.addEventListener('click', function(e) {
            e.preventDefault();
            const field = this.closest('.editable-field');
            const input = field.querySelector('input, textarea');
            const field_name = input.name;

            if (!isEditing) {
                // === АКТИВАЦИЯ РЕДАКТИРОВАНИЯ ===
                isEditing = true;

                // Меняем иконку на галочку (сохранить)
                this.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
                this.style.color = '#4caf50';

                // Подсвечиваем поле
                field.classList.add('editable-field--active');
                input.style.borderColor = '#4caf50';
                input.style.boxShadow = '0 0 0 2px rgba(76,175,80,0.2)';

                // Разблокируем поле
                input.removeAttribute('readonly');
                input.focus();
                input.select();
            } else {
                // === СОХРАНЕНИЕ ===
                const field_value = input.value;

                // Меняем иконку обратно на карандаш
                this.innerHTML = '<img src="/media/icon/edit.svg" alt="">';
                this.style.color = '';

                // Убираем подсветку
                field.classList.remove('editable-field--active');
                input.style.borderColor = '';
                input.style.boxShadow = '';

                // Блокируем поле
                input.setAttribute('readonly', '');
                isEditing = false;

                // AJAX сохранение
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
                        showSaveNotification('Сохранено');
                    } else {
                        showSaveNotification('Ошибка сохранения', true);
                    }
                })
                .catch(function(err) {
                    showSaveNotification('Ошибка сети', true);
                });
            }
        });
    });

    function showSaveNotification(text, isError) {
        let notif = document.getElementById('save-notification');
        if (!notif) {
            notif = document.createElement('div');
            notif.id = 'save-notification';
            notif.style.cssText = 'position:fixed;top:20px;right:20px;padding:10px 20px;border-radius:8px;color:#fff;font-size:13px;z-index:9999;transition:opacity 0.3s;';
            document.body.appendChild(notif);
        }
        notif.textContent = text;
        notif.style.background = isError ? '#f44336' : '#4caf50';
        notif.style.opacity = '1';
        setTimeout(function() { notif.style.opacity = '0'; }, 2000);
    }

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

    // ===== Модальное окно смены пароля =====
    var passwordModal = document.getElementById('password-modal');
    var openPasswordBtn = document.getElementById('open-password-modal');
    var closePasswordBtn = document.getElementById('close-password-modal');

    if (openPasswordBtn && passwordModal) {
        openPasswordBtn.addEventListener('click', function() {
            passwordModal.style.display = 'flex';
        });
    }
    if (closePasswordBtn && passwordModal) {
        closePasswordBtn.addEventListener('click', function() {
            passwordModal.style.display = 'none';
        });
    }
    if (passwordModal) {
        passwordModal.addEventListener('click', function(e) {
            if (e.target === passwordModal) {
                passwordModal.style.display = 'none';
            }
        });
    }

    // AJAX-отправка формы смены пароля (ошибки показываются в модалке)
    var passwordForm = document.getElementById('passwordModalForm');
    if (passwordForm) {
        passwordForm.addEventListener('submit', function(e) {
            e.preventDefault();

            // Скрываем прошлые ошибки
            ['old_password', 'new_password1', 'new_password2'].forEach(function(name) {
                var el = document.getElementById('error_' + name);
                if (el) { el.style.display = 'none'; el.textContent = ''; }
            });
            var nonField = document.getElementById('error_non_field');
            if (nonField) { nonField.style.display = 'none'; nonField.textContent = ''; }

            var formData = new FormData(passwordForm);
            formData.append('csrfmiddlewaretoken', csrfToken);

            fetch(changePasswordUrl, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                body: formData
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.status === 'success') {
                    passwordModal.style.display = 'none';
                    passwordForm.reset();
                    showSaveNotification('Пароль успешно изменён!');
                } else if (data.status === 'error' && data.errors) {
                    var hasErrors = false;
                    Object.keys(data.errors).forEach(function(field) {
                        var target = document.getElementById('error_' + field);
                        if (!target) target = nonField;
                        if (target) {
                            target.textContent = data.errors[field].join(' ');
                            target.style.display = 'block';
                            hasErrors = true;
                        }
                    });
                    if (!hasErrors) showSaveNotification('Ошибка сохранения', true);
                } else {
                    showSaveNotification('Ошибка сохранения', true);
                }
            })
            .catch(function(err) {
                showSaveNotification('Ошибка сети', true);
            });
        });
    }

    // Загрузка видео-визитки
    var videoInput = document.getElementById('id_video_business_card');
    if (videoInput) {
        videoInput.addEventListener('change', function() {
            var file = this.files[0];
            if (!file) return;

            var formData = new FormData();
            formData.append('video_business_card', file);
            formData.append('csrfmiddlewaretoken', csrfToken);

            fetch(saveFieldUrl + '?action=upload_video', {
                method: 'POST',
                body: formData
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.status === 'success') {
                    showSaveNotification('Видео загружено');
                    setTimeout(function() { location.reload(); }, 1500);
                } else {
                    showSaveNotification(data.message || 'Ошибка загрузки видео', true);
                }
            })
            .catch(function(err) {
                showSaveNotification('Ошибка сети', true);
            });
        });
    }
});
