function openBuyPackageModal(packageId, packageName, price) {
    var statusEl = document.querySelector('[data-verification-status]');
    if (statusEl && statusEl.dataset.verificationStatus !== 'approved') {
        alert('Для покупки пакета аккаунт должен быть одобрен.');
        return;
    }
    pendingPackageChange.packageId = packageId;
    pendingPackageChange.isChange = true;
    showPackageChangeModal('', '', packageName, price);
}

function openBuyNewPackageModal(packageId, packageName, price) {
    var statusEl = document.querySelector('[data-verification-status]');
    if (statusEl && statusEl.dataset.verificationStatus !== 'approved') {
        alert('Для покупки пакета аккаунт должен быть одобрен.');
        return;
    }
    pendingPackageChange.packageId = packageId;
    pendingPackageChange.isChange = false;
    document.getElementById('modal-package-id').value = packageId;
    var modalEl = document.getElementById('buy-package-modal');
    if (modalEl) modalEl.style.display = 'flex';
}

function closeBuyPackageModal() {
    var modalEl = document.getElementById('buy-package-modal');
    if (modalEl) modalEl.style.display = 'none';
}

var paymentMethodSelect = document.getElementById('payment-method');
if (paymentMethodSelect) {
    paymentMethodSelect.addEventListener('change', function() {
        var invoiceField = document.getElementById('invoice-admin-field');
        if (invoiceField) {
            invoiceField.style.display = this.value === 'invoice' ? 'block' : 'none';
        }
    });
}

var buyForm = document.getElementById('buy-package-form');
if (buyForm) {
    buyForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const packageId = formData.get('package_id');
    const paymentMethod = formData.get('payment_method');
    const submitBtn = this.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Обработка…';

    if (paymentMethod === 'yookassa') {
        // Проверяем, это смена пакета или новая покупка
        if (pendingPackageChange.isChange === false || pendingPackageChange.isChange === undefined) {
            // Новая покупка пакета
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
                    // Если вдруг оказалась активная подписка — показываем модалку смены
                    showPackageChangeModal(
                        data.current_package.name,
                        data.current_package.end_date,
                        data.new_package.name,
                        data.new_package.price
                    );
                } else {
                    alert('Ошибка: ' + (data.error || ''));
                }
            })
            .catch(err => alert('Ошибка: ' + err))
            .finally(() => { submitBtn.disabled = false; submitBtn.textContent = 'Купить'; });
        } else {
            // Смена пакета — используем запомненный тип (immediate или scheduled)
            changePackage(pendingPackageChange.changeType);
        }
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
                alert('Заявка на выставление счёта отправлена. После оплаты счёта подписка будет активирована.');
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
}

// Глобальные переменные для модального окна смены пакета
let pendingPackageChange = {
    packageId: null,
    currentPackageName: '',
    currentPackageEndDate: '',
    newPackageName: '',
    newPackagePrice: '',
    isChange: false,
    changeType: 'immediate'
};

function showPackageChangeModal(currentName, endDate, newName, price) {
    var textEl = document.getElementById('package-change-text');
    var btnSchedule = document.getElementById('btn-schedule-change');

    if (!textEl) return;

    if (!currentName || currentName === '') {
        textEl.innerHTML = 'Вы хотите приобрести пакет <strong>' + newName + '</strong> за <strong>' + price + ' руб.</strong>';
        if (btnSchedule) btnSchedule.style.display = 'none';
    } else {
        textEl.innerHTML = 'У вас есть активная подписка на пакет <strong>' + currentName + '</strong> до <strong>' + endDate + '</strong>.<br>Вы хотите перейти на пакет <strong>' + newName + '</strong> за <strong>' + price + ' руб.</strong>.';
        if (btnSchedule) btnSchedule.style.display = 'block';
    }

    var modalEl = document.getElementById('package-change-modal');
    if (modalEl) modalEl.style.display = 'flex';
}

function closePackageChangeModal() {
    var modalEl = document.getElementById('package-change-modal');
    if (modalEl) modalEl.style.display = 'none';
}

function changePackageImmediate() {
    pendingPackageChange.changeType = 'immediate';
    closePackageChangeModal();
    var modalEl = document.getElementById('buy-package-modal');
    if (modalEl) modalEl.style.display = 'flex';
}

function changePackageScheduled() {
    pendingPackageChange.changeType = 'scheduled';
    closePackageChangeModal();
    var modalEl = document.getElementById('buy-package-modal');
    if (modalEl) modalEl.style.display = 'flex';
}

function changePackage(changeType) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    fetch('/payment/handle_package_change_choice/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            package_id: pendingPackageChange.packageId,
            change_type: changeType
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            if (data.payment_url) {
                closePackageChangeModal();
                window.location.href = data.payment_url;
            } else {
                closePackageChangeModal();
                alert(data.message + ': ' + data.scheduled_change.new_package + ' с ' + data.scheduled_change.change_date);
                window.location.reload();
            }
        } else {
            alert('Ошибка: ' + (data.error || ''));
        }
    })
    .catch(err => alert('Ошибка: ' + err));
}

// Обработчики кнопок в модальном окне смены пакета
document.addEventListener('DOMContentLoaded', function() {
    var btnImmediate = document.getElementById('btn-immediate-change');
    var btnSchedule = document.getElementById('btn-schedule-change');
    if (btnImmediate) {
        btnImmediate.addEventListener('click', changePackageImmediate);
    }
    if (btnSchedule) {
        btnSchedule.addEventListener('click', changePackageScheduled);
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
var logoInput = document.getElementById('id_logo');
if (logoInput) {
    logoInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            var btn = this.closest('.form-group').querySelector('.file-upload-btn');
            if (btn) btn.textContent = 'Изменить';
        }
    });
}

var videoInput = document.getElementById('id_video_business_card');
if (videoInput) {
    videoInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            var btn = this.closest('.form-group').querySelector('.file-upload-btn');
            if (btn) btn.textContent = 'Изменить';
        }
    });
}