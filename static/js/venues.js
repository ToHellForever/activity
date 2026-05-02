document.addEventListener('DOMContentLoaded', function() {
   // Поэтапная подгрузка карточек ("Показать ещё")
    const loadMoreBtn = document.getElementById('load-more-btn');
    const venuesGrid = document.getElementById('venues-grid');
    
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', function() {
            const nextPage = loadMoreBtn.dataset.page;
            const filterFormData = new FormData(document.getElementById('filter-form'));
            
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
});