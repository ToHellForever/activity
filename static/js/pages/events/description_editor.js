(function () {
    "use strict";

    const allowedSizes = new Set(["13", "14", "15", "16", "17", "18", "19", "20"]);
    const markerPattern = /^\[\[size=(1[3-9]|20)\]\]([\s\S]*)\[\[\/size\]\]$/;

    function appendTextWithBreaks(parent, text) {
        text.split("\n").forEach((part, index) => {
            if (index > 0) {
                parent.appendChild(document.createElement("br"));
            }
            parent.appendChild(document.createTextNode(part));
        });
    }

    function createParagraph(editor, line, defaultSize) {
        const paragraph = document.createElement("div");
        paragraph.className = "event-description-editor-paragraph";
        paragraph.dataset.descriptionParagraph = "";

        const match = line.match(markerPattern);
        if (match) {
            paragraph.dataset.descriptionFontSize = match[1];
            paragraph.style.fontSize = `${match[1]}px`;
            appendTextWithBreaks(paragraph, match[2]);
        } else {
            paragraph.dataset.descriptionFontSize = defaultSize;
            paragraph.style.fontSize = `${defaultSize}px`;
            appendTextWithBreaks(paragraph, line);
        }
        editor.appendChild(paragraph);
    }

    function serializeNode(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            return node.nodeValue || "";
        }
        if (node.nodeType !== Node.ELEMENT_NODE) {
            return "";
        }
        if (node.tagName === "BR") {
            return "\n";
        }
        const childSeparator = ["DIV", "P"].includes(node.tagName) ? "\n" : "";
        return Array.from(node.childNodes, serializeNode).join(childSeparator);
    }

    function serializeParagraph(paragraph, defaultSize) {
        const text = serializeNode(paragraph);
        const size = paragraph.dataset.descriptionFontSize;
        if (!allowedSizes.has(size) || size === defaultSize) {
            return text;
        }
        return text
            .split("\n")
            .map((line) => `[[size=${size}]]${line}[[/size]]`)
            .join("\n");
    }

    function directParagraphs(editor, fallbackSize) {
        return Array.from(editor.children).map((paragraph) => {
            if (!paragraph.matches("[data-description-paragraph]")) {
                paragraph.classList.add("event-description-editor-paragraph");
                paragraph.dataset.descriptionParagraph = "";
                if (!allowedSizes.has(paragraph.dataset.descriptionFontSize)) {
                    const inheritedSize = parseInt(paragraph.style.fontSize, 10);
                    const size = allowedSizes.has(String(inheritedSize))
                        ? String(inheritedSize)
                        : fallbackSize;
                    paragraph.dataset.descriptionFontSize = size;
                    paragraph.style.fontSize = `${size}px`;
                }
            }
            return paragraph;
        });
    }

    function initialize(textarea) {
        if (textarea.dataset.descriptionEditorReady === "true") {
            return;
        }

        const fieldGroup = textarea.closest(".form-group") || textarea.parentElement;
        const sizeField = document.getElementById("id_description_font_size");
        let toolbar = fieldGroup.querySelector("[data-description-toolbar]");
        let editor = fieldGroup.querySelector("[data-description-editor]");
        let applyButton = fieldGroup.querySelector("[data-description-apply-size]");

        if (!toolbar) {
            toolbar = document.createElement("div");
            toolbar.className = "event-description-editor-toolbar";
            toolbar.dataset.descriptionToolbar = "";
            if (sizeField && sizeField.parentElement !== toolbar) {
                const originalFieldRow = sizeField.closest(".form-row");
                const label = document.createElement("label");
                label.htmlFor = sizeField.id;
                label.textContent = "Размер текста по умолчанию";
                toolbar.appendChild(label);
                toolbar.appendChild(sizeField);
                if (originalFieldRow && !originalFieldRow.contains(sizeField)) {
                    originalFieldRow.remove();
                }
            }
            fieldGroup.insertBefore(toolbar, textarea);
        }

        if (!applyButton) {
            applyButton = document.createElement("button");
            applyButton.type = "button";
            applyButton.className = "btn btn-outline-secondary";
            applyButton.dataset.descriptionApplySize = "";
            applyButton.textContent = "Применить к абзацу";
            toolbar.appendChild(applyButton);
        }

        if (!editor) {
            editor = document.createElement("div");
            editor.className = "event-description-editor";
            editor.dataset.descriptionEditor = "";
            toolbar.insertAdjacentElement("afterend", editor);
        }

        const defaultSize = sizeField && allowedSizes.has(sizeField.value)
            ? sizeField.value
            : "13";
        editor.contentEditable = "true";
        editor.setAttribute("role", "textbox");
        editor.setAttribute("aria-multiline", "true");
        editor.style.fontSize = `${defaultSize}px`;
        textarea.value.split("\n").forEach((line) => createParagraph(editor, line, defaultSize));
        if (!editor.firstChild) {
            createParagraph(editor, "", defaultSize);
        }

        textarea.hidden = true;
        textarea.dataset.descriptionEditorReady = "true";

        let savedRange = null;
        let activeParagraph = directParagraphs(editor, defaultSize)[0];

        function rememberSelection() {
            const selection = window.getSelection();
            if (!selection || !selection.rangeCount) {
                return;
            }
            const range = selection.getRangeAt(0);
            if (!editor.contains(range.commonAncestorContainer)) {
                return;
            }
            savedRange = range.cloneRange();
            let node = range.startContainer;
            if (node.nodeType === Node.TEXT_NODE) {
                node = node.parentElement;
            }
            const paragraph = node && node.closest("[data-description-paragraph]");
            if (paragraph && editor.contains(paragraph)) {
                activeParagraph = paragraph;
            }
        }

        function applySizeToCurrentParagraphs(selectedSize) {
            if (!allowedSizes.has(selectedSize)) {
                return;
            }

            const selection = window.getSelection();
            if (selection && savedRange) {
                selection.removeAllRanges();
                selection.addRange(savedRange);
            }
            const range = selection && selection.rangeCount ? selection.getRangeAt(0) : null;
            const paragraphs = directParagraphs(editor, defaultSize);
            let targets = range
                ? paragraphs.filter((paragraph) => {
                    try {
                        return range.intersectsNode(paragraph);
                    } catch (_error) {
                        return false;
                    }
                })
                : [];

            if (!targets.length && range) {
                let node = range.startContainer;
                if (node.nodeType === Node.TEXT_NODE) {
                    node = node.parentElement;
                }
                const paragraph = node && node.closest("[data-description-paragraph]");
                if (paragraph && editor.contains(paragraph)) {
                    targets = [paragraph];
                }
            }
            if (!targets.length && activeParagraph && editor.contains(activeParagraph)) {
                targets = [activeParagraph];
            }

            targets.forEach((paragraph) => {
                paragraph.dataset.descriptionFontSize = selectedSize;
                paragraph.style.fontSize = `${selectedSize}px`;
            });
            if (targets.length) {
                activeParagraph = targets[0];
            }
            syncTextarea();
            rememberSelection();
        }

        if (sizeField) {
            sizeField.addEventListener("mousedown", rememberSelection);
            sizeField.addEventListener("change", () => {
                applySizeToCurrentParagraphs(sizeField.value);
            });
        }

        editor.addEventListener("keyup", rememberSelection);
        editor.addEventListener("mouseup", rememberSelection);
        editor.addEventListener("click", rememberSelection);
        applyButton.addEventListener("mousedown", (event) => {
            rememberSelection();
            event.preventDefault();
        });
        applyButton.addEventListener("click", () => {
            applySizeToCurrentParagraphs(sizeField && sizeField.value);
        });

        function syncTextarea() {
            const currentDefaultSize = sizeField && allowedSizes.has(sizeField.value)
                ? sizeField.value
                : "13";
            textarea.value = directParagraphs(editor, currentDefaultSize)
                .map((paragraph) => serializeParagraph(paragraph, currentDefaultSize))
                .join("\n");
        }

        editor.addEventListener("input", () => {
            const currentSize = sizeField && allowedSizes.has(sizeField.value)
                ? sizeField.value
                : defaultSize;
            directParagraphs(editor, currentSize).forEach((paragraph) => {
                if (!allowedSizes.has(paragraph.dataset.descriptionFontSize)) {
                    paragraph.dataset.descriptionFontSize = currentSize;
                    paragraph.style.fontSize = `${currentSize}px`;
                }
            });
            rememberSelection();
            syncTextarea();
        });
        const form = textarea.form;
        if (form) {
            form.addEventListener("submit", syncTextarea);
        }
        syncTextarea();
    }

    document.addEventListener("DOMContentLoaded", () => {
        const textarea = document.getElementById("id_description");
        if (textarea) {
            initialize(textarea);
        }
    });
})();
