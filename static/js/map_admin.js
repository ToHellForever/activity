// Инициализация Яндекс Карт для админ-панели

document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, что находимся на странице редактирования площадки
    if (document.getElementById('venue_form')) {
        // API ключ Яндекс Карт
        const apiKey = 'f4f22e64-c72d-4d41-a5ad-76b4f6367b75';
        
        // Создаем скрипт для загрузки API Яндекс Карт
        const script = document.createElement('script');
        script.src = `https://api-maps.yandex.ru/2.1/?apikey=${apiKey}&lang=ru_RU`;
        script.async = true;
        script.onload = initMap;
        document.head.appendChild(script);
    }
});

function initMap() {
    // Проверяем, что API Яндекс Карт загружен
    if (typeof ymaps === 'undefined') {
        console.error('Яндекс Карты не загружены');
        return;
    }
    
    // Находим все поля формы заранее
    const addressField = document.querySelector('#id_address');
    const cityField = document.querySelector('#id_city');
    const districtField = document.querySelector('#id_district');
    const metroField = document.querySelector('#id_metro');
    const latitudeField = document.querySelector('#id_latitude');
    const longitudeField = document.querySelector('#id_longitude');
    
    // Ждем полной загрузки API
    ymaps.ready(function() {
        // Получаем элементы DOM
        const mapContainer = document.createElement('div');
        mapContainer.id = 'map-container';
        mapContainer.style.width = '100%';
        mapContainer.style.height = '400px';
        mapContainer.style.marginBottom = '20px';
        
        // Находим поле адреса
        const addressField = document.querySelector('#id_address');
        if (!addressField) {
            console.error('Поле адреса не найдено');
            return;
        }
        
        // Находим поля координат
        const latitudeField = document.querySelector('#id_latitude');
        const longitudeField = document.querySelector('#id_longitude');
        
        // Вставляем контейнер для карты перед полем адреса
        addressField.parentNode.insertBefore(mapContainer, addressField);
        
        // Получаем текущие координаты из полей (по умолчанию - Новосибирск)
        let currentLat = latitudeField && latitudeField.value ? parseFloat(latitudeField.value) : 55.030204;
        let currentLon = longitudeField && longitudeField.value ? parseFloat(longitudeField.value) : 82.920430;
        
        // Инициализируем карту
        const map = new ymaps.Map('map-container', {
            center: [currentLat, currentLon],
            zoom: 14
        });
        
        // Создаем метку
        let placemark = new ymaps.Placemark([currentLat, currentLon], {
            balloonContent: 'Перетащите метку для изменения местоположения'
        }, {
            preset: 'islands#violetDotIconWithCaption',
            draggable: true
        });
        
        map.geoObjects.add(placemark);
        
        // Обработчик клика на карте
        map.events.add('click', function(e) {
            const coords = e.get('coords');
            
            // Обновляем позицию метки
            placemark.geometry.setCoordinates(coords);
            
            // Обновляем скрытые поля координат
            if (latitudeField) latitudeField.value = coords[0];
            if (longitudeField) longitudeField.value = coords[1];
            
            // Обновляем адрес через геокодер
            updateAddressFromCoords(coords[0], coords[1]);
        });
        
        // Обработчик перетаскивания метки
        placemark.events.add('dragend', function(e) {
            const newCoords = placemark.geometry.getCoordinates();
            
            // Обновляем скрытые поля координат
            if (latitudeField) latitudeField.value = newCoords[0];
            if (longitudeField) longitudeField.value = newCoords[1];
            
            // Обновляем адрес через геокодер
            updateAddressFromCoords(newCoords[0], newCoords[1]);
        });
        
        // Функция для обновления адреса по координатам
        function updateAddressFromCoords(lat, lon) {
            ymaps.geocode([lon, lat], { kind: 'house' }).then(
                function(res) {
                    if (res.geoObjects.getLength() > 0) {
                        const firstGeoObject = res.geoObjects.get(0);
                        
                        // Получаем полный адрес
                        const address = firstGeoObject.getAddressLine();
                        
                        // Получаем детализированную информацию о компонентах адреса
                        const metaData = firstGeoObject.properties.get('metaDataProperty.GeocoderMetaData');
                        
                        // Обновляем поле адреса
                        if (addressField) addressField.value = address;
                        
                        // Обновляем город
                        if (cityField) cityField.value = 'Новосибирск';
                        
                        // Обновляем район и метро через детализированные данные
                        updateAddressComponents(metaData);
                    } else {
                        console.warn('Не удалось получить адрес для данных координат');
                        // Попробуем получить хотя бы приблизительный адрес
                        ymaps.geocode([lon, lat]).then(
                            function(res) {
                                if (res.geoObjects.getLength() > 0) {
                                    const firstGeoObject = res.geoObjects.get(0);
                                    if (addressField) addressField.value = firstGeoObject.getAddressLine();
                                }
                            }
                        );
                    }
                }
            )
            .catch(function(err) {
                console.error('Ошибка геокодирования:', err);
            });
        }
        
        // Функция для обновления компонентов адреса
        function updateAddressComponents(metaData) {
            if (!metaData) return;
            
            // Очищаем предыдущие значения
            if (districtField) districtField.value = '';
            if (metroField) metroField.value = '';
            
            // Пробуем получить район из компонентов адреса
            if (metaData.Address && metaData.Address.Components) {
                const components = metaData.Address.Components;
                
                // Ищем район
                const districtComponent = components.find(c => c.kind === 'district');
                if (districtComponent && districtField) {
                    districtField.value = districtComponent.name;
                }
                
                // Ищем метро
                const metroComponent = components.find(c => c.kind === 'metro');
                if (metroComponent && metroField) {
                    metroField.value = metroComponent.name;
                }
            }
        }
        
        // Обработчик изменения адреса
        if (addressField) {
            addressField.addEventListener('change', function() {
                const address = this.value;
                
                // Геокодируем адрес
                ymaps.geocode(address, { results: 1 }).then(
                    function(res) {
                        if (res.geoObjects.getLength() > 0) {
                            const firstGeoObject = res.geoObjects.get(0);
                            const coords = firstGeoObject.geometry.getCoordinates();
                            
                            // Обновляем метку на карте
                            placemark.geometry.setCoordinates(coords);
                            
                            // Обновляем скрытые поля координат
                            if (latitudeField) latitudeField.value = coords[0];
                            if (longitudeField) longitudeField.value = coords[1];
                            
                            // Центрируем карту
                            map.setCenter(coords, 16);
                        } else {
                            console.warn('Адрес не найден');
                        }
                    }
                )
                .catch(function(err) {
                    console.error('Ошибка геокодирования:', err);
                });
            });
        }
    });
}