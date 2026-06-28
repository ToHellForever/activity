document.addEventListener('DOMContentLoaded', function() {
   // Поэтапная подгрузка карточек ("Показать ещё")
   const loadMoreBtn = document.getElementById('load-more-btn');
   const venuesGrid = document.getElementById('venues-grid');
   const filterForm = document.getElementById('filter-form');
   
   if (loadMoreBtn) {
       loadMoreBtn.addEventListener('click', function() {
           const nextPage = loadMoreBtn.dataset.page;
           const filterFormData = new FormData(filterForm);
           
           // Добавляем выбранное оборудование в форму
           document.querySelectorAll('.equip-checkbox:checked').forEach(checkbox => {
               filterFormData.append('equipment', checkbox.value);
           });
           
           fetch(`/venues/?page=${nextPage}&${new URLSearchParams(filterFormData).toString()}`)
               .then(response => response.text())
               .then(html => {
                   const parser = new DOMParser();
                   const doc = parser.parseFromString(html, 'text/html');
                   const newCardsHTML = doc.querySelector('#venues-grid').innerHTML;
                   
                   venuesGrid.innerHTML += newCardsHTML;
                   
                   // Обновляем кнопку "Показать ещё"
                   const newNextPageLink = doc.querySelector('#load-more-btn');
                   if (newNextPageLink) {
                       loadMoreBtn.dataset.page = newNextPageLink.dataset.page;
                       loadMoreBtn.style.display = '';
                   } else {
                       loadMoreBtn.remove();
                   }
               });
       });
   }
   
   // Обработка отправки формы фильтров
   if (filterForm) {
       filterForm.addEventListener('submit', function(e) {
           e.preventDefault();
           
           // Удаляем предыдущие скрытые поля с оборудованием, если они есть
           const existingEquipmentInputs = filterForm.querySelectorAll('input[name="equipment"]');
           existingEquipmentInputs.forEach(input => input.remove());
           
           // Добавляем выбранное оборудование в форму
           document.querySelectorAll('.equip-checkbox:checked').forEach(checkbox => {
               const hiddenInput = document.createElement('input');
               hiddenInput.type = 'hidden';
               hiddenInput.name = 'equipment';
               hiddenInput.value = checkbox.value;
               filterForm.appendChild(hiddenInput);
           });
           
           this.submit();
       });
   }
});