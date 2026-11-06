(function () {
  var initialBar = document.querySelector(".visitor-pagination-bar");
  if (initialBar) {
    var initialState = Object.assign({}, window.history.state || {}, {
      visitorPagination: initialBar.dataset.rowId,
    });
    window.history.replaceState(initialState, "", window.location.href);
  }

  function getPageElements(doc, rowId) {
    return {
      row: doc.getElementById(rowId),
      bar: doc.querySelector(
        '.visitor-pagination-bar[data-row-id="' + rowId + '"]'
      ),
    };
  }

  async function loadPage(url, rowId, shouldPushState) {
    var current = getPageElements(document, rowId);
    if (!current.row || !current.bar) {
      throw new Error("Не найдены список билетов или пагинатор.");
    }

    current.bar.setAttribute("aria-busy", "true");
    try {
      var response = await fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) {
        throw new Error("Сервер вернул ошибку " + response.status);
      }

      var html = await response.text();
      var nextDoc = new DOMParser().parseFromString(html, "text/html");
      var next = getPageElements(nextDoc, rowId);
      if (!next.row || !next.bar) {
        throw new Error("В ответе сервера не найдены список билетов или пагинатор.");
      }

      current.row.replaceWith(next.row);
      current.bar.replaceWith(next.bar);
      if (shouldPushState) {
        window.history.pushState({ visitorPagination: rowId }, "", url);
      }
      next.row.scrollIntoView({ behavior: "smooth", block: "start" });
    } finally {
      var updatedBar = getPageElements(document, rowId).bar;
      if (updatedBar) updatedBar.removeAttribute("aria-busy");
    }
  }

  document.addEventListener("click", function (event) {
    var link = event.target.closest(".visitor-pagination-link");
    if (
      !link ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    var bar = link.closest(".visitor-pagination-bar");
    if (bar.getAttribute("aria-busy") === "true") return;

    event.preventDefault();
    var rowId = bar.dataset.rowId;
    loadPage(link.href, rowId, true).catch(function (error) {
      console.error("Не удалось загрузить страницу билетов:", error);
      var errorMessage = document.createElement("p");
      errorMessage.className = "visitor-pagination-error";
      errorMessage.setAttribute("role", "alert");
      errorMessage.textContent = "Не удалось загрузить страницу. Попробуйте ещё раз.";
      var currentBar = getPageElements(document, rowId).bar;
      if (currentBar) {
        var oldMessage = currentBar.parentNode.querySelector(
          ".visitor-pagination-error"
        );
        if (oldMessage) oldMessage.remove();
        currentBar.insertAdjacentElement("afterend", errorMessage);
      }
    });
  });

  window.addEventListener("popstate", function () {
    var state = window.history.state;
    if (!state || !state.visitorPagination) return;
    loadPage(window.location.href, state.visitorPagination, false).catch(
      function (error) {
        console.error("Не удалось восстановить страницу билетов:", error);
      }
    );
  });
})();
