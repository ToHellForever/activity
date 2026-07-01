function openBuyPackageModal(packageId, packageName, price) {
    if ('{{ user.verification_status }}' !== 'approved') {
        alert('Для покупки пакета аккаунт должен быть одобрен.');
        return;
    }
    document.getElementById('modal-package-id').value = packageId;
    document.getElementById('buy-package-modal').style.display = 'flex';
}

function closeBuyPackageModal() {
    document.getElementById('buy-package-modal').style.display = 'none';
}

document.getElementById('payment-method').addEventListener('change', function() {
    document.getElementById('invoice-admin-field').style.display =
        this.value === 'invoice' ? 'block' : 'none';
});

document.getElementById('buy-package-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const packageId = formData.get('package_id');
    const paymentMethod = formData.get('payment_method');
    const submitBtn = this.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Обработка…';

    if (paymentMethod === 'yookassa') {
        fetch('/payment/create_package_payment/' + packageId + '/', {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }
        })
        .then(r => r.json())
        .then(data => {
            if (data.payment_url) {
                window.location.href = data.payment_url;
            } else if (data.has_active_subscription) {
                alert('У вас уже есть активная подписка.');
            } else {
                alert('Ошибка: ' + (data.error || ''));
            }
        })
        .catch(err => alert('Ошибка: ' + err))
        .finally(() => { submitBtn.disabled = false; submitBtn.textContent = 'Купить'; });
    } else {
        const adminEmail = formData.get('admin_email');
        if (!adminEmail) {
            alert('Укажите email администратора для выставления счёта.');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Купить';
            return;
        }
        fetch('/payment/create_invoice/' + packageId + '/', {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Заявка на выставление счёта отправлена.');
                closeBuyPackageModal();
                window.location.reload();
            } else {
                alert('Ошибка: ' + (data.error || ''));
            }
        })
        .catch(err => alert('Ошибка: ' + err))
        .finally(() => { submitBtn.disabled = false; submitBtn.textContent = 'Купить'; });
    }
});

function removeFile(type) {
    if (confirm('Удалить файл?')) {
        const input = document.getElementById('id_' + type);
        if (input) {
            input.value = '';
            input.dispatchEvent(new Event('change'));
        }
        // Убираем превью
        const preview = input?.closest('.form-group')?.querySelector('.file-preview');
        if (preview) preview.remove();
        // Показываем кнопку снова
        const btn = input?.closest('.form-group')?.querySelector('.file-upload-btn');
        if (btn) {
            btn.textContent = type === 'logo' ? 'Добавить логотип' : 'Добавить видео-визитку';
        }
    }
}

// Показываем имя файла при выборе
document.getElementById('id_logo').addEventListener('change', function() {
    if (this.files.length > 0) {
        const btn = this.closest('.form-group').querySelector('.file-upload-btn');
        btn.textContent = 'Изменить';
    }
});

document.getElementById('id_video_business_card').addEventListener('change', function() {
    if (this.files.length > 0) {
        const btn = this.closest('.form-group').querySelector('.file-upload-btn');
        btn.textContent = 'Изменить';
    }
});