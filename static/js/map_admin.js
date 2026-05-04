document.addEventListener('DOMContentLoaded', function() {
    // Ищем форму площадки по ID
    const venueForm = document.getElementById('venue_form');
    if (!venueForm) return;

    // API ключ Яндекс Карт
    const apiKey = 'f4f22e64-c72d-4d41-a5ad-76b4f6367b75';
    
    // Загружаем API Яндекс Карт
    const script = document.createElement('script');
    script.src = `https://api-maps.yandex.ru/2.1/?apikey=${apiKey}&lang=ru_RU`;
    script.async = true;
    script.onload = () => ymaps.ready(initMap);
    document.head.appendChild(script);
});

function initMap() {
    // --- 1. Ищем все поля формы ---
    const $fields = {
        address: document.querySelector('#id_address'),
        city: document.querySelector('#id_city'),
        district: document.querySelector('#id_district'),
        metro: document.querySelector('#id_metro'),
        latitude: document.querySelector('#id_latitude'),
        longitude: document.querySelector('#id_longitude')
    };

    // Проверяем наличие обязательных полей
    if (!$fields.address || !$fields.latitude || !$fields.longitude) {
        console.error('Не найдены обязательные поля формы');
        return;
    }

    // --- 2. Создаем контейнер для карты ---
    const mapContainer = document.createElement('div');
    mapContainer.id = 'map-container';
    mapContainer.style.width = '100%';
    mapContainer.style.height = '400px';
    mapContainer.style.marginBottom = '20px';
    
    // Вставляем карту перед полем адреса
    $fields.address.parentNode.insertBefore(mapContainer, $fields.address);

    // --- 3. Получаем начальные координаты ---
    const defaultLat = 55.030204; // Новосибирск (центр)
    const defaultLon = 82.920430;
    
    let currentLat = $fields.latitude.value ? parseFloat($fields.latitude.value) : defaultLat;
    let currentLon = $fields.longitude.value ? parseFloat($fields.longitude.value) : defaultLon;

    // --- 4. Инициализируем карту и метку ---
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

    // --- 5. Функция обновления полей из геокодера ---
    function updateFieldsFromGeocoder(lat, lon) {
        ymaps.geocode([lat, lon], { results: 1 }).then(res => {
            if (res.geoObjects.getLength()) {
                const geoObject = res.geoObjects.get(0);
                const metaData = geoObject.properties.get('metaDataProperty.GeocoderMetaData');
                
                // Заполняем адрес и координаты (всегда)
                $fields.address.value = geoObject.getAddressLine();
                $fields.latitude.value = lat.toFixed(6);
                $fields.longitude.value = lon.toFixed(6);
                
                // Заполняем доп. поля (если есть данные)
                if (metaData) {
                    const details = metaData.AddressDetails?.Country;
                    if (details) {
                        // Город
                        const cityObj = details.AdministrativeArea?.Locality;
                        if (cityObj && $fields.city) {
                            $fields.city.value = cityObj.LocalityName;
                        }
                        // Район
                        const districtObj = details.AdministrativeArea?.SubAdministrativeArea;
                        if (districtObj && $fields.district) {
                            $fields.district.value = districtObj.SubAdministrativeAreaName;
                        }
                    }
                    // Метро (ищем в Components)
                    const metroComp = (metaData.Address?.Components || []).find(c => c.kind === 'metro');
                    if (metroComp && $fields.metro) {
                        $fields.metro.value = metroComp.name;
                    }
                }
            }
        }).catch(err => console.error('Геокодер:', err));
    }

    // --- 6. Обработчики событий ---
    
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