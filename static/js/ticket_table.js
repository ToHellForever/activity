// Функция для добавления новой строки билета
function addTicketRow() {
    const tableBody = document.querySelector('#ticketTable tbody');
    const newRow = document.createElement('tr');
    
    newRow.innerHTML = `
        <td><input type="text" name="ticket_name[]" class="form-control" required></td>
        <td><input type="number" name="ticket_price[]" step="0.01" min="0" class="form-control" required></td>
        <td><input type="number" name="ticket_quantity[]" min="0" class="form-control" required></td>
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
    
    document.getElementById('ticketTypesHidden').value = ticketData.join('\n');
    console.log("Updated ticket data:", document.getElementById('ticketTypesHidden').value);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Добавляем обработчик для кнопки добавления строки
    document.getElementById('addTicketRow').addEventListener('click', function() {
        addTicketRow();
        updateTicketTypesHiddenField();
    });
    
    // Добавляем обработчики удаления для существующих строк
    document.querySelectorAll('.remove-ticket-row').forEach(button => {
        button.addEventListener('click', function() {
            this.closest('tr').remove();
            updateTicketTypesHiddenField();
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
});