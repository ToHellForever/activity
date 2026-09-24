/**
 * Вложения в переписке (техподдержка, чаты посетителя и организатора).
 *
 * Делает три вещи:
 * 1. Показывает превью выбранных фото полосой над строкой ввода (без размера).
 * 2. Разрешает отправить сообщение без текста, если прикреплёно хотя бы одно фото.
 * 3. Рендерит фото в сообщениях сеткой: одно фото — на всю ширину,
 *    два и больше — по два в ряд, подпись идёт под сеткой.
 */
window.ChatAttachments = (function () {
    const MAX_COUNT = 5;
    const MAX_SIZE_MB = 10;
    const ALLOWED_EXT = ['jpg', 'jpeg', 'png', 'gif', 'webp'];

    function extensionOf(name) {
        const dot = String(name || '').lastIndexOf('.');
        return dot === -1 ? '' : String(name).slice(dot + 1).toLowerCase();
    }

    /** Возвращает текст ошибки или null, если вложения допустимы. */
    function validate(files) {
        const list = Array.from(files || []);

        if (list.length > MAX_COUNT) {
            return `Можно прикрепить не более ${MAX_COUNT} фото`;
        }

        for (const file of list) {
            if (!ALLOWED_EXT.includes(extensionOf(file.name))) {
                return `«${file.name}» — можно прикреплять только фото (${ALLOWED_EXT.join(', ')})`;
            }
            if (file.size > MAX_SIZE_MB * 1024 * 1024) {
                return `«${file.name}» больше ${MAX_SIZE_MB} МБ`;
            }
        }

        return null;
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(
            /[&<>"']/g,
            (symbol) => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;',
            })[symbol]
        );
    }

    /** HTML сетки фото для сообщения. Пустная строка, если вложений нет. */
    function attachmentsHtml(attachments) {
        const list = Array.from(attachments || []);
        if (!list.length) return '';

        const items = list
            .map((attachment) => {
                const url = escapeHtml(attachment.url);
                const name = escapeHtml(attachment.name || 'Фото');
                return (
                    '<div class="message-attachment">' +
                        `<a href="${url}" target="_blank" rel="noopener" class="message-attachment-link">` +
                            `<img class="message-attachment-image" src="${url}" alt="${name}" loading="lazy">` +
                        '</a>' +
                    '</div>'
                );
            })
            .join('');

        return `<div class="message-attachments-grid${list.length > 1 ? ' message-attachments-grid--multiple' : ''}">${items}</div>`;
    }

    /**
     * Подключает превью и валидацию к форме с file-инпутом.
     * Полоса превью (.attachment-preview) располагается над строкой ввода,
     * поэтому при выборе файлов над инпутом появляется место под миниатюры.
     */
    function attachToForm(form) {
        const input = form.querySelector('.support-attachment-input') || form.querySelector('input[type="file"]');
        const preview = form.querySelector('.attachment-preview');
        if (!input || !preview) return;

        const textInput = form.querySelector('[name="text"]');
        let selected = [];

        function writeBackToInput() {
            const transfer = new DataTransfer();
            selected.forEach((file) => transfer.items.add(file));
            input.files = transfer.files;
        }

        function render() {
            preview.innerHTML = '';
            preview.hidden = selected.length === 0;

            selected.forEach((file, index) => {
                const item = document.createElement('div');
                item.className = 'attachment-preview-item';

                const image = document.createElement('img');
                image.className = 'attachment-preview-thumb';
                image.alt = file.name;
                const objectUrl = URL.createObjectURL(file);
                image.src = objectUrl;
                image.addEventListener('load', () => URL.revokeObjectURL(objectUrl), { once: true });

                const remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'attachment-preview-remove';
                remove.innerHTML = '&times;';
                remove.setAttribute('aria-label', `Убрать ${file.name}`);
                remove.title = 'Убрать';
                remove.addEventListener('click', () => {
                    selected.splice(index, 1);
                    writeBackToInput();
                    render();
                });

                item.appendChild(image);
                item.appendChild(remove);
                preview.appendChild(item);
            });
        }

        input.addEventListener('change', () => {
            const incoming = Array.from(input.files || []);
            const merged = selected.slice();

            incoming.forEach((file) => {
                const alreadyAdded = merged.some(
                    (existing) =>
                        existing.name === file.name &&
                        existing.size === file.size &&
                        existing.lastModified === file.lastModified
                );
                if (!alreadyAdded) merged.push(file);
            });

            const error = validate(merged);
            if (error) {
                alert(error);
                input.value = '';
                return;
            }

            selected = merged;
            input.value = '';
            writeBackToInput();
            render();
        });

        form.addEventListener('submit', (event) => {
            writeBackToInput();

            const hasText = Boolean(textInput && textInput.value.trim());
            // Фото можно отправить без подписи, пустое сообщение — нельзя.
            if (!hasText && !selected.length) {
                event.preventDefault();
                alert('Введите сообщение или прикрепите фото');
            }
        });

        render();
    }

    function init(root) {
        const scope = root || document;
        scope
            .querySelectorAll('form input[type="file"]')
            .forEach((input) => {
                const form = input.closest('form');
                if (form && !form.dataset.attachmentsBound) {
                    form.dataset.attachmentsBound = '1';
                    attachToForm(form);
                }
            });
    }

    document.addEventListener('DOMContentLoaded', () => init());

    return { init, validate, attachmentsHtml, attachToForm, MAX_COUNT, MAX_SIZE_MB };
})();
