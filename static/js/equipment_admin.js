document.addEventListener('DOMContentLoaded', function() {
    // Находим элементы DOM
    const equipmentField = document.getElementById('id_equipment');
    const equipmentItemsContainer = document.createElement('div');
    equipmentItemsContainer.id = 'equipment-items-container';
    
    // Устанавливаем стили для контейнера
    equipmentItemsContainer.style.marginTop = '15px';
    equipmentItemsContainer.style.padding = '10px';
    equipmentItemsContainer.style.border = '1px solid #ddd';
    equipmentItemsContainer.style.borderRadius = '4px';
    equipmentItemsContainer.style.backgroundColor = '#fff';
    equipmentItemsContainer.style.minHeight = '300px';
    equipmentItemsContainer.style.maxHeight = '400px';
    equipmentItemsContainer.style.overflowY = 'auto';

    // Вставляем контейнер после поля equipment
    if (equipmentField) {
        equipmentField.parentNode.insertBefore(equipmentItemsContainer, equipmentField.nextSibling);
    }

    // Получаем ID текущей площадки из URL
    const pathParts = window.location.pathname.split('/');
    // URL выглядит как /admin/venues/venue/47/change/, поэтому ID площадки - это pathParts[4]
    const venueId = pathParts[4];

    // Функция для загрузки элементов оборудования
    function loadEquipmentItems() {
        // Получаем выбранные категории оборудования
        const selectedOptions = Array.from(equipmentField.selectedOptions).map(option => option.value);

        if (selectedOptions.length === 0) {
            equipmentItemsContainer.innerHTML = '<p>Выберите категории оборудования</p>';
            return;
        }

        // Показываем загрузку
        equipmentItemsContainer.innerHTML = '<p>Загрузка...</p>';

        // Создаем обещания для загрузки элементов каждой выбранной категории
        const promises = selectedOptions.map(categoryId =>
            fetch(`/venues/get_equipment_items/?category_id=${categoryId}`)
                .then(response => response.json())
                .then(data => {
                    // Добавляем category_id к каждому элементу
                    return data.map(item => ({...item, category_id: categoryId}));
                })
        );

        // Ожидаем выполнения всех запросов
        Promise.all(promises)
            .then(results => {
                // Объединяем все результаты
                const allItems = results.flat();

                if (allItems.length === 0) {
                    equipmentItemsContainer.innerHTML = '<p>Нет элементов оборудования для выбранных категорий</p>';
                    return;
                }

                // Получаем выбранные элементы для текущей площадки
                fetch(`/venues/venue/${venueId}/get_equipment_items/`)
                    .then(response => response.json())
                    .then(selectedItems => {
                        // Создаем чекбоксы для всех элементов оборудования
                        let html = '<h4 style="color: black; margin-bottom: 15px;">Элементы оборудования:</h4>';
                        html += '<div style="max-height: 300px; overflow-y: auto; padding: 5px;">';

                        // Группируем элементы по категориям
                        const itemsByCategory = {};
                        allItems.forEach(item => {
                            if (!itemsByCategory[item.category_id]) {
                                itemsByCategory[item.category_id] = [];
                            }
                            itemsByCategory[item.category_id].push(item);
                        });

                        // Отображаем элементы по категориям
                        for (const [categoryId, items] of Object.entries(itemsByCategory)) {
                            const categoryName = equipmentField.querySelector(`option[value="${categoryId}"]`).text;
                            html += `<div style="margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px;">`;
                            html += `<h5 style="margin-bottom: 10px; color: black;">${categoryName}</h5>`;

                            html += '<div style="display: grid; grid-template-columns: 1fr; gap: 5px;">';

                            items.forEach(item => {
                                const isChecked = selectedItems.some(selected => selected.id === item.id);
                                html += `<div style="display: flex; align-items: center;">`;
                                html += `<input type="checkbox" name="equipment_items" value="${item.id}" id="item_${item.id}" ${isChecked ? 'checked' : ''} style="margin-right: 8px;">`;
                                html += `<label for="item_${item.id}" style="color: black; margin: 0;">${item.name}</label>`;
                                html += `</div>`;
                            });

                            html += '</div>';
                            html += `</div>`;
                        }

                        html += '</div>';
                        equipmentItemsContainer.innerHTML = html;

                        // Добавляем обработчики изменений для всех чекбоксов
                        document.querySelectorAll('input[name="equipment_items"]').forEach(checkbox => {
                            checkbox.addEventListener('change', function() {
                                const equipmentId = this.value;
                                const isChecked = this.checked;

                                // Отправляем данные на сервер
                                fetch('/venues/save_venue_equipment/', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/x-www-form-urlencoded',
                                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                                    },
                                    body: `venue_id=${venueId}&equipment_id=${equipmentId}&is_checked=${isChecked}`
                                })
                                .then(response => response.json())
                                .then(data => {
                                    if (!data.success) {
                                        console.error('Ошибка при сохранении:', data.error);
                                        // Возвращаем чекбокс в исходное состояние
                                        this.checked = !isChecked;
                                    }
                                })
                                .catch(error => {
                                    console.error('Ошибка:', error);
                                    // Возвращаем чекбокс в исходное состояние
                                    this.checked = !isChecked;
                                });
                            });
                        });
                    })
                    .catch(error => {
                        console.error('Ошибка при загрузке выбранных элементов:', error);
                        equipmentItemsContainer.innerHTML = '<p>Ошибка загрузки выбранных элементов оборудования</p>';
                    });
            })
            .catch(error => {
                console.error('Ошибка:', error);
                equipmentItemsContainer.innerHTML = '<p>Ошибка загрузки элементов оборудования</p>';
            });
    }

    // Добавляем обработчик изменения выбора категорий оборудования
    if (equipmentField) {
        equipmentField.addEventListener('change', function() {
            loadEquipmentItems();
        });

        // Загружаем элементы для выбранных категорий при загрузке страницы
        loadEquipmentItems();
    }
});