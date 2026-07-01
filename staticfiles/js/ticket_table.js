// Функция для добавления новой строки билета
function addTicketRow() {
    const tableBody = document.querySelector('#ticketTable tbody');
    const newRow = document.createElement('tr');
    
    newRow.innerHTML = `
        <td><input type="text" name="ticket_name[]" class="form-control" required></td>
        <td><input type="text" name="ticket_price[]" class="form-control" required></td>
        <td><input type="number" name="ticket_quantity[]" min="0" class="form-control" required></td>
        <td><input type="number" name="ticket_min_quantity[]" value="1" min="1" class="form-control" required></td>
        <td><input type="text" name="ticket_description[]" class="form-control"></td>
        <td><input type="checkbox" name="ticket_is_per_person[]" class="form-check-input per-person-check"></td>
        <td><button type="button" class="btn btn-danger btn-sm remove-ticket-row">Удалить</button></td>
    `;
    
    tableBody.appendChild(newRow);
    
    // Добавляем обработчик удаления для новой строки
    newRow.querySelector('.remove-ticket-row').addEventListener('click', function() {
        newRow.remove();
    });
}

// Функция для обновления скрытого поля с данными билетов
function updateTicketTypesHiddenField() {
    const hiddenField = document.getElementById('ticketTypesHidden');
    if (!hiddenField) {
        return;
    }

    const rows = document.querySelectorAll('#ticketTable tbody tr');
    let ticketData = [];

    rows.forEach(row => {
        const nameInput = row.querySelector('input[name="ticket_name[]"]');
        const priceInput = row.querySelector('input[name="ticket_price[]"]');
        const quantityInput = row.querySelector('input[name="ticket_quantity[]"]');

        if (nameInput && priceInput && quantityInput) {
            const name = nameInput.value.trim();
            const price = priceInput.value.trim();
            const quantity = quantityInput.value.trim();

            if (name && price && quantity) {
                ticketData.push(`${name}:${price}:${quantity}`);
            }
        }
    });

    hiddenField.value = ticketData.join('\n');
}

// Функция для валидации целых чисел
function validateIntegerInput(input) {
    const value = input.value.trim();
    const numericValue = parseFloat(value);
    
    if (value === '' || (Number.isInteger(numericValue) && numericValue >= 0)) {
        input.classList.remove('is-invalid');
        return true;
    } else {
        input.classList.add('is-invalid');
        return false;
    }
}

// Функция для проверки наличия хотя бы одного типа билета
function validateTicketTypes() {
    const rows = document.querySelectorAll('#ticketTable tbody tr');
    let hasValidTicket = false;

    rows.forEach(row => {
        const nameInput = row.querySelector('input[name="ticket_name[]"]');
        const priceInput = row.querySelector('input[name="ticket_price[]"]');
        const quantityInput = row.querySelector('input[name="ticket_quantity[]"]');

        if (nameInput && priceInput && quantityInput) {
            const name = nameInput.value.trim();
            const price = priceInput.value.trim();
            const quantity = quantityInput.value.trim();

            if (name && price && quantity) {
                hasValidTicket = true;
            }
        }
    });

    return hasValidTicket;
}

// Функция для проверки наличия одновременно бесплатных и платных билетов
function validateFreeAndPaidTickets() {
    const priceInputs = document.querySelectorAll('input[name="ticket_price[]"]');
    let hasFreeTickets = false;
    let hasPaidTickets = false;

    priceInputs.forEach(input => {
        const priceValue = input.value.trim();
        if (priceValue) {
            try {
                const price = parseFloat(priceValue.replace(",", "."));
                if (price === 0) {
                    hasFreeTickets = true;
                } else {
                    hasPaidTickets = true;
                }
            } catch (e) {
                // Игнорируем ошибки парсинга
            }
        }
    });

    return { hasFreeTickets, hasPaidTickets };
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Добавляем обработчик для кнопки добавления строки
    document.getElementById('addTicketRow').addEventListener('click', function() {
        addTicketRow();
        updateTicketTypesHiddenField();
        setupPriceFieldHandlers();
        checkFreeTickets();
    });

    // Добавляем обработчики удаления для существующих строк
    document.querySelectorAll('.remove-ticket-row').forEach(button => {
        button.addEventListener('click', function() {
            this.closest('tr').remove();
            updateTicketTypesHiddenField();
            checkFreeTickets();
        });
    });

    // Добавляем обработчики валидации для полей цены и количества
    document.querySelectorAll('#ticketTable tbody').forEach(tbody => {
        tbody.addEventListener('input', function(e) {
            const target = e.target;
            if (target.matches('input[name="ticket_price[]"], input[name="ticket_quantity[]"]')) {
                validateIntegerInput(target);
                updateTicketTypesHiddenField();
            }
        });
    });

    // Добавляем обработчик для обновления скрытого поля при изменении данных
    const tableBody = document.querySelector('#ticketTable tbody');
    if (tableBody) {
        tableBody.addEventListener('input', updateTicketTypesHiddenField);
    }

    // Инициализируем скрытое поле при загрузке
    updateTicketTypesHiddenField();

    // Добавляем первую пустую строку, если таблица пустая
    if (document.querySelectorAll('#ticketTable tbody tr').length === 0) {
        addTicketRow();
    }

    // Настраиваем обработчики для полей цены
    setupPriceFieldHandlers();

    // Проверяем наличие бесплатных билетов при загрузке страницы
    checkFreeTickets();
});

// Функция для проверки наличия бесплатных билетов и обновления чекбоксов
function checkFreeTickets() {
    const priceInputs = document.querySelectorAll('input[name="ticket_price[]"]');
    let hasFreeTickets = false;

    priceInputs.forEach(input => {
        const priceValue = input.value.trim();
        if (priceValue) {
            try {
                const price = parseFloat(priceValue.replace(",", "."));
                if (price === 0) {
                    hasFreeTickets = true;
                }
            } catch (e) {
                // Игнорируем ошибки парсинга
            }
        }
    });

    // Обновляем состояние чекбоксов
    const allowBookingCheckbox = document.getElementById('id_allow_booking_without_payment');
    const allowPlatformRequestsCheckbox = document.getElementById('id_allow_platform_requests');

    if (allowBookingCheckbox) {
        allowBookingCheckbox.disabled = hasFreeTickets;
        if (hasFreeTickets) {
            allowBookingCheckbox.checked = false;
        }
    }

    if (allowPlatformRequestsCheckbox) {
        allowPlatformRequestsCheckbox.disabled = hasFreeTickets;
        if (hasFreeTickets) {
            allowPlatformRequestsCheckbox.checked = false;
        }
    }
}

// Добавляем обработчики для каждого поля цены отдельно
function setupPriceFieldHandlers() {
    document.querySelectorAll('input[name="ticket_price[]"]').forEach(input => {
        input.addEventListener('blur', function() {
            const priceValue = this.value.trim();
            if (priceValue) {
                try {
                    const price = parseFloat(priceValue.replace(",", "."));
                    if (price === 0) {
                        // Если цена стала 0, сразу убираем галочки
                        const allowBookingCheckbox = document.getElementById('id_allow_booking_without_payment');
                        const allowPlatformRequestsCheckbox = document.getElementById('id_allow_platform_requests');

                        if (allowBookingCheckbox) {
                            allowBookingCheckbox.checked = false;
                        }

                        if (allowPlatformRequestsCheckbox) {
                            allowPlatformRequestsCheckbox.checked = false;
                        }
                    }
                } catch (e) {
                    // Игнорируем ошибки парсинга
                }
            }
            checkFreeTickets(); // Полная проверка всех билетов
        });
    });
}

// Функция для проверки перед отправкой формы
function validateForm(event) {
    let isValid = true;

    // Проверяем все поля цены и количества
    document.querySelectorAll('input[name="ticket_price[]"], input[name="ticket_quantity[]"]').forEach(input => {
        if (!validateIntegerInput(input)) {
            isValid = false;
        }
    });

    // Проверяем наличие хотя бы одного типа билета
    if (!validateTicketTypes()) {
        isValid = false;
        alert('Вы должны добавить хотя бы один тип билета со всеми заполненными полями');
    }

    // Проверяем, что нет одновременно бесплатных и платных билетов
    const { hasFreeTickets, hasPaidTickets } = validateFreeAndPaidTickets();
    if (hasFreeTickets && hasPaidTickets) {
        isValid = false;
        alert('Невозможно создать мероприятие с бесплатными и платными билетами одновременно.');
    }

    if (!isValid) {
        event.preventDefault();
    }
}

// Добавляем обработчик для проверки перед отправкой формы
const form = document.querySelector('form');
if (form) {
    form.addEventListener('submit', validateForm);
}