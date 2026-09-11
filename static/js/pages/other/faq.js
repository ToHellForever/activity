// === FAQ ===

function toggleAccordion(button) {
    var item = button.parentElement;
    var answer = item.querySelector('.faq-accordion-answer');
    var arrow = item.querySelector('.faq-accordion-arrow');
    var isOpen = item.classList.contains('active');

    // Закрываем все остальные вопросы в этом аккордеоне
    var accordion = item.parentElement;
    accordion.querySelectorAll('.faq-accordion-item').forEach(function(i) {
        i.classList.remove('active');
        i.querySelector('.faq-accordion-answer').style.maxHeight = null;
        i.querySelector('.faq-accordion-arrow').classList.remove('open');
    });

    // Открываем текущий, если он был закрыт
    if (!isOpen) {
        item.classList.add('active');
        answer.style.maxHeight = answer.scrollHeight + 'px';
        arrow.classList.add('open');
    }
}
