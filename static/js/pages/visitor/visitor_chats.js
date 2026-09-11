// === VISITOR CHATS ===

// ============================================================
// РАЗДЕЛИТЕЛИ ДАТ В ЧАТЕ
// ============================================================
function addDateDividers(container) {
    const wrappers = container.querySelectorAll('.chat-message-wrapper');
    let lastDate = null;

    wrappers.forEach(function(wrapper, index) {
        const msgDate = wrapper.getAttribute('data-message-date');
        if (!msgDate) return;
        if (msgDate !== lastDate) {
            const divider = document.createElement('div');
            divider.className = 'chat-date-divider';
            const parts = msgDate.split('-');
            if (parts.length === 3) {
                divider.textContent = parts[2] + '.' + parts[1] + '.' + parts[0];
            } else {
                divider.textContent = msgDate;
            }
            container.insertBefore(divider, wrapper);
            lastDate = msgDate;
        }
    });
}

// Автопрокрутка вниз при загрузке
document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.querySelector('.chat-messages');
    if (chatMessages) {
        addDateDividers(chatMessages);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});

// ============================================================
// ОТПРАВКА СООБЩЕНИЯ ЧЕРЕЗ AJAX (без перезагрузки страницы)
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('chatSendForm');
    const textInput = document.getElementById('chatTextInput');
    const fileInput = document.getElementById('chat-attachment');
    const messagesContainer = document.querySelector('.chat-messages');

    if (!form || !messagesContainer) return;

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const text = textInput.value.trim();
        const files = fileInput.files;

        if (!text && files.length === 0) return;

        const formData = new FormData();
        formData.append('ticket_id', form.querySelector('[name="ticket_id"]').value);
        formData.append('text', text);
        formData.append('csrfmiddlewaretoken', form.querySelector('[name="csrfmiddlewaretoken"]').value);
        for (let i = 0; i < files.length; i++) {
            formData.append('attachment', files[i]);
        }

        // URL отправки сообщений передаётся шаблоном через data-send-url формы
        fetch(form.dataset.sendUrl || '/send-message/', {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                alert(data.message || 'Ошибка отправки сообщения');
                return;
            }

            const m = data.message;

            // Проверяем, сменился ли день — добавляем разделитель если да
            const container = document.querySelector('.chat-messages');
            const allWrappers = container.querySelectorAll('.chat-message-wrapper');
            const lastWrapper = allWrappers.length > 0 ? allWrappers[allWrappers.length - 1] : null;
            // Используем full_created_at (полная ISO-дата), а не created_at (только время "ЧЧ:ММ")
            const isoDateTime = (m && m.full_created_at) ? m.full_created_at : '';
            if (!isoDateTime) {
                console.error("Сервер не вернул дату создания сообщения:", m);
            }
            // Fallback: текущая дата, чтобы страница не сломалась
            var newDate = isoDateTime
              ? isoDateTime.slice(0, 10)
              : new Date().toISOString().slice(0, 10);
            let needsDivider = false;
            if (!lastWrapper) {
              // Первое сообщение
              needsDivider = true;
            } else {
              const lastDate = lastWrapper.getAttribute('data-message-date');
              if (lastDate !== newDate) {
                needsDivider = true;
              }
            }

            if (needsDivider) {
              const divider = document.createElement('div');
              divider.className = 'chat-date-divider';
              const parts = newDate.split('-');
              divider.textContent = (parts.length === 3)
                ? parts[2] + '.' + parts[1] + '.' + parts[0]
                : newDate;
              messagesContainer.appendChild(divider);
            }

            // Строим HTML исходящего сообщения (от посетителя)
            const wrapper = document.createElement('div');
            wrapper.className = 'chat-message-wrapper chat-message-wrapper--outgoing';
            wrapper.setAttribute('data-message-date', newDate);
            const outerDiv = document.createElement('div');
            outerDiv.className = 'chat-message chat-message--outgoing';
            let bubbleContent = escapeHtml(m.text);
            if (m.attachments && m.attachments.length) {
              m.attachments.forEach(function(att) {
                bubbleContent += '<br><a href="' + att.url + '" target="_blank" style="color:#fff;text-decoration:underline;">📎 ' + att.name + '</a>';
              });
            }
            outerDiv.innerHTML =
              '<div class="chat-message-bubble-row">' +
                '<div class="chat-message-bubble">' + bubbleContent + '</div>' +
                '<div class="chat-message-time">' + m.created_at + '</div>' +
              '</div>';
            wrapper.appendChild(outerDiv);

            messagesContainer.appendChild(wrapper);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            textInput.value = '';
            fileInput.value = '';
        })
        .catch(err => {
            console.error('Ошибка:', err);
            alert('Произошла ошибка при отправке сообщения');
        });
    });
});

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
