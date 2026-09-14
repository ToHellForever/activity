/**
 * Кастомный календарь для выбора даты
 */
class CustomCalendar {
    constructor(inputId, calendarId, hiddenInputName, options = {}) {
        console.log('[CustomCalendar] Constructor called for:', inputId);
        this.input = document.getElementById(inputId);
        this.calendar = document.getElementById(calendarId);
        this.hiddenInputName = hiddenInputName;
        this.selectedDate = null;
        this.currentMonth = new Date();
        this.displayDateFormat = options.displayDateFormat || 'dd.mm.yyyy';
        this.valueDateFormat = options.valueDateFormat || 'yyyy-mm-dd';
        this.allowPastDates = options.allowPastDates === true;
        this.minDate = options.minDate || null; // Минимальная дата (например, +24 часа)
        this.onSelectDate = typeof options.onSelectDate === 'function' ? options.onSelectDate : null;
        
        if (!this.input || !this.calendar) {
            console.warn('Calendar elements not found on first try, waiting for DOM...');
            this.retryInit(inputId, calendarId, hiddenInputName);
            return;
        }

        this.input.dataset.rawValue = '';
        
        console.log('[CustomCalendar] Elements found, calling init()');
        this.init();
    }

    parseDateValue(value) {
        if (!value) {
            return null;
        }

        const trimmed = String(value).trim();
        if (!trimmed) {
            return null;
        }

        const isoMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (isoMatch) {
            const [, year, month, day] = isoMatch;
            return new Date(Number(year), Number(month) - 1, Number(day));
        }

        const dotMatch = trimmed.match(/^(\d{2})\.(\d{2})\.(\d{4})/);
        if (dotMatch) {
            const [, day, month, year] = dotMatch;
            return new Date(Number(year), Number(month) - 1, Number(day));
        }

        const parsed = new Date(trimmed);
        return Number.isNaN(parsed.getTime()) ? null : parsed;
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
        const inputContainer = this.input.closest('.input-with-button, .date-container');
        const toggleBtn = inputContainer ? inputContainer.querySelector('.calendar-toggle-btn') : null;
        
        if (toggleBtn) {
            toggleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.toggle();
            });
        }

        // Открытие календаря по клику на инпут
        this.input.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!this.calendar.classList.contains('active')) {
                this.open();
            }
        });

        // Открытие календаря по фокусу, только если он ещё закрыт
        this.input.addEventListener('focus', () => {
            if (!this.calendar.classList.contains('active')) {
                this.open();
            }
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
            if (!this.calendar.contains(e.target)
                && !this.input.contains(e.target)
                && !this.input.isSameNode(e.target)
                && !e.target.closest('.calendar-toggle-btn')) {
                this.close();
            }
        });

        const initialValue = this.input.value;
        if (initialValue) {
            this.selectedDate = this.parseDateValue(initialValue);
            if (this.selectedDate) {
                this.currentMonth = new Date(this.selectedDate.getFullYear(), this.selectedDate.getMonth(), 1);
            }
            this.input.dataset.rawValue = this.formatDate(this.selectedDate, this.valueDateFormat);
            this.input.value = this.formatDate(this.selectedDate, this.displayDateFormat);
        }

        const form = this.input.closest('form');
        if (form) {
            form.addEventListener('submit', () => {
                if (this.input.dataset.rawValue) {
                    this.input.value = this.input.dataset.rawValue;
                }
            });
        }

        // Первоначальная отрисовка
        this.render();
    }

    open() {
        this.calendar.classList.add('active');
        console.log('Calendar opened');
        
        // Добавляем класс open у контейнера
        const container = this.input.closest('.date-container');
        if (container) {
            container.classList.add('open');
        }
        
        this.render();
    }

    toggle() {
        if (this.calendar.classList.contains('active')) {
            this.close();
        } else {
            this.open();
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

    selectDate(date, options = {}) {
        const { silent = false } = options;

        this.selectedDate = date;
        const formattedDate = this.formatDate(date, this.valueDateFormat);
        this.input.dataset.rawValue = formattedDate;
        this.input.value = this.formatDate(date, this.displayDateFormat);
        this.updateHiddenInput(formattedDate);
        this.render();

        if (!silent && typeof this.onSelectDate === 'function') {
            this.onSelectDate(date);
        }

        this.close();
    }

    updateHiddenInput(value) {
        if (!this.hiddenInputName) {
            return;
        }

        // Ищем по ID (это основной способ, так как hiddenInputName — это ID)
        const hiddenInput = document.getElementById(this.hiddenInputName);
        if (hiddenInput) {
            hiddenInput.value = value;
            return;
        }

        // Fallback: ищем по name в пределах того же parent
        const fallback = this.input.parentElement.querySelector(`input[name="${this.hiddenInputName}"]`);
        if (fallback) {
            fallback.value = value;
        }
    }

    formatDate(date, format = this.displayDateFormat) {
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();

        return format
            .replace(/yyyy/g, year)
            .replace(/mm/g, month)
            .replace(/dd/g, day);
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

        // Минимальная дата (для формы — +24 часа, для фильтров — сегодня)
        let minDate = null;
        if (this.minDate) {
            minDate = new Date(this.minDate);
            minDate.setHours(0, 0, 0, 0);
        } else if (!this.allowPastDates) {
            minDate = today;
        }

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
            const isDisabled = minDate ? date < minDate : (this.allowPastDates ? false : isPast);

            let classes = 'calendar-day';
            if (isToday) classes += ' calendar-day-today';
            if (isSelected) classes += ' calendar-day-selected';
            if (isDisabled) classes += ' calendar-day-disabled';

            if (!isDisabled) {
                grid.innerHTML += `<div class="${classes}" data-date="${date.getFullYear()}-${date.getMonth()}-${date.getDate()}">${day}</div>`;
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
        }

        // Открытие dropdown по клику на инпут
        this.input.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggle();
        });

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

/**
 * Обновляет скрытое поле даты/времени в форме бронирования площадки
 */
function updateBookingEventDate() {
    const cal = window.bookingCalendar;
    const hidden = document.getElementById('booking_event_date');
    if (!cal || !hidden) return;

    if (!cal.selectedDate) {
        hidden.value = '';
        return;
    }

    const hoursInput = document.getElementById('bookingTimeHours');
    const minutesInput = document.getElementById('bookingTimeMinutes');
    const h = hoursInput ? String(parseInt(hoursInput.value || 12, 10)).padStart(2, '0') : '12';
    const min = minutesInput ? String(parseInt(minutesInput.value || 0, 10)).padStart(2, '0') : '00';
    const y = cal.selectedDate.getFullYear();
    const m = String(cal.selectedDate.getMonth() + 1).padStart(2, '0');
    const d = String(cal.selectedDate.getDate()).padStart(2, '0');
    hidden.value = `${y}-${m}-${d} ${h}:${min}`;
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('Calendar JS loaded and initializing...');
    
    // Инициализация календаря для даты (только если элемент существует)
    if (document.getElementById('dateFromInput')) {
        window.calendar = new CustomCalendar(
            'dateFromInput',
            'dateFromCalendar',
            'date_from',
            { allowPastDates: false }
        );
    } else {
        console.log('No dateFromInput found on this page, skipping...');
    }

    // Инициализация календаря для формы создания/редактирования мероприятия
    if (document.getElementById('formCalendar')) {
        // Минимальная дата — через 24 часа от текущего момента
        const minDate = new Date();
        minDate.setHours(minDate.getHours() + 24);
        new CustomCalendar(
            'eventFormDateInput',
            'formCalendar',
            'date_time',
            {
                minDate: minDate,
                displayDateFormat: 'dd.mm.yyyy',
                valueDateFormat: 'yyyy-mm-dd',
                // Коллбэк при выборе даты — обновляем скрытый input с временем
                onSelectDate: function(date) {
                    const idDateTime = document.getElementById('id_date_time');
                    const eventFormTimeHours = document.getElementById('eventFormTimeHours');
                    const eventFormTimeMinutes = document.getElementById('eventFormTimeMinutes');
                    if (idDateTime) {
                        const y = date.getFullYear();
                        const m = String(date.getMonth() + 1).padStart(2, '0');
                        const d = String(date.getDate()).padStart(2, '0');
                        const h = eventFormTimeHours ? String(parseInt(eventFormTimeHours.value || 12, 10)).padStart(2, '0') : '12';
                        const min = eventFormTimeMinutes ? String(parseInt(eventFormTimeMinutes.value || 0, 10)).padStart(2, '0') : '00';
                        idDateTime.value = `${y}-${m}-${d}T${h}:${min}`;
                    }
                }
            }
        );
    }

    // Инициализация календаря в форме бронирования площадки
    if (document.getElementById('bookingDateInput')) {
        // Минимальная дата — завтрашний день (прошедшие и сегодня недоступны)
        const minBookingDate = new Date();
        minBookingDate.setHours(0, 0, 0, 0);
        minBookingDate.setDate(minBookingDate.getDate() + 1);

        window.bookingCalendar = new CustomCalendar(
            'bookingDateInput',
            'bookingCalendar',
            'booking_event_date',
            {
                minDate: minBookingDate,
                onSelectDate: function(date) {
                    updateBookingEventDate();
                }
            }
        );

        // Обновляем скрытое поле при изменении времени
        ['bookingTimeHours', 'bookingTimeMinutes'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', updateBookingEventDate);
            }
        });
    }

    // Инициализация dropdown формата в форме бронирования площадки
    if (document.getElementById('bookingFormatInput')) {
        new CustomDropdown('bookingFormatInput', 'bookingFormatDropdown', 'booking_event_format');
    }

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
