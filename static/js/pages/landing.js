document.addEventListener('DOMContentLoaded', function() {
    // Находим элементы бургер-иконки, меню и крестика
    const burgerIcon = document.querySelector('.burger-menu-icon');
    const burgerMenu = document.querySelector('.burger-menu');
    const burgerClose = document.querySelector('.burger-close-icon');

    // Проверяем, что элементы существуют
    if (!burgerIcon || !burgerMenu || !burgerClose) {
        console.error('Элементы бургер-меню не найдены!');
        return;
    }

    // Добавляем обработчик клика на бургер-иконку
    burgerIcon.addEventListener('click', function(event) {
        event.stopPropagation(); // Останавливаем всплытие события
        console.log('Бургер-иконка кликнута'); // Отладочное сообщение
        burgerMenu.classList.add('active');
    });

    // Добавляем обработчик клика на крестик
    burgerClose.addEventListener('click', function(event) {
        event.stopPropagation(); // Останавливаем всплытие события
        console.log('Крестик кликнут'); // Отладочное сообщение
        burgerMenu.classList.remove('active');
    });

    // Закрытие меню при клике вне его
    document.addEventListener('click', function(event) {
        if (!burgerMenu.contains(event.target) && !burgerIcon.contains(event.target)) {
            console.log('Клик вне меню'); // Отладочное сообщение
            burgerMenu.classList.remove('active');
        }
    });
});
