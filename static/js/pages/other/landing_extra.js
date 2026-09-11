// === LANDING EXTRA ===

// Универсальный получение CSRF-токена (из cookie или скрытого поля формы)
function getLandingCsrf() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input) return input.value;
    const match = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[2]) : '';
}

// Страницы редиректа передаются шаблоном через data-атрибуты кнопки createEventBtn
document.addEventListener('DOMContentLoaded', function() {
    const createEventBtn = document.getElementById('createEventBtn');
    
    createEventBtn.addEventListener('click', function() {
        const userType = this.getAttribute('data-user-type');
        const isAuthenticated = this.getAttribute('data-is-auth') === 'true';
        const loginUrl = this.getAttribute('data-login-url') || '/login/';
        const eventListUrl = this.getAttribute('data-event-list-url') || '/partner/partner_event_list/';
        
        console.log('User authenticated:', isAuthenticated, 'User type:', userType);
        
        if (!isAuthenticated) {
            // Пользователь не авторизован - redirect на login
            window.location.href = loginUrl;
        } else if (userType === 'partner') {
            // Партнёр - redirect в список мероприятий
            window.location.href = eventListUrl;
        } else {
            // Обычный пользователь или гость - redirect на login
            window.location.href = loginUrl;
        }
    });
});
