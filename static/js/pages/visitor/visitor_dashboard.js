document.addEventListener('DOMContentLoaded', function () {
  var modal = document.getElementById('ticketModal');
  var modalInner = document.getElementById('ticketModalInner');
  var closeBtn = document.getElementById('ticketModalClose');

  // Открыть модалку
  document.querySelectorAll('.show-ticket-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var url = this.getAttribute('data-ticket-url');
      var title = this.getAttribute('data-event-title');

      // Показываем лоадер
      modalInner.innerHTML =
        '<div style="text-align:center;padding:80px 0;color:#888;font-family:Montserrat,sans-serif;">' +
        '<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="animation:spin 1s linear infinite;">' +
        '<circle cx="20" cy="20" r="16" stroke="#ff8348" stroke-width="3" stroke-linecap="round" stroke-dasharray="80" stroke-dashoffset="20"/>' +
        '</svg>' +
        '<p style="margin-top:16px;">Загрузка билета…</p>' +
        '</div>';

      // Анимация появления
      modal.style.display = 'flex';
      requestAnimationFrame(function () {
        modal.classList.add('ticket-modal--open');
      });

      // Загружаем HTML-фрагмент билета
      fetch(url)
        .then(function (res) {
          if (!res.ok) throw new Error('Network error');
          return res.text();
        })
        .then(function (html) {
          modalInner.innerHTML = html;
        })
        .catch(function () {
          modalInner.innerHTML =
            '<p style="text-align:center;padding:60px 0;color:#c62828;font-family:Montserrat,sans-serif;">' +
            'Не удалось загрузить билет. Попробуйте позже.' +
            '</p>';
        });
    });
  });

  // Закрыть модалку
  function closeModal() {
    modal.classList.remove('ticket-modal--open');
    setTimeout(function () {
      modal.style.display = 'none';
      modalInner.innerHTML = '';
    }, 300);
  }

  closeBtn.addEventListener('click', closeModal);
  modal.querySelector('.ticket-modal-backdrop').addEventListener('click', closeModal);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('ticket-modal--open')) {
      closeModal();
    }
  });
});
