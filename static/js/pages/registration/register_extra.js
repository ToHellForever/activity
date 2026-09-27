// === REGISTER EXTRA ===

// Скрипт подключается в <head> без defer — DOM ещё не построен.
// Вся работа с элементами страницы — только после DOMContentLoaded,
// иначе getElementById возвращает null и превью не работает.
document.addEventListener('DOMContentLoaded', function () {

// Максимальное число документов для загрузки (регистрация и дашборд)
var MAX_DOCUMENTS = 3;

// === Логотип: плейсхолдер <-> превью, визуально как в форме мероприятия ===
var logoInput = document.getElementById('id_logo');
var logoContainer = document.getElementById('logo-upload-container');
var logoDisplay = document.getElementById('logo-file-display');
var logoPlaceholder = document.getElementById('logo-upload-placeholder');
var logoPreviewImg = document.getElementById('logo-preview-img');
var logoFileName = document.getElementById('logo-file-name');

function setLogoState(hasFile) {
    if (!logoContainer) return;
    if (hasFile) {
        logoDisplay.style.display = 'flex';
        logoPlaceholder.style.display = 'none';
        logoContainer.classList.remove('has-no-photos');
        logoContainer.classList.add('has-photos');
    } else {
        logoDisplay.style.display = 'none';
        logoPlaceholder.style.display = 'flex';
        logoContainer.classList.add('has-no-photos');
        logoContainer.classList.remove('has-photos');
    }
}

if (logoInput && logoContainer) {
    logoInput.addEventListener('change', function () {
        var file = this.files && this.files[0];
        if (!file) {
            setLogoState(false);
            return;
        }
        var reader = new FileReader();
        reader.onload = function (e) {
            logoPreviewImg.src = e.target.result;
            logoFileName.textContent = file.name;
            setLogoState(true);
        };
        reader.readAsDataURL(file);
    });

    // «Заменить» — снова открываем выбор файла
    var logoReplaceBtn = document.getElementById('logo-replace-btn');
    if (logoReplaceBtn) {
        logoReplaceBtn.addEventListener('click', function () {
            logoInput.click();
        });
    }

    // Крестик: очищаем input и возвращаем плейсхолдер
    var logoRemoveBtn = document.getElementById('logo-remove-btn');
    if (logoRemoveBtn) {
        logoRemoveBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            logoInput.value = '';
            logoPreviewImg.src = '';
            logoFileName.textContent = '';
            setLogoState(false);
        });
    }
}

// === Документы: до 3 файлов, список как в форме мероприятия ===
var documentsInput = document.getElementById('documents-upload');
var documentsContainer = document.getElementById('documents-upload-container');
var documentsDisplay = document.getElementById('documents-file-display');
var documentsPlaceholder = document.getElementById('documents-upload-placeholder');

function setDocumentsState(hasFiles) {
    if (!documentsContainer) return;
    if (hasFiles) {
        documentsDisplay.style.display = 'flex';
        documentsPlaceholder.style.display = 'none';
        documentsContainer.classList.remove('has-no-photos');
        documentsContainer.classList.add('has-photos');
    } else {
        documentsDisplay.style.display = 'none';
        documentsPlaceholder.style.display = 'flex';
        documentsContainer.classList.add('has-no-photos');
        documentsContainer.classList.remove('has-photos');
    }
}

function renderDocumentsList() {
    documentsDisplay.innerHTML = '';
    var files = documentsInput.files;
    if (!files || files.length === 0) {
        setDocumentsState(false);
        return;
    }
    // DataTransfer позволяет пересобрать список файлов при удалении одного
    var dt = new DataTransfer();
    for (var i = 0; i < files.length; i++) {
        dt.items.add(files[i]);
        (function (index) {
            // Строка документа: иконка + имя + крестик (как программа в event_form)
            var row = document.createElement('div');
            row.style.cssText = 'position:relative; display:flex; align-items:center; gap:10px; width:100%;';

            var icon = document.createElement('div');
            icon.className = 'btn-document';
            icon.style.cssText = 'margin:0; flex-shrink:0;';
            var iconImg = document.createElement('img');
            iconImg.src = '/media/icon/document.png';
            iconImg.alt = '';
            iconImg.style.cssText = 'width:40px; height:40px; object-fit:contain;';
            icon.appendChild(iconImg);

            var name = document.createElement('span');
            name.textContent = files[index].name;
            name.style.cssText = 'font-size:12px; color:#555; word-break:break-all; flex:1; text-align:left;';

            var btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = '\u00d7';
            btn.title = 'Удалить';
            btn.className = 'program-remove-btn';
            btn.style.right = 'auto';
            btn.style.cssText += 'position:relative; flex-shrink:0;';
            btn.addEventListener('click', function () {
                var current = documentsInput.files;
                var dtRemove = new DataTransfer();
                for (var j = 0; j < current.length; j++) {
                    if (j !== index) dtRemove.items.add(current[j]);
                }
                documentsInput.files = dtRemove.files;
                renderDocumentsList();
            });

            row.appendChild(icon);
            row.appendChild(name);
            row.appendChild(btn);
            documentsDisplay.appendChild(row);
        })(i);
    }

    // Кнопка «Добавить ещё» под списком (лимит 3)
    var addMore = document.createElement('button');
    addMore.type = 'button';
    addMore.className = 'media-program-button';
    addMore.textContent = 'Добавить ещё';
    addMore.style.marginTop = '4px';
    addMore.addEventListener('click', function () {
        documentsInput.click();
    });
    documentsDisplay.appendChild(addMore);

    setDocumentsState(true);
}

if (documentsInput && documentsContainer) {
    documentsInput.addEventListener('change', function () {
        // Лимит: не больше 3 документов — лишние молча отбрасываем
        if (this.files && this.files.length > MAX_DOCUMENTS) {
            var dt = new DataTransfer();
            for (var i = 0; i < MAX_DOCUMENTS; i++) {
                dt.items.add(this.files[i]);
            }
            this.files = dt.files;
            alert('Можно загрузить не более ' + MAX_DOCUMENTS + ' документов. Оставлены первые ' + MAX_DOCUMENTS + '.');
        }
        renderDocumentsList();
    });
}

// Автоопределение почтового индекса по юридическому адресу
var addressInput = document.getElementById('id_legal_address');
var postalInput = document.getElementById('id_postal_code');
if (addressInput && postalInput) {
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

}); // end DOMContentLoaded
