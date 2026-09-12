document.addEventListener('DOMContentLoaded', function() {
    'use strict';
    
    // === ЛОГГЕР ===
    // ID мероприятия передаётся шаблоном через meta-тег event-id (см. event_detail.html)
    const eventMeta = document.querySelector('meta[name="event-id"]');
    const eventId = eventMeta ? eventMeta.content : '';
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
    
    // Устанавливаем начальные значения для is_per_person билетов
    document.querySelectorAll('.ticket-card').forEach(card => {
        const ticketId = card.dataset.ticketId;
        const input = document.getElementById('qty_' + ticketId);
        const minQty = parseInt(card.dataset.minQty) || 1;
        const isPerPerson = card.dataset.isPerPerson === 'true';
        
        if (input && isPerPerson && minQty > 1) {
            // Устанавливаем minQty как начальное значение
            input.value = 0; // Оставляем 0, но при первом нажатии + будет minQty
        }
    });
    
    // Подсчёт уже полученных бесплатных билетов на ЭТОМ мероприятии (из localStorage)
    function getAlreadyFreeTicketsForEvent() {
        try {
            // Сначала ищем под ключом мероприятия
            const stored = localStorage.getItem('free_tickets_event_' + eventId);
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
    
    // CSRF: сначала скрытое поле формы со страницы, затем cookie csrftoken
    function getCsrfFromPage() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }
    const csrfToken = getCsrfFromPage() || getCookie('csrftoken') || '';
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
        const minQty = parseInt(card.dataset.minQty) || 1;
        const isPerPerson = card.dataset.isPerPerson === 'true';
        
        let currentQty = parseInt(input.value) || 0;
        let newQty;
        
        if (isPerPerson && minQty > 1) {
            if (delta > 0) {
                if (currentQty === 0) {
                    newQty = minQty;
                } else {
                    newQty = currentQty + 1;
                }
            } else {
                if (currentQty <= minQty) {
                    newQty = 0;
                } else {
                    newQty = currentQty - 1;
                }
            }
        } else {
            newQty = currentQty + delta;
        }
        
        const effectiveMin = isPerPerson && minQty > 1 ? 0 : 0;
        newQty = Math.max(effectiveMin, Math.min(newQty, maxQty));
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
            const minQty = parseInt(card.dataset.minQty) || 1;
            const isPerPerson = card.dataset.isPerPerson === 'true';
            let val = parseInt(this.value) || 0;
            
            if (isPerPerson && minQty > 1 && val > 0) {
                const rounded = Math.round(val / minQty) * minQty;
                val = Math.max(minQty, rounded);
            }
            
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
            const isPerPerson = card.dataset.isPerPerson === 'true';
            const qty = parseInt(document.getElementById('qty_' + ticketId).value) || 0;
            
            if (qty > 0) {
                totalItems += qty;
                // Для is_per_person цена уже за человека, итого = цена × кол-во
                totalPrice += ticketPrice * qty;
                selectedTickets.push({
                    id: ticketId,
                    name: ticketName,
                    price: ticketPrice,
                    quantity: qty,
                    subtotal: ticketPrice * qty,
                    is_per_person: isPerPerson
                });
                
                let itemLabel = ticketName;
                if (isPerPerson) {
                    itemLabel += ' (' + qty + ' чел.)';
                }
                itemsHtml += '<div class="cart-item">' + itemLabel + '</div>';
                
                addLog('Добавлено в корзину: ' + itemLabel + ' = ' + (ticketPrice * qty).toLocaleString('ru-RU') + ' руб.', 'success');
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
        
        // Добавляем бронирование без оплаты (если чекбокс установлен)
        const reserveCheckbox = document.getElementById('reserve_without_payment');
        if (reserveCheckbox && reserveCheckbox.checked) {
            payload.reserve_without_payment = true;
        }
        
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
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
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
                        localStorage.setItem('free_tickets_event_' + eventId, String(data.free_tickets_count));
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
                    
                    // Если это бронирование без оплаты — показываем сообщение об успехе
                    if (data.message.includes('забронированы') || data.message.includes('Бронирование')) {
                        setTimeout(function() {
                            document.getElementById('purchaseLog').innerHTML += 
                                '<div style="padding: 10px; background: #d4edda; color: #155724; border-radius: 4px; margin-top: 10px;">' +
                                'Бронь создана! Письмо с ссылкой для оплаты отправлено на ' + email + '.' +
                                '</div>';
                        }, 500);
                    }
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
    
    // === ИЗБРАННОЕ ===
    var favLink = document.querySelector('.favourites-link');
    if (favLink) {
        favLink.addEventListener('click', function(e) {
            e.preventDefault();
            
            var eventId = this.dataset.eventId;
            var url = this.href;
            
            // Проверяем, партнёр ли это
            if (typeof window.IS_PARTNER !== 'undefined' && window.IS_PARTNER) {
                showToast('Для партнёров эта функция недоступна', true);
                return;
            }
            
            // Проверяем, авторизован ли пользователь
            // Если IS_PARTNER не определён или false — это может быть гость или visitor
            // Пробуем сделать запрос — если 403/401/redirect, значит не авторизован
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken || getCookie('csrftoken'),
                }
            })
            .then(function(response) {
                // Если ответ не JSON (статус 3xx или 4xx с HTML) — не авторизован
                var contentType = response.headers.get('content-type') || '';
                if (!contentType.includes('application/json') || response.status >= 400) {
                    // Не авторизован — гость
                    showToast('Для добавления в избранное нужно войти в аккаунт. Перенаправляем...', true);
                    setTimeout(function() {
                        var loginUrl = (typeof window.LOGIN_URL !== 'undefined' && window.LOGIN_URL) ? window.LOGIN_URL : '/login/';
                        window.location.href = loginUrl;
                    }, 2000);
                    return;
                }
                
                return response.json().then(function(data) {
                    if (data.status === 'added') {
                        showToast('Добавлено в избранное', false);
                        favLink.querySelector('img').src = '/media/icon/favourites_active.png';
                    } else if (data.status === 'removed') {
                        showToast('Удалено из избранного');
                        favLink.querySelector('img').src = '/media/icon/favourites.png';
                    } else {
                        showToast(data.message || 'Ошибка', true);
                    }
                });
            })
            .catch(function(err) {
                console.error('Favorite error:', err);
                // Ошибка сети — значит не авторизован
                showToast('Для добавления в избранное нужно войти в аккаунт. Перенаправляем...', true);
                setTimeout(function() {
                    var loginUrl = (typeof window.LOGIN_URL !== 'undefined' && window.LOGIN_URL) ? window.LOGIN_URL : '/login/';
                    window.location.href = loginUrl;
                }, 2000);
            });
        });
    }
    
    // === КНОПКА ЗАДАТЬ ВОПРОС — для партнёров недоступна ===
    var questionBtn = document.querySelector('.question-organizator');
    if (questionBtn) {
        questionBtn.addEventListener('click', function(e) {
            if (window.IS_PARTNER) {
                showToast('Задать вопрос организатору недоступно для партнёров.');
                e.preventDefault();
                return false;
            }
        });
    }
    // === ОПИСАНИЕ БИЛЕТА: одна строка, клик — полный текст ===
    (function initTicketDescriptions() {
        var descs = document.querySelectorAll('.ticket-desc');
        if (!descs.length) return;

        // Помечаем те, чей текст реально не влазит в одну строку
        descs.forEach(function(el) {
            if (el.scrollWidth > el.clientWidth + 1) {
                el.classList.add('is-truncated');
            }
        });

        var tooltip = null;
        var activeEl = null;

        function hideTooltip() {
            if (!tooltip) return;
            tooltip.classList.remove('show');
            var t = tooltip;
            tooltip = null;
            activeEl = null;
            setTimeout(function() {
                if (t && t.parentNode) t.parentNode.removeChild(t);
            }, 200);
        }

        function showTooltipFor(el) {
            hideTooltip();
            tooltip = document.createElement('div');
            tooltip.className = 'ticket-desc-tooltip';
            tooltip.textContent = el.textContent.trim();
            document.body.appendChild(tooltip);
            activeEl = el;

            // Позиционируем под элементом, не вылезая за границы экрана
            var rect = el.getBoundingClientRect();
            var tipRect = tooltip.getBoundingClientRect();
            var left = rect.left;
            var top = rect.bottom + 8;
            if (left + tipRect.width > window.innerWidth - 8) {
                left = window.innerWidth - tipRect.width - 8;
            }
            if (left < 8) left = 8;
            if (top + tipRect.height > window.innerHeight - 8) {
                top = rect.top - tipRect.height - 8;
            }
            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
            // Показываем на следующем кадре для анимации
            requestAnimationFrame(function() {
                if (tooltip) tooltip.classList.add('show');
            });
        }

        descs.forEach(function(el) {
            // Реагируем только на сокращённые описания
            function handleToggle(e) {
                e.stopPropagation();
                if (!el.classList.contains('is-truncated')) return;
                if (activeEl === el && tooltip) {
                    hideTooltip();
                } else {
                    showTooltipFor(el);
                }
            }
            el.addEventListener('click', handleToggle);
            el.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleToggle(e);
                }
            });
        });

        // Закрытие по клику вне и по Escape
        document.addEventListener('click', function() {
            if (tooltip) hideTooltip();
        });
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && tooltip) hideTooltip();
        });
        // При ресизве пересчитываем, что не влазит, и прячем тултип
        var resizeTimer = null;
        window.addEventListener('resize', function() {
            if (tooltip) hideTooltip();
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function() {
                descs.forEach(function(el) {
                    el.classList.toggle('is-truncated', el.scrollWidth > el.clientWidth + 1);
                });
            }, 150);
        });
    })();
});