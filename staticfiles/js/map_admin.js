document.addEventListener('DOMContentLoaded', function() {
    console.log('map_admin.js loaded');
    
    // Ищем форму площадки или мероприятия по ID
    const venueForm = document.getElementById('venue_form');
    const eventForm = document.getElementById('event_form');
    console.log('Found venue_form:', venueForm);
    console.log('Found event_form:', eventForm);
    
    if (!eventForm && !venueForm) {
        console.log('No venue or event form found, exiting');
        return;
    }

    // Добавляем стили для поисковой строки Яндекс.Карт
    const style = document.createElement('style');
    style.textContent = `
        .ymap-container .ymaps-2-1-79-searchbox-input__input {
            color: black !important;
            background-color: white !important;
            border: 1px solid #ccc !important;
            opacity: 1 !important;
        }
        .ymap-container .ymaps-2-1-79-searchbox-popup-item-title {
            color: black !important;
        }
        .ymap-container .ymaps-2-1-79-searchbox-popup-item-text {
            color: black !important;
        }
        .ymap-container .ymaps-2-1-79-searchbox-view__input-wrapper {
            background-color: white !important;
        }
    `;
    document.head.appendChild(style);

    // API ключ Яндекс Карт
    const apiKey = 'f4f22e64-c72d-4d41-a5ad-76b4f6367b75';
    
    // Загружаем API Яндекс Карт
    const script = document.createElement('script');
    script.src = `https://api-maps.yandex.ru/2.1/?apikey=${apiKey}&lang=ru_RU`;
    script.async = true;
    script.onload = () => {
        console.log('YMaps API loaded');
        ymaps.ready(initMap);
    };
    script.onerror = () => {
        console.error('Failed to load YMaps API');
    };
    document.head.appendChild(script);
});

function initMap() {
    console.log('initMap called');
    // --- 1. Ищем все поля формы ---
    const $fields = {
        address: document.querySelector('#id_address'),
        city: document.querySelector('#id_city'),
        district: document.querySelector('#id_district'),
        metro: document.querySelector('#id_metro'),
        latitude: document.querySelector('#id_latitude'),
        longitude: document.querySelector('#id_longitude')
    };
    console.log('Found fields:', $fields);
    // Проверяем наличие обязательных полей
    if (!$fields.address || !$fields.latitude || !$fields.longitude) {
        console.error('Не найдены обязательные поля формы');
        return;
    }

    // --- 2. Скрываем скрытые поля в UI (если они не HiddenInput) ---
    if ($fields.latitude && $fields.latitude.style.display !== 'none') {
        $fields.latitude.style.display = 'none';
    }
    if ($fields.longitude && $fields.longitude.style.display !== 'none') {
        $fields.longitude.style.display = 'none';
    }
    console.log('Creating map container...');
    // --- 3. Создаем контейнер для карты ---
    const mapContainer = document.createElement('div');
    mapContainer.id = 'map-container';
    mapContainer.style.width = '100%';
    mapContainer.style.height = '400px';
    mapContainer.style.marginBottom = '20px';
    mapContainer.style.border = '1px solid #ddd';
    mapContainer.style.borderRadius = '4px';
    console.log('Inserting map container before address field...');
    // Вставляем карту перед полем адреса
    $fields.address.parentNode.insertBefore(mapContainer, $fields.address);
    console.log('Map container inserted. ID:', mapContainer.id);
    console.log('Getting coordinates...');

    // --- ✅ ИСПРАВЛЕНО: переместили объявление перед использованием ---
    const defaultLat = 55.030204; 
    const defaultLon = 82.920430;
    let currentLat = $fields.latitude.value ? parseFloat($fields.latitude.value) : defaultLat;
    let currentLon = $fields.longitude.value ? parseFloat($fields.longitude.value) : defaultLon;

    console.log('Coordinates:', currentLat, currentLon); // Теперь всё ок
    console.log('Initializing ymaps.Map...');
    console.log('ymaps object:', ymaps);
    console.log('ymaps.Map:', ymaps.Map);
    // --- 5. Инициализируем карту и метку ---
    const map = new ymaps.Map('map-container', {
        center: [currentLat, currentLon],
        zoom: 14,
        controls: ['searchControl'] 
    });

    const placemark = new ymaps.Placemark([currentLat, currentLon], {}, {
        preset: 'islands#violetDotIconWithCaption',
        draggable: true
    });
    
    map.geoObjects.add(placemark);

    // --- 6. Функция обновления полей из геокодера ---
    function updateFieldsFromGeocoder(lat, lon) {
        ymaps.geocode([lat, lon], { results: 1 }).then(res => {
            if (res.geoObjects.getLength()) {
                const geoObject = res.geoObjects.get(0);
                const metaData = geoObject.properties.get('metaDataProperty.GeocoderMetaData');

                // Заполняем адрес и координаты (всегда)
                $fields.address.value = geoObject.getAddressLine();
                $fields.latitude.value = lat.toFixed(6);
                $fields.longitude.value = lon.toFixed(6);

                // Устанавливаем флаг, что данные о местоположении обновлены
                const placeDataField = document.querySelector('#id_place_data');
                if (placeDataField) {
                    placeDataField.dataset.updated = 'true';
                }

                // Сбросим доп. поля перед заполнением
                if ($fields.city) $fields.city.value = '';
                if ($fields.district) $fields.district.value = '';
                if ($fields.metro) $fields.metro.value = '';

                // Заполняем доп. поля (ищем в Components)
                let metroFound = false;
                if (metaData && metaData.Address && metaData.Address.Components) {
                    metaData.Address.Components.forEach(comp => {
                        if (comp.kind === 'locality' && $fields.city) {
                            $fields.city.value = comp.name;
                        }
                        if (comp.kind === 'district' && $fields.district) {
                            $fields.district.value = comp.name;
                        }
                        if (comp.kind === 'metro' && $fields.metro) {
                            $fields.metro.value = comp.name;
                            metroFound = true;
                        }
                    });
                }

                // Если метро не найдено в адресе, ищем ближайшую станцию
                if ($fields.metro && !metroFound) {
                    ymaps.geocode([lat, lon], {
                        kind: 'metro',
                        results: 1,
                        radius: 1000 // радиус поиска в метрах
                    }).then(metroRes => {
                        if (metroRes.geoObjects.getLength()) {
                            const metroGeo = metroRes.geoObjects.get(0);
                            $fields.metro.value = metroGeo.properties.get('name');
                        }
                    }).catch(err => console.error('Поиск метро:', err));
                }
            }
        }).catch(err => console.error('Геокодер:', err));
    }

    // --- 7. Обработчики событий ---
    
    // Клик по карте
    map.events.add('click', e => {
        const coords = e.get('coords'); // [lat, lon]
        placemark.geometry.setCoordinates(coords);
        updateFieldsFromGeocoder(coords[0], coords[1]);
        map.setCenter(coords);
    });

    // Перетаскивание метки
    placemark.events.add('dragend', () => {
        const coords = placemark.geometry.getCoordinates();
        updateFieldsFromGeocoder(coords[0], coords[1]);
        map.setCenter(coords);
    });
}