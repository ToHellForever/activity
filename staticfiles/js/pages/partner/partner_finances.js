// === PARTNER FINANCES ===

$(document).ready(function() {
    let isSubmitting = false;
    // Максимальная сумма выплаты передаётся шаблоном через скрытый input #payoutAmount
    const amountInput = document.getElementById('payoutAmount');
    const maxPayoutAmount = amountInput
        ? parseFloat(String(amountInput.value).replace(',', '.'))
        : NaN;

    function formatInput(value) {
        return value.replace(',', '.');
    }

    function openPayoutModal() {
        let enteredAmountStr = formatInput($('#availableAmountInput').val());
        const enteredAmount = parseFloat(enteredAmountStr);
        
        if (isNaN(enteredAmount) || enteredAmount <= 0) {
            alert('Введите сумму выплаты больше нуля.');
            return;
        }

        if (enteredAmount > maxPayoutAmount) {
            alert('Сумма выплаты не может превышать доступную сумму: ' + maxPayoutAmount.toFixed(2) + ' ₽');
            return;
        }

        $('#payoutAmount').val(enteredAmount.toFixed(2));
        $('#payoutModal').modal('show');
        setTimeout(function() {
            $('#payoutAmount').trigger('focus');
        }, 200);
    }

    $('#openPayoutModalButton').on('click', function() {
        openPayoutModal();
    });

    $('#availableAmountInput').on('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            openPayoutModal();
        }
    });

    // Разрешаем ввод только цифр, точки и запятой
    $('#availableAmountInput, #payoutAmount').on('keydown', function(e) {
        const allowedKeys = [8, 9, 13, 27, 46, 110, 188, 190];
        if (allowedKeys.includes(e.keyCode)) return;
        if ((e.ctrlKey || e.metaKey) && [65, 67, 86, 88].includes(e.keyCode)) return;
        if ((e.keyCode >= 48 && e.keyCode <= 57) || e.keyCode === 190 || e.keyCode === 188) return;
        e.preventDefault();
    });

    $('#payoutRequestForm').submit(function(e) {
        e.preventDefault();

        let amountVal = formatInput($('input[name="amount"]').val());
        $('input[name="amount"]').val(amountVal);

        const currentValue = parseFloat($('input[name="amount"]').val());

        if (isNaN(currentValue) || currentValue > maxPayoutAmount) {
            alert('Сумма выплаты не может превышать доступную сумму: ' + maxPayoutAmount.toFixed(2) + ' ₽');
            return;
        }

        if (isSubmitting) return;

        const form = $(this);
        const button = form.find('button[type="submit"]');
        const spinner = button.find('.spinner-border');
        
        isSubmitting = true;
        spinner.removeClass('d-none');
        button.prop('disabled', true);
        
        // URL и CSRF-токен берутся из data-атрибута контейнера и скрытого поля формы
        const layout = document.querySelector('.partner-layout');
        const payoutUrl = (layout && layout.dataset.requestPayoutUrl) || '/partner/request_payout/';
        const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
        fetch(payoutUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrf,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: new URLSearchParams({
                amount: $('input[name="amount"]').val(),
                payout_details: $('select[name="payout_details"]').val(),
                comment: $('textarea[name="comment"]').val(),
                csrfmiddlewaretoken: csrf
            })
        })
        .then(response => response.json())
        .then(data => {
            isSubmitting = false;
            spinner.addClass('d-none');
            button.prop('disabled', false);
            
            if (data.status === 'success') {
                alert('Запрос на выплату успешно отправлен!');
                form.trigger('reset'); 
                $('#payoutModal').modal('hide'); 
                window.location.reload();
            } else {
                alert('Ошибка: ' + data.message);
            }
        })
        .catch(error => {
            isSubmitting = false;
            console.error('Error:', error);
            spinner.addClass('d-none');
            button.prop('disabled', false);
            alert('Произошла ошибка при отправке запроса на выплату');
        });
    });

    // === Кастомный dropdown для реквизитов ===
    (function() {
        const container = document.querySelector('#payoutDetailsDropdown')?.closest('.dropdown-container');
        if (!container) return;
        const input = container.querySelector('.filter-input-dropdown');
        // В разметке кнопки нет — используется сама строка ввода с иконкой-треугольником
        const button = container.querySelector('.dropdown-toggle-btn') || input;
        const dropdown = container.querySelector('.dropdown-menu-custom');
        const hidden = document.getElementById('payoutDetailsHidden');
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

        dropdown.querySelectorAll('.dropdown-option').forEach(function(opt) {
            opt.addEventListener('click', function() {
                const val = this.getAttribute('data-value');
                const txt = this.textContent.trim();
                input.value = txt;
                if (hidden) hidden.value = val;
                dropdown.querySelectorAll('.dropdown-option').forEach(function(o) { o.classList.remove('active'); });
                this.classList.add('active');
                closeDropdown();
            });
        });

        document.addEventListener('click', function(e) {
            if (!container.contains(e.target)) closeDropdown();
        });
    })();
});
