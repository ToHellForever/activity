// === SUPPORT DASHBOARD ===

document.addEventListener('DOMContentLoaded', function() {
    const newBtn = document.getElementById('new-ticket-btn');
    const form = document.getElementById('new-ticket-form');
    const cancelBtn = document.getElementById('cancel-ticket-btn');
    const attachmentInput = document.getElementById('attachment');
    const fileText = document.getElementById('file-text');
    const fileCount = document.getElementById('file-count');

    if (newBtn && form && cancelBtn) {
        newBtn.addEventListener('click', function() {
            form.style.display = 'flex';
            newBtn.style.display = 'none';
        });

        cancelBtn.addEventListener('click', function() {
            form.style.display = 'none';
            newBtn.style.display = 'block';
            form.reset();
            fileText.textContent = 'Выберите файлы';
            fileCount.style.display = 'none';
        });
    }

    if (attachmentInput) {
        attachmentInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                fileText.textContent = this.files[0].name;
                if (this.files.length > 1) {
                    fileCount.textContent = `+${this.files.length - 1}`;
                    fileCount.style.display = 'inline';
                } else {
                    fileCount.style.display = 'none';
                }
            } else {
                fileText.textContent = 'Выберите файлы';
                fileCount.style.display = 'none';
            }
        });
    }

    // Фильтры обращений
    const filterBtns = document.querySelectorAll('.ticket-filter-btn');
    filterBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const filter = this.getAttribute('data-filter');
            const url = new URL(window.location.href);
            if (filter === 'all') {
                url.searchParams.delete('ticket_filter');
            } else {
                url.searchParams.set('ticket_filter', filter);
            }
            window.location.href = url.toString();
        });
    });
});

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

// Автопрокрутка вниз при загрузке страницы
const supportHistoryInit = document.querySelector('.support-chat-history');
if (supportHistoryInit) {
    supportHistoryInit.scrollTop = supportHistoryInit.scrollHeight;
}

const supportForm = document.getElementById('chatSendForm');
const supportTextInput = document.getElementById('chatTextInput');
const supportFileInput = document.getElementById('chat-attachment');
const supportHistory = document.querySelector('.support-chat-history');

if (supportForm && supportHistory) {
    supportForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const text = supportTextInput.value.trim();
        const files = supportFileInput.files;

        if (!text && files.length === 0) return;

        const formData = new FormData();
        formData.append('ticket_id', supportForm.querySelector('[name="ticket_id"]').value);
        formData.append('text', text);
        formData.append('csrfmiddlewaretoken', supportForm.querySelector('[name="csrfmiddlewaretoken"]').value);
        for (let i = 0; i < files.length; i++) {
            formData.append('attachment', files[i]);
        }

        // URL отправки сообщений передаётся шаблоном через data-send-url формы
        fetch(supportForm.dataset.sendUrl || '/send-message/', {
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
            wrapper.className = 'support-message ' + (m.is_from_user ? 'user' : 'agent');

            let bubbleContent = escapeHtml(m.text);
            if (m.attachments && m.attachments.length) {
                m.attachments.forEach(function(att) {
                    bubbleContent += '<div class="attachments"><a href="' + att.url + '" target="_blank" class="attachment-link" title="' + att.name + '">📄 Файл</a></div>';
                });
            }

            const avatarHtml = m.is_from_user
                ? '<span class="sender-initials">ВЫ</span>'
                : '<img src="/media/icon/fluent_person-support-20-filled.svg" alt="">';

            wrapper.innerHTML =
                '<div class="support-avatar">' + avatarHtml + '</div>' +
                '<div class="support-message-body">' +
                    '<div class="support-bubble">' + bubbleContent + '</div>' +
                    '<div class="support-message-time">' + m.created_at + '</div>' +
                '</div>';

            supportHistory.appendChild(wrapper);
            supportHistory.scrollTop = supportHistory.scrollHeight;

            supportTextInput.value = '';
            supportFileInput.value = '';
        })
        .catch(err => {
            console.error('Ошибка:', err);
            alert('Произошла ошибка при отправке сообщения');
        });
    });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
