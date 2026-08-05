(function () {
  "use strict";

  // Menu lateral (sidebar): abre/fecha em telas pequenas via o botão
  // hambúrguer da barra superior; um overlay escurecido cobre o resto da
  // página e fecha a sidebar ao ser tocado (padrão comum de menu off-canvas).
  var toggle = document.getElementById("navToggle");
  var sidebar = document.getElementById("mainNav");
  var overlay = document.getElementById("sidebarOverlay");

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("is-open");
    if (overlay) overlay.classList.remove("is-open");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }

  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      var isOpen = sidebar.classList.toggle("is-open");
      if (overlay) overlay.classList.toggle("is-open", isOpen);
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }
  if (overlay) {
    overlay.addEventListener("click", closeSidebar);
  }
  // Fecha a sidebar automaticamente ao navegar por um link dela (evita ficar
  // aberta por cima da próxima página em telas pequenas).
  if (sidebar) {
    sidebar.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", closeSidebar);
    });
  }

  // Fecha alertas de flash automaticamente após um tempo (não bloqueia leitura).
  document.querySelectorAll(".flash").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity .4s ease";
      el.style.opacity = "0";
    }, 6000);
  });

  // Alternador de tema claro/escuro — o tema já foi aplicado antes da
  // renderização (script inline no <head>, evita "flash" de tema errado);
  // aqui só cuidamos do clique e de persistir a escolha em localStorage.
  var root = document.documentElement;
  function setTheme(theme) {
    if (theme === "dark") {
      root.setAttribute("data-theme", "dark");
    } else {
      root.removeAttribute("data-theme");
    }
    try { localStorage.setItem("theme", theme); } catch (e) { /* modo privado etc. */ }
  }
  document.querySelectorAll(".theme-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var isDark = root.getAttribute("data-theme") === "dark";
      setTheme(isDark ? "light" : "dark");
    });
  });
})();
