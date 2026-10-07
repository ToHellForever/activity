/**
 * Автодополнение партнёров в форме реестра продаж.
 *
 * При фокусе на инпуте показывается список всех партнёров.
 * При вводе текста список фильтруется по email (и по имени).
 * Клик по элементу выбирает партнёра (id уходит в hidden input).
 * Крестик/очистка инпута сбрасывает выбор — реестр формируется по всем.
 */
document.addEventListener("DOMContentLoaded", function () {
    var input = document.getElementById("partner_search");
    var list = document.getElementById("partner_list");
    var hidden = document.getElementById("partner_id");
    var selectedInfo = document.getElementById("partner_selected");
    if (!input || !list || !hidden) return;

    var partners = window.SALES_REGISTER_PARTNERS || [];
    var selectedPartner = null;
    var activeIndex = -1;

    function renderList(items) {
        list.innerHTML = "";
        if (!items.length) {
            var empty = document.createElement("div");
            empty.className = "partner-autocomplete-empty";
            empty.textContent = "Ничего не найдено";
            list.appendChild(empty);
        } else {
            items.forEach(function (p) {
                var item = document.createElement("div");
                item.className = "partner-autocomplete-item";
                item.dataset.id = p.id;

                var email = document.createElement("div");
                email.className = "email";
                email.textContent = p.email;
                item.appendChild(email);

                if (p.name && p.name !== p.email) {
                    var name = document.createElement("div");
                    name.className = "name";
                    name.textContent = p.name;
                    item.appendChild(name);
                }

                item.addEventListener("mousedown", function (e) {
                    // mousedown, чтобы сработать до blur инпута
                    e.preventDefault();
                    selectPartner(p);
                });

                list.appendChild(item);
            });
        }
        list.classList.remove("d-none");
    }

    function filterPartners(query) {
        var q = query.trim().toLowerCase();
        if (!q) return partners;
        return partners.filter(function (p) {
            return (
                p.email.toLowerCase().indexOf(q) !== -1 ||
                (p.name && p.name.toLowerCase().indexOf(q) !== -1)
            );
        });
    }

    function selectPartner(p) {
        selectedPartner = p;
        input.value = p.email;
        hidden.value = p.id;
        selectedInfo.textContent =
            "Выбран партнёр: " + (p.name ? p.name + " (" + p.email + ")" : p.email);
        hideList();
        activeIndex = -1;
    }

    function resetSelection() {
        selectedPartner = null;
        hidden.value = "";
        selectedInfo.textContent = "Будут показаны все партнёры";
    }

    function hideList() {
        list.classList.add("d-none");
        list.innerHTML = "";
        activeIndex = -1;
    }

    function setActive(items, index) {
        var children = list.querySelectorAll(".partner-autocomplete-item");
        children.forEach(function (el) {
            el.classList.remove("active");
        });
        if (index >= 0 && index < children.length) {
            children[index].classList.add("active");
            children[index].scrollIntoView({ block: "nearest" });
        }
    }

    input.addEventListener("focus", function () {
        renderList(filterPartners(input.value));
    });

    input.addEventListener("input", function () {
        // Ручной ввод сбрасывает прежний выбор
        if (selectedPartner && input.value !== selectedPartner.email) {
            resetSelection();
        }
        renderList(filterPartners(input.value));
    });

    input.addEventListener("blur", function () {
        // Убираем список с задержкой, чтобы успел сработать mousedown
        setTimeout(hideList, 150);
    });

    input.addEventListener("keydown", function (e) {
        var items = list.querySelectorAll(".partner-autocomplete-item");
        if (list.classList.contains("d-none") || !items.length) return;

        if (e.key === "ArrowDown") {
            e.preventDefault();
            activeIndex = Math.min(activeIndex + 1, items.length - 1);
            setActive(items, activeIndex);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            activeIndex = Math.max(activeIndex - 1, 0);
            setActive(items, activeIndex);
        } else if (e.key === "Enter") {
            e.preventDefault();
            if (activeIndex >= 0 && activeIndex < items.length) {
                var id = items[activeIndex].dataset.id;
                var partner = partners.find(function (p) {
                    return String(p.id) === String(id);
                });
                if (partner) selectPartner(partner);
            }
        } else if (e.key === "Escape") {
            hideList();
        }
    });
});
