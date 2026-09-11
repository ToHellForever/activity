// === ADMIN PARTNER CHANGE FORM ===

function openAssignPackageModal() {
    document.getElementById('assign-package-modal').style.display = 'flex';
}
function closeAssignPackageModal() {
    document.getElementById('assign-package-modal').style.display = 'none';
}

// Установить даты по умолчанию
document.addEventListener('DOMContentLoaded', function() {
    var now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    document.getElementById('assign-start').value = now.toISOString().slice(0,16);
    
    var end = new Date();
    end.setDate(end.getDate() + 30);
    end.setMinutes(end.getMinutes() - end.getTimezoneOffset());
    document.getElementById('assign-end').value = end.toISOString().slice(0,16);
});
