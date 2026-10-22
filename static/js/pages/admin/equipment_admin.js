document.addEventListener('DOMContentLoaded', function() {
    const equipmentField = document.getElementById('id_equipment');
    if (!equipmentField) {
        return;
    }

    const equipmentItemsContainer = document.createElement('div');
    equipmentItemsContainer.id = 'equipment-items-container';
    equipmentItemsContainer.style.marginTop = '15px';
    equipmentItemsContainer.style.padding = '10px';
    equipmentItemsContainer.style.border = '1px solid #ddd';
    equipmentItemsContainer.style.borderRadius = '4px';
    equipmentItemsContainer.style.backgroundColor = '#fff';
    equipmentItemsContainer.style.minHeight = '300px';
    equipmentItemsContainer.style.maxHeight = '400px';
    equipmentItemsContainer.style.overflowY = 'auto';
    equipmentField.parentNode.insertBefore(equipmentItemsContainer, equipmentField.nextSibling);

    const equipmentItemsForm = document.createElement('div');
    equipmentItemsForm.hidden = true;
    equipmentField.form.appendChild(equipmentItemsForm);

    const pathParts = window.location.pathname.split('/');
    const venueId = pathParts[4];
    const isExistingVenue = venueId && !isNaN(venueId);
    const selectedItemIds = new Set();
    let categoryRequestId = 0;

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, function(character) {
            return {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            }[character];
        });
    }

    function updateSubmittedItems() {
        equipmentItemsForm.innerHTML = '<input type="hidden" name="equipment_items_present" value="1">';
        selectedItemIds.forEach(itemId => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'equipment_items';
            input.value = itemId;
            equipmentItemsForm.appendChild(input);
        });
    }

    function loadEquipmentItems() {
        const requestId = ++categoryRequestId;
        const selectedCategories = Array.from(equipmentField.selectedOptions).map(option => option.value);

        if (selectedCategories.length === 0) {
            equipmentItemsContainer.innerHTML = '<p>Выберите категории оборудования</p>';
            return;
        }

        equipmentItemsContainer.innerHTML = '<p>Загрузка...</p>';
        const promises = selectedCategories.map(categoryId =>
            fetch(`/venues/get_equipment_items/?category_id=${encodeURIComponent(categoryId)}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    return response.json();
                })
                .then(items => items.map(item => ({...item, category_id: categoryId})))
        );

        Promise.all(promises)
            .then(results => {
                if (requestId !== categoryRequestId) {
                    return;
                }

                const allItems = results.flat();
                if (allItems.length === 0) {
                    equipmentItemsContainer.innerHTML = '<p>Нет элементов оборудования для выбранных категорий</p>';
                    return;
                }

                let html = '<h4 style="color: black; margin-bottom: 15px;">Элементы оборудования:</h4>';
                html += '<div style="max-height: 300px; overflow-y: auto; padding: 5px;">';

                const itemsByCategory = {};
                allItems.forEach(item => {
                    if (!itemsByCategory[item.category_id]) {
                        itemsByCategory[item.category_id] = [];
                    }
                    itemsByCategory[item.category_id].push(item);
                });

                for (const [categoryId, items] of Object.entries(itemsByCategory)) {
                    const categoryOption = Array.from(equipmentField.options)
                        .find(option => option.value === categoryId);
                    const categoryName = categoryOption ? categoryOption.text : '';
                    html += '<div style="margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px;">';
                    html += `<h5 style="margin-bottom: 10px; color: black;">${escapeHtml(categoryName)}</h5>`;
                    html += '<div style="display: grid; grid-template-columns: 1fr; gap: 5px;">';

                    items.forEach(item => {
                        const itemId = String(item.id);
                        const isChecked = selectedItemIds.has(itemId);
                        html += '<div style="display: flex; align-items: center;">';
                        html += `<input type="checkbox" value="${escapeHtml(itemId)}" id="item_${escapeHtml(itemId)}" ${isChecked ? 'checked' : ''} style="margin-right: 8px;">`;
                        html += `<label for="item_${escapeHtml(itemId)}" style="color: black; margin: 0;">${escapeHtml(item.name)}</label>`;
                        html += '</div>';
                    });

                    html += '</div></div>';
                }

                html += '</div>';
                equipmentItemsContainer.innerHTML = html;
            })
            .catch(error => {
                if (requestId !== categoryRequestId) {
                    return;
                }
                console.error('Ошибка загрузки элементов оборудования:', error);
                equipmentItemsContainer.innerHTML = '<p>Ошибка загрузки элементов оборудования</p>';
            });
    }

    equipmentItemsContainer.addEventListener('change', function(event) {
        if (event.target.matches('input[type="checkbox"]')) {
            const itemId = event.target.value;
            if (event.target.checked) {
                selectedItemIds.add(itemId);
            } else {
                selectedItemIds.delete(itemId);
            }
            updateSubmittedItems();
        }
    });

    fetch(isExistingVenue
        ? `/venues/venue/${venueId}/get_equipment_items/`
        : '/venues/venue/add/get_equipment_items/')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(selectedItems => {
            selectedItems.forEach(item => selectedItemIds.add(String(item.id)));
            updateSubmittedItems();
            loadEquipmentItems();
        })
        .catch(error => {
            console.error('Ошибка при загрузке выбранных элементов:', error);
            equipmentItemsContainer.innerHTML = '<p>Ошибка загрузки выбранных элементов оборудования</p>';
        });

    equipmentField.addEventListener('change', loadEquipmentItems);
});
