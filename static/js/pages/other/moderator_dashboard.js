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

// === ПОИСК ПОЛЬЗОВАТЕЛЯ И СОЗДАНИЕ НОВОГО ОБРАЩЕНИЯ АДМИНОМ ===
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('userSearchInput');
    const resultsBox = document.getElementById('searchResults');
    if (!searchInput || !resultsBox) return;

    const userIdField = document.getElementById('selectedUserId');
    const selectedUserBox = document.getElementById('selectedUserBox');
    const selectedUserLabel = document.getElementById('selectedUserLabel');
    const clearBtn = document.getElementById('clearSelectedUser');

    let searchTimer = null;
    let items = [];      // текущий список пользователей в дропдауне
    let activeIndex = -1;

    function hideResults() {
        resultsBox.style.display = 'none';
        resultsBox.innerHTML = '';
        items = [];
        activeIndex = -1;
    }

    function selectUser(user) {
        userIdField.value = user.id;
        const label = user.name + (user.email ? ' (' + user.email + ')' : '') +
            (user.user_type ? ' — ' + user.user_type : '');
        selectedUserLabel.textContent = label;
        selectedUserBox.style.display = 'block';
        hideResults();
        searchInput.value = '';
    }

    function setActive(idx) {
        const nodes = resultsBox.querySelectorAll('.search-result-item');
        nodes.forEach(function(n) { n.classList.remove('active'); });
        if (idx >= 0 && nodes[idx]) {
            activeIndex = idx;
            nodes[idx].classList.add('active');
            nodes[idx].scrollIntoView({ block: 'nearest' });
        }
    }

    function renderResults(users) {
        resultsBox.innerHTML = '';
        if (!users.length) {
            resultsBox.innerHTML = '<div class="search-hint">Никого не найдено.</div>';
            resultsBox.style.display = 'block';
            items = [];
            activeIndex = -1;
            return;
        }
        items = users;
        activeIndex = -1;
        users.forEach(function(user) {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            const emailHtml = user.email ? '<div class="u-type">' + escapeHtml(user.email) + '</div>' : '';
            const typeHtml = user.user_type ? ' <span class="u-type">— ' + escapeHtml(user.user_type) + '</span>' : '';
            item.innerHTML =
                '<div><strong>' + escapeHtml(user.name) + '</strong>' + typeHtml + '</div>' + emailHtml;
            item.addEventListener('mousedown', function(e) {
                e.preventDefault();
                selectUser(user);
            });
            resultsBox.appendChild(item);
        });
        resultsBox.style.display = 'block';
    }

    function doSearch(query) {
        resultsBox.innerHTML = '<div class="search-hint">Поиск…</div>';
        resultsBox.style.display = 'block';
        const url = (searchInput.dataset.searchUrl || '/moderator/search-users/') +
                    '?q=' + encodeURIComponent(query);
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.json())
            .then(data => renderResults(data.users || []))
            .catch(function() { hideResults(); });
    }

    searchInput.addEventListener('input', function() {
        const query = searchInput.value.trim();
        if (searchTimer) clearTimeout(searchTimer);
        if (query.length < 1) {
            hideResults();
            return;
        }
        searchTimer = setTimeout(function() { doSearch(query); }, 250);
    });

    // Навигация стрелками и выбор по Enter
    searchInput.addEventListener('keydown', function(e) {
        if (!items.length || resultsBox.style.display === 'none') return;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive(Math.min(activeIndex + 1, items.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive(Math.max(activeIndex - 1, 0));
        } else if (e.key === 'Enter') {
            if (activeIndex >= 0) {
                e.preventDefault();
                selectUser(items[activeIndex]);
            }
        } else if (e.key === 'Escape') {
            hideResults();
        }
    });

    // Скрытие списка при клике вне поиска
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.user-search-wrap')) hideResults();
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            userIdField.value = '';
            selectedUserBox.style.display = 'none';
            selectedUserLabel.textContent = '';
            searchInput.focus();
        });
    }

    const composeForm = document.getElementById('composeTicketForm');
    if (composeForm) {
        composeForm.addEventListener('submit', function(e) {
            if (!userIdField.value) {
                e.preventDefault();
                alert('Сначала найдите и выберите пользователя');
                searchInput.focus();
            }
        });
    }
});

