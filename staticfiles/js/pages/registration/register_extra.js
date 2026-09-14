// === REGISTER EXTRA ===

// Обработка отображения имени файла логотипа
document.getElementById('id_logo').addEventListener('change', function() {
    const filename = this.files.length > 0 ? this.files[0].name : '';
    document.getElementById('logo-filename').textContent = filename;
});

// Обработка отображения имени файла документов
document.getElementById('documents-upload').addEventListener('change', function() {
    const count = this.files.length;
    document.getElementById('documents-filename').textContent = count > 0 ? 'Выбрано файлов: ' + count : '';
});

// Автоопределение почтового индекса по юридическому адресу
var addressInput = document.getElementById('id_legal_address');
var postalInput = document.getElementById('id_postal_code');
if (!addressInput || !postalInput) { /* поля не найдены — пропускаем */ }
else {
    var timer = null;
    addressInput.addEventListener('blur', function() {
        clearTimeout(timer);
        timer = setTimeout(fetchPostalCode, 300);
    });
}

function fetchPostalCode() {
    var address = addressInput.value.trim();
    if (!address) return;

    fetch('https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=' + encodeURIComponent(address))
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data && data.length > 0 && data[0].address) {
                var addr = data[0].address;
                var postcode = addr.postcode || addr.postal_code || '';
                postalInput.value = postcode;
            }
        })
        .catch(function() { /* индекс не определён — останется пустым */ });
}
