/**
 * Кастомный календарь для выбора даты
 */
class CustomCalendar {
    constructor(inputId, calendarId, hiddenInputName) {
        this.input = document.getElementById(inputId);
        this.calendar = document.getElementById(calendarId);
        this.hiddenInputName = hiddenInputName;
        this.selectedDate = null;
        this.currentMonth = new Date();
        
        if (!this.input || !this.calendar) {
            console.warn('Calendar elements not found on first try, waiting for DOM...');
            this.retryInit(inputId, calendarId, hiddenInputName);
            return;
        }

        this.init();
    }

    retryInit(inputId, calendarId, hiddenInputName) {
        let attempts = 0;
        const maxAttempts = 50; // 5 секунд максимум
        
        const tryFind = () => {
            attempts++;
            this.input = this.input || document.getElementById(inputId);
            this.calendar = this.calendar || document.getElementById(calendarId);
            
            if (this.input && this.calendar) {
                console.log(`Calendar elements found after ${attempts} attempts`);
                this.hiddenInputName = hiddenInputName;
                this.init();
            } else if (attempts < maxAttempts) {
                setTimeout(tryFind, 100);
            } else {
                console.error('Calendar elements still not found after retries:', { input: this.input, calendar: this.calendar });
            }
        };
        
        tryFind();
    }

    init() {
        // Кнопка открытия календаря - ищем внутри родителя input
        const inputContainer = this.input.closest('.input-with-button');
        const toggleBtn = inputContainer ? inputContainer.querySelector('.calendar-toggle-btn') : null;
        
        if (toggleBtn) {
            toggleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('Calendar toggle clicked');
                this.toggle();
            });
        }

        // Открытие календаря по клику на инпут
        this.input.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggle();
        });

        // Кнопки навигации
        const prevBtn = this.calendar.querySelector('.calendar-prev-month');
        const nextBtn = this.calendar.querySelector('.calendar-next-month');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                this.currentMonth.setMonth(this.currentMonth.getMonth() - 1);
                this.render();
            });
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                this.currentMonth.setMonth(this.currentMonth.getMonth() + 1);
                this.render();
            });
        }

        // Кнопки футера
        const clearBtn = this.calendar.querySelector('.calendar-clear');
        const closeBtn = this.calendar.querySelector('.calendar-close');
        
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.clear();
            });
        }
        
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.close();
            });
        }

        // Закрытие при клике вне календаря
        document.addEventListener('click', (e) => {
            if (!this.calendar.contains(e.target) && !e.target.closest('.calendar-toggle-btn')) {
                this.close();
            }
        });

        // Первоначальная отрисовка
        this.render();
    }

    toggle() {
        this.calendar.classList.toggle('active');
        console.log('Calendar toggled, active:', this.calendar.classList.contains('active'));
        
        // Добавляем/убираем класс open у контейнера
        const container = this.input.closest('.date-container');
        if (container) {
            container.classList.toggle('open');
        }
        
        if (this.calendar.classList.contains('active')) {
            this.render();
        }
    }

    close() {
        this.calendar.classList.remove('active');
        
        // Убираем класс open у контейнера
        const container = this.input.closest('.date-container');
        if (container) {
            container.classList.remove('open');
        }
    }

    clear() {
        this.selectedDate = null;
        this.input.value = '';
        this.updateHiddenInput('');
        this.close();
    }

    selectDate(date) {
        this.selectedDate = date;
        // Формируем дату без учёта timezone (используем локальные компоненты)
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const formattedDate = `${year}-${month}-${day}`;
        this.input.value = this.formatDate(date);
        this.updateHiddenInput(formattedDate);
        this.render();
        this.close();
    }

    updateHiddenInput(value) {
        const hiddenInput = this.input.parentElement.querySelector(`input[name="${this.hiddenInputName}"]`);
        if (hiddenInput) {
            hiddenInput.value = value;
        }
    }

    formatDate(date) {
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        return `${day}.${month}.${year}`;
    }

    render() {
        const header = this.calendar.querySelector('.calendar-month-year');
        const grid = this.calendar.querySelector('.calendar-grid');

        if (!header || !grid) return;

        const monthNames = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ];

        header.textContent = `${monthNames[this.currentMonth.getMonth()]} ${this.currentMonth.getFullYear()}`;

        // Дни недели
        const weekDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
        grid.innerHTML = weekDays.map(day => 
            `<div class="calendar-day-header">${day}</div>`
        ).join('');

        // Первый день месяца
        const firstDay = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth(), 1);
        const lastDay = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth() + 1, 0);
        
        // Корректировка для русской недели (понедельник - первый день)
        let startDay = firstDay.getDay() - 1;
        if (startDay < 0) startDay = 6;

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        // Пустые ячейки до начала месяца
        for (let i = 0; i < startDay; i++) {
            grid.innerHTML += '<div class="calendar-day calendar-day-empty"></div>';
        }

        // Дни месяца
        for (let day = 1; day <= lastDay.getDate(); day++) {
            const date = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth(), day);
            const isToday = date.getTime() === today.getTime();
            const isSelected = this.selectedDate && 
                date.getTime() === new Date(this.selectedDate).setHours(0, 0, 0, 0);
            const isPast = date < today;

            let classes = 'calendar-day';
            if (isToday) classes += ' calendar-day-today';
            if (isSelected) classes += ' calendar-day-selected';
            if (isPast) classes += ' calendar-day-disabled';

            if (!isPast) {
                grid.innerHTML += `<div class="${classes}" data-date="${date.getFullYear()}-${date.getMonth()}-${date.day}">${day}</div>`;
            } else {
                grid.innerHTML += `<div class="${classes}">${day}</div>`;
            }
        }

        // Добавляем обработчики клика для дней
        grid.querySelectorAll('.calendar-day:not(.calendar-day-empty):not(.calendar-day-disabled)').forEach(dayEl => {
            dayEl.addEventListener('click', () => {
                const day = parseInt(dayEl.textContent);
                this.selectDate(new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth(), day));
            });
        });
    }
}

/**
 * Управление выпадающими списками
 */
class CustomDropdown {
    constructor(inputId, dropdownId, hiddenInputName) {
        this.input = document.getElementById(inputId);
        this.dropdown = document.getElementById(dropdownId);
        this.hiddenInputName = hiddenInputName;
        
        if (!this.input || !this.dropdown) {
            console.error('Dropdown elements not found:', { input: this.input, dropdown: this.dropdown });
            return;
        }

        this.init();
    }

    init() {
        // Кнопка открытия dropdown - ищем внутри родителя input
        const inputContainer = this.input.closest('.input-with-button');
        const toggleBtn = inputContainer ? inputContainer.querySelector('.dropdown-toggle-btn') : null;
        
        if (toggleBtn) {
            toggleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('Dropdown toggle clicked');
                this.toggle();
            });
        } else {
            console.error('Dropdown toggle button not found');
        }

        // Обработка выбора опции
        this.dropdown.querySelectorAll('.dropdown-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectOption(option);
            });
        });

        // Закрытие при клике вне dropdown
        document.addEventListener('click', (e) => {
            if (!this.dropdown.contains(e.target) && !e.target.closest('.dropdown-toggle-btn')) {
                this.dropdown.classList.remove('active');
                const container = this.input.closest('.dropdown-container');
                if (container) {
                    container.classList.remove('open');
                }
            }
        });
    }
    
    toggle() {
        this.dropdown.classList.toggle('active');
        // Добавляем/убираем класс open у контейнера
        const container = this.input.closest('.dropdown-container');
        if (container) {
            container.classList.toggle('open');
        }
        console.log('Dropdown toggled, active:', this.dropdown.classList.contains('active'));
    }

    close() {
        this.dropdown.classList.remove('active');
        // Убираем класс open у контейнера
        const container = this.input.closest('.dropdown-container');
        if (container) {
            container.classList.remove('open');
        }
    }

    selectOption(option) {
        const value = option.dataset.value;
        const text = option.textContent.trim();
        const placeholder = this.input.dataset.placeholder || '';

        // Обновляем отображаемый текст
        this.input.value = value ? text : placeholder;

        // Обновляем active класс
        this.dropdown.querySelectorAll('.dropdown-option').forEach(opt => {
            opt.classList.remove('active');
        });
        option.classList.add('active');

        // Обновляем скрытый input
        const hiddenInput = this.input.parentElement.querySelector(`input[name="${this.hiddenInputName}"]`);
        if (hiddenInput) {
            hiddenInput.value = value;
        }

        this.close();
    }
}

/**
 * Ползунок стоимости (один ползунок с отображением цены сверху)
 */
class PriceSlider {
    constructor(sliderId, valueDisplayId) {
        this.slider = document.getElementById(sliderId);
        this.valueDisplay = document.getElementById(valueDisplayId);
        
        if (!this.slider || !this.valueDisplay) {
            console.error('PriceSlider elements not found');
            return;
        }

        this.init();
    }

    init() {
        // Устанавливаем начальное значение
        this.updateValue();
        
        // Обновляем значение при движении ползунка
        this.slider.addEventListener('input', () => {
            this.updateValue();
        });
    }

    updateValue() {
        const value = parseInt(this.slider.value);
        // Форматируем число с разделителями тысяч
        const formattedValue = value.toLocaleString('ru-RU');
        this.valueDisplay.textContent = `${formattedValue} ₽`;
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('Calendar JS loaded and initializing...');
    
    // Инициализация календаря для даты
    window.calendar = new CustomCalendar(
        'dateFromInput',
        'dateFromCalendar',
        'date_from'
    );

    // Инициализация dropdown для категории
    const categoryInput = document.getElementById('categoryInput');
    if (categoryInput) {
        const categoryDropdown = document.getElementById('categoryDropdown');
        if (categoryDropdown) {
            console.log('Initializing category dropdown');
            const dropdownInstance = new CustomDropdown('categoryInput', 'categoryDropdown', 'category');
            
            // Синхронизируем отображаемое значение с выбранным из GET параметров
            const hiddenInput = categoryInput.parentElement.querySelector('input[name="category"]');
            if (hiddenInput && hiddenInput.value) {
                const selectedOption = categoryDropdown.querySelector(`[data-value="${hiddenInput.value}"]`);
                if (selectedOption) {
                    categoryInput.value = selectedOption.textContent.trim();
                }
            }
        } else {
            console.error('Category dropdown element not found');
        }
    } else {
        console.log('No category input found on this page');
    }
    
    // Инициализация dropdown для формата (если есть)
    const formatInput = document.getElementById('formatInput');
    if (formatInput) {
        const formatDropdown = document.getElementById('formatDropdown');
        if (formatDropdown) {
            new CustomDropdown('formatInput', 'formatDropdown', 'format');
        } else {
            console.error('Format dropdown element not found');
        }
    }
    
    // Инициализация dropdown для метро (если есть)
    const metroInput = document.getElementById('metroInput');
    if (metroInput) {
        const metroDropdown = document.getElementById('metroDropdown');
        if (metroDropdown) {
            console.log('Initializing metro dropdown');
            const metroDropdownInstance = new CustomDropdown('metroInput', 'metroDropdown', 'metro');
            
            // Синхронизируем отображаемое значение с выбранным из GET параметров
            const hiddenInput = metroInput.parentElement.querySelector('input[name="metro"]');
            if (hiddenInput && hiddenInput.value) {
                const selectedOption = metroDropdown.querySelector(`[data-value="${hiddenInput.value}"]`);
                if (selectedOption) {
                    metroInput.value = selectedOption.textContent.trim();
                }
            }
        }
    }
    
    // Инициализация ползунка стоимости (если есть)
    const priceSlider = document.getElementById('priceSlider');
    if (priceSlider) {
        new PriceSlider('priceSlider', 'priceValueDisplay');
    }
});
