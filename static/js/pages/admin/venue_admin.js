// === VENUE ADMIN ===

document.addEventListener('DOMContentLoaded', function() {
    const equipmentGroup = document.querySelector('#equipment_items_group fieldset.module');
    if (equipmentGroup) {
        equipmentGroup.style.minHeight = '300px';
        equipmentGroup.style.maxHeight = '400px';
        equipmentGroup.style.overflowY = 'auto';
        equipmentGroup.style.padding = '10px';
        equipmentGroup.style.border = '1px solid #dee2e6';
        equipmentGroup.style.borderRadius = '5px';
        equipmentGroup.style.backgroundColor = '#fff';
    }
});
