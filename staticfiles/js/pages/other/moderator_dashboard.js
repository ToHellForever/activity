// === MODERATOR DASHBOARD ===

// Решение для обработки вставки файлов
document.addEventListener('DOMContentLoaded', function() {
    const chatInput = document.querySelector('input[name="text"]');
    if (chatInput) {
        chatInput.addEventListener('paste', function(e) {
            if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length > 0) {
                e.preventDefault();
                alert('Чтобы загрузить файлы, пожалуйста, используйте кнопку выбора файлов рядом с полем ввода');
            }
        });
    }

    // ============================================================
    // ОТПРАВКА СООБЩЕНИЯ ЧЕРЕЗ AJAX (без перезагрузки страницы)
    // ============================================================
    const form = document.getElementById('chatSendForm');
    const textInput = document.getElementById('chatTextInput');
    const fileInput = document.getElementById('chatFileInput');
    const history = document.querySelector('.chat-history');

    if (!form || !history) return;

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
            const wrapper = document.createElement('div');
            wrapper.className = 'message ' + (m.is_from_user ? 'user' : 'moderator');

            let bubbleContent = escapeHtml(m.text);
            if (m.attachments && m.attachments.length) {
                m.attachments.forEach(function(att) {
                    bubbleContent += '<div style="margin-top: 8px;"><a href="' + att.url + '" target="_blank" style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.9em; color: #1890ff; text-decoration: none;">📎 ' + att.name + '</a></div>';
                });
            }

            wrapper.innerHTML =
                '<div style="display: flex; justify-content: space-between; margin-bottom: 4px;">' +
                    '<strong>' + escapeHtml(m.user_first_name || m.user_email) + '</strong>' +
                    '<span style="font-size: 0.8em; color: #888;">' + m.created_at + '</span>' +
                '</div>' +
                '<div>' + bubbleContent + '</div>';

            history.appendChild(wrapper);
            history.scrollTop = history.scrollHeight;

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
