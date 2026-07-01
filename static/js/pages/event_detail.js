document.addEventListener('DOMContentLoaded', function() {
    'use strict';
    
    // === ЛОГГЕР ===
    const eventId = '{{ event.id }}';
    const logPrefix = '[Event:' + eventId + ']';
    const purchaseLog = [];
    const MAX_FREE_TICKETS = 2;
    
    // === UTM-МЕТКИ ===
    function captureUtmParams() {
        const params = new URLSearchParams(window.location.search);
        const utmKeys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];
        const utmData = {};
        let hasUtm = false;
        
        utmKeys.forEach(key => {
            const value = params.get(key);
            if (value) {
                utmData[key] = value;
                hasUtm = true;
            }
        });
        
        if (hasUtm) {
            try {
                localStorage.setItem('utm_params', JSON.stringify(utmData));
                addLog('UTM-метки сохранены: ' + JSON.stringify(utmData), 'info');
            } catch(e) {}
        }
    }
    
    function getUtmParams() {
        try {
            const stored = localStorage.getItem('utm_params');
            if (stored) {
                return JSON.parse(stored);
            }
        } catch(e) {}
        return {};
    }
    
    // Захватываем UTM-метки при загрузке страницы
    captureUtmParams();
    
    // === Toast-уведомления ===
    function showToast(message, isError = true) {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) return;
        
        const toastElement = document.createElement('div');
        toastElement.className = `toast align-items-center text-white ${isError ? 'bg-danger' : 'bg-success'}`;
        toastElement.setAttribute('role', 'alert');
        toastElement.setAttribute('aria-live', 'assertive');
        toastElement.setAttribute('aria-atomic', 'true');
        
        const toastBody = document.createElement('div');
        toastBody.className = 'd-flex';
        
        const toastMessage = document.createElement('div');
        toastMessage.className = 'toast-body';
        toastMessage.textContent = message;
        
        const toastClose = document.createElement('button');
        toastClose.type = 'button';
        toastClose.className = 'btn-close btn-close-white me-2 m-auto';
        toastClose.setAttribute('data-bs-dismiss', 'toast');
        toastClose.setAttribute('aria-label', 'Close');
        
        toastBody.appendChild(toastMessage);
        toastBody.appendChild(toastClose);
        toastElement.appendChild(toastBody);
        
        toastContainer.appendChild(toastElement);
        
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: 5000
        });
        toast.show();
        
        toastElement.addEventListener('hidden.bs.toast', function() {
            toastElement.remove();
        });
    }
    
    // Определяем какие билеты бесплатные
    const freeTicketIds = [];
    document.querySelectorAll('.ticket-card').forEach(card => {
        if (parseFloat(card.dataset.ticketPrice) === 0) {
            freeTicketIds.push(card.dataset.ticketId);
        }
    });
    
    // Подсчёт уже полученных бесплатных билетов на ЭТОМ мероприятии (из localStorage)
    function getAlreadyFreeTicketsForEvent() {
        try {
            // Сначала ищем под ключом мероприятия
            const stored = localStorage.getItem('free_tickets_event_' + '{{ event.id }}');
            if (stored !== null) {
                const val = parseInt(stored);
                return isNaN(val) ? 0 : val;
            }
            // Фолбэк на старый глобальный ключ (на случай миграции)
            const oldStored = localStorage.getItem('free_tickets_purchased');
            if (oldStored !== null) {
                const val = parseInt(oldStored);
                return isNaN(val) ? 0 : val;
            }
            return 0;
        } catch(e) {
            return 0;
        }
    }
    
    function updateFreeTicketLimits() {
        const alreadyFree = getAlreadyFreeTicketsForEvent();
        const remaining = MAX_FREE_TICKETS - alreadyFree;
        
        document.querySelectorAll('.ticket-card').forEach(card => {
            const ticketId = card.dataset.ticketId;
            const input = document.getElementById('qty_' + ticketId);
            const availableSmall = card.querySelector('.available-count');
            
            if (freeTicketIds.indexOf(ticketId) !== -1 && remaining <= 0) {
                // Бесплатный билет, лимит исчерпан
                input.max = 0;
                input.value = 0;
                input.disabled = true;
                input.style.opacity = '0.5';
                if (availableSmall) {
                    availableSmall.textContent = 'Лимит бесплатных билетов исчерпан';
                    availableSmall.style.color = '#dc3545';
                }
            } else if (freeTicketIds.indexOf(ticketId) !== -1 && remaining > 0) {
                // Бесплатный билет, лимит есть — ограничиваем остатком
                const currentMax = parseInt(input.max) || 99;
                input.max = Math.min(currentMax, remaining);
                if (availableSmall) {
                    availableSmall.textContent = 'Доступно: ' + (input.max > 0 ? input.max : 0) + ' из ' + MAX_FREE_TICKETS + ' (остаток)';
                    availableSmall.style.color = '#dc3545';
                }
            } else {
                // Платный билет — без ограничений
                input.disabled = false;
                input.style.opacity = '1';
            }
        });
        
        // Обновляем корзину
        updateCartDisplay();
    }
    
    function addLog(message, type) {
        type = type || 'info';
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = timestamp + ' ' + message;
        purchaseLog.push(logEntry);
        
        console.log(logPrefix, '[' + type.toUpperCase() + ']', message);
        
        const logEl = document.getElementById('purchaseLog');
        if (logEl) {
            logEl.style.display = 'block';
            const entry = document.createElement('div');
            entry.className = 'log-entry log-' + type;
            entry.style.cssText = 'padding: 4px 8px; margin: 2px 0; border-radius: 4px; font-size: 12px; font-family: monospace;';
            switch(type) {
                case 'success': entry.style.background = '#d4edda'; entry.style.color = '#155724'; break;
                case 'error': entry.style.background = '#f8d7da'; entry.style.color = '#721c24'; break;
                case 'warning': entry.style.background = '#fff3cd'; entry.style.color = '#856404'; break;
                default: entry.style.background = '#e7f3ff'; entry.style.color = '#004085'; break;
            }
            entry.textContent = logEntry;
            logEl.appendChild(entry);
            logEl.scrollTop = logEl.scrollHeight;
        }
    }
    
    // === ПОЛУЧЕНИЕ CSRF-ТОКЕНА ===
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    const csrfToken = getCookie('csrftoken') || '{{ csrf_token }}';
    addLog('CSRF-токен получен', 'info');
    
    // === ИНИЦИАЛИЗАЦИЯ ===
    addLog('Инициализация модального окна покупки билетов', 'info');
    
    const modalEl = document.getElementById('buyTicketModal');
    const statusModalEl = document.getElementById('purchaseStatusModal');
    const buyModal = new bootstrap.Modal(modalEl);
    const statusModal = new bootstrap.Modal(statusModalEl);
    
    // === ОТКРЫТИЕ МОДАЛЬНОГО ОКНА ===
    
    // Убираем скрытие модалки Bootstrap
    const openBuyBtn = document.getElementById('openBuyModal');
    if (openBuyBtn && !openBuyBtn.disabled) {
        openBuyBtn.addEventListener('click', function(e) {
            // Партнёрам недоступна покупка билетов
            if (window.IS_PARTNER) {
                showToast('Покупка билетов недоступна для партнёров.');
                e.preventDefault();
                return false;
            }
            
            addLog('Модальное окно открыто', 'info');
            updateFreeTicketLimits();
            updateCartDisplay();
            buyModal.show();
        });
    } else if (openBuyBtn && openBuyBtn.disabled) {
        addLog('Кнопка покупки отключена — нет доступных билетов', 'warning');
    }
    
    // === УПРАВЛЕНИЕ КОЛИЧЕСТВОМ ===
    function updateQuantity(ticketId, delta) {
        addLog('Изменение количества билета ' + ticketId + ' на ' + delta, 'info');
        const input = document.getElementById('qty_' + ticketId);
        const card = input.closest('.ticket-card');
        const maxQty = parseInt(card.dataset.maxQty) || 99;
        let newQty = (parseInt(input.value) || 0) + delta;
        newQty = Math.max(0, Math.min(newQty, maxQty));
        input.value = newQty;
        
        addLog('Новое количество для билета ' + ticketId + ': ' + newQty, 'info');
        updateCartDisplay();
    }
    
    document.querySelectorAll('.qty-increase').forEach(btn => {
        btn.addEventListener('click', function() {
            updateQuantity(this.dataset.ticketId, 1);
        });
    });
    
    document.querySelectorAll('.qty-decrease').forEach(btn => {
        btn.addEventListener('click', function() {
            updateQuantity(this.dataset.ticketId, -1);
        });
    });
    
    document.querySelectorAll('.qty-input-field').forEach(input => {
        input.addEventListener('change', function() {
            const ticketId = this.dataset.ticketId;
            const card = this.closest('.ticket-card');
            const maxQty = parseInt(card.dataset.maxQty) || 99;
            let val = parseInt(this.value) || 0;
            val = Math.max(0, Math.min(val, maxQty));
            this.value = val;
            addLog('Ручной ввод количества для билета ' + ticketId + ': ' + val, 'info');
            updateCartDisplay();
        });
    });
    
    // === ОБНОВЛЕНИЕ КОРЗИНЫ ===
    function updateCartDisplay() {
        addLog('Обновление корзины', 'info');
        const cartItems = document.getElementById('cartItems');
        const cartSection = document.getElementById('cartSection');
        const confirmBtn = document.getElementById('confirmPurchaseBtn');
        let totalItems = 0;
        let totalPrice = 0;
        let itemsHtml = '';
        const selectedTickets = [];
        
        document.querySelectorAll('.ticket-card').forEach(card => {
            const ticketId = card.dataset.ticketId;
            const ticketName = card.dataset.ticketName;
            const ticketPrice = parseFloat(card.dataset.ticketPrice) || 0;
            const qty = parseInt(document.getElementById('qty_' + ticketId).value) || 0;
            
            if (qty > 0) {
                totalItems += qty;
                totalPrice += ticketPrice * qty;
                selectedTickets.push({
                    id: ticketId,
                    name: ticketName,
                    price: ticketPrice,
                    quantity: qty,
                    subtotal: ticketPrice * qty
                });
                
                itemsHtml += '<div class="cart-item">' + ticketName + '</div>';
                
                addLog('Добавлено в корзину: ' + ticketName + ' x ' + qty + ' = ' + (ticketPrice * qty).toLocaleString('ru-RU') + ' ₽', 'success');
            }
        });
        
        if (cartSection) {
            if (totalItems > 0) {
                cartSection.style.display = 'block';
                cartItems.innerHTML = itemsHtml;
                const countText = totalItems === 1 ? '1 билет' : (totalItems < 5 ? totalItems + ' билета' : totalItems + ' билетов');
                document.querySelector('.cart-total-count').textContent = countText;
                document.querySelector('.cart-total-price').textContent = totalPrice.toLocaleString('ru-RU') + ' руб.';
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Оплатить ' + totalPrice.toLocaleString('ru-RU') + ' ₽';
                addLog('Корзина обновлена. Всего: ' + totalItems + ' билетов на сумму ' + totalPrice.toLocaleString('ru-RU') + ' ₽', 'success');
            } else {
                cartSection.style.display = 'none';
                confirmBtn.disabled = true;
                confirmBtn.textContent = 'Оформить заказ';
                addLog('Корзина пуста', 'warning');
            }
        }
        
        window.selectedTickets = selectedTickets;
        window.cartTotal = totalPrice;
    }
    
    // === ПОКУПКА ===
    const buyBtn = document.getElementById('confirmPurchaseBtn');
    if (buyBtn) {
        buyBtn.addEventListener('click', function() {
            addLog('Начало процесса покупки', 'info');
        
        // Закрываем модалку выбора
        buyModal.hide();
        
        // Проверяем корзину
        if (!window.selectedTickets || window.selectedTickets.length === 0) {
            addLog('Ошибка: корзина пуста', 'error');
            alert('Пожалуйста, выберите хотя бы один билет');
            return;
        }
        
        // Собираем данные
        const emailInput = document.getElementById('buyerEmail');
        const email = emailInput
            ? emailInput.value.trim()
            : document.querySelector('input[name="buyer_email"]')?.value?.trim() || '';
        
        if (!email) {
            addLog('Ошибка: заполните email покупателя', 'error');
            alert('Пожалуйста, укажите email');
            return;
        }
        
        // Показываем модалку статуса
        statusModal.show();
        document.getElementById('purchaseSpinner').style.display = 'block';
        document.getElementById('purchaseStatusText').textContent = 'Формирование заказа...';
        document.getElementById('purchaseStatusDetail').textContent = 'Пожалуйста, подождите';
        document.getElementById('purchaseLog').innerHTML = '';
        
        // Отправляем запрос
        const payload = {
            tickets: window.selectedTickets,
            total_price: window.cartTotal,
            email: email
        };
        
        // Добавляем UTM-метки в payload
        const utmParams = getUtmParams();
        if (Object.keys(utmParams).length > 0) {
            payload.utm_params = utmParams;
            addLog('UTM-метки добавлены в запрос: ' + JSON.stringify(utmParams), 'info');
        }
        
        addLog('Отправка запроса на сервер...', 'info');
        document.getElementById('purchaseStatusText').textContent = 'Отправка запроса...';
        
        fetch(window.BULK_BUY_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload)
        })
        .then(function(response) {
            addLog('Получен ответ от сервера: ' + response.status, 'info');
            document.getElementById('purchaseStatusText').textContent = 'Получение ответа...';
            
            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }
            return response.json();
        })
        .then(function(data) {
            addLog('Ответ получен: ' + JSON.stringify(data), 'success');
            
            if (data.success) {
                document.getElementById('purchaseSpinner').style.display = 'none';
                document.getElementById('purchaseStatusText').textContent = 'Заказ оформлен!';
                
                // Сохраняем информацию о бесплатных билетах (для этого мероприятия)
                if (data.free_tickets_count !== undefined) {
                    try {
                        localStorage.setItem('free_tickets_event_' + '{{ event.id }}', String(data.free_tickets_count));
                    } catch(e) {}
                }
                
                if (data.payment_url) {
                    document.getElementById('purchaseStatusDetail').textContent = 'Перенаправление на оплату...';
                    addLog('Перенаправление на оплату: ' + data.payment_url, 'success');
                    
                    // Показываем финальное сообщение перед редиректом
                    setTimeout(function() {
                        document.getElementById('purchaseLog').innerHTML += 
                            '<div style="padding: 10px; background: #d4edda; color: #155724; border-radius: 4px; margin-top: 10px;">' +
                            'Заказ #' + data.order_id + ' создан. Перенаправляем на оплату...' +
                            '</div>';
                    }, 500);
                    
                    window.location.href = data.payment_url;
                } else if (data.message) {
                    document.getElementById('purchaseStatusDetail').textContent = data.message;
                    addLog(data.message, 'success');
                }
            } else {
                throw new Error(data.error || 'Неизвестная ошибка');
            }
        })
        .catch(function(error) {
            addLog('Ошибка: ' + error.message, 'error');
            document.getElementById('purchaseSpinner').style.display = 'none';
            document.getElementById('purchaseStatusText').textContent = 'Ошибка оформления';
            document.getElementById('purchaseStatusDetail').textContent = error.message;
            
            // Показываем лог для отладки
            document.getElementById('purchaseLog').innerHTML += 
                '<div style="padding: 10px; background: #f8d7da; color: #721c24; border-radius: 4px; margin-top: 10px;">' +
                '<strong>Детали ошибки:</strong><br>' + error.message +
                '</div>';
            });
        });
    }
    
    addLog('Инициализация завершена', 'success');
    
    // === КАРТА ===
    function initMap() {
        var mapEl = document.getElementById('map-canvas');
        if (!mapEl) return;
        
        var lat = parseFloat(mapEl.dataset.lat.replace(',', '.'));
        var lon = parseFloat(mapEl.dataset.lon.replace(',', '.'));
        var title = mapEl.dataset.eventTitle || '';
        var address = mapEl.dataset.eventAddress || '';
        
        console.log('=== Координаты мероприятия ===');
        console.log('ID мероприятия:', eventId);
        console.log('Название:', title);
        console.log('Адрес:', address);
        console.log('Широта (latitude):', lat);
        console.log('Долгота (longitude):', lon);
        console.log('==============================');
        
        if (isNaN(lat) || isNaN(lon)) {
            console.error('Некорректные координаты:', lat, lon);
            return;
        }
        
        if (typeof ymaps === 'undefined') {
            console.error('YMaps API не загружен');
            return;
        }
        
        ymaps.ready(function() {
            var map = new ymaps.Map('map-canvas', {
                center: [lat, lon],
                zoom: 15
            });
            
            var placemark = new ymaps.Placemark([lat, lon], {
                balloonContent: title,
                hintContent: address
            }, {
                preset: 'islands#blueMapIcon'
            });
            
            map.geoObjects.add(placemark);
            map.setCenter([lat, lon]);
        });
    }
    
    // Инициализируем карту если есть контейнер
    if (document.getElementById('map-canvas')) {
        initMap();
    }
});