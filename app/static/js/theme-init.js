// Aplica o tema salvo ANTES da primeira renderização (evita "flash" de tema
// claro por uma fração de segundo ao carregar uma página em modo escuro).
// Precisa ser um arquivo externo (não inline) porque a CSP do sistema usa
// script-src 'self' sem 'unsafe-inline' — um <script> inline seria bloqueado
// silenciosamente pelo navegador. Carregado de forma síncrona no <head>
// (sem defer/async) para rodar antes do <body> ser pintado.
(function () {
  "use strict";
  try {
    var saved = localStorage.getItem("theme");
    var theme = saved || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    }
  } catch (e) {
    // localStorage indisponível (modo privado, cookies bloqueados etc.) — segue no tema claro/sistema.
  }
})();
