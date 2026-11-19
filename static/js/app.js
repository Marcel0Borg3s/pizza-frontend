/* Theme toggle, password visibility and small progressive enhancements. */
(function () {
  "use strict";

  var root = document.documentElement;

  function applyTheme(theme) {
    root.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem("theme", theme);
    } catch (error) {
      /* storage can be disabled, the page still works */
    }
    /* The sun/moon swap is pure CSS (dark: variants); only the label changes. */
    document.querySelectorAll("[data-theme-toggle]").forEach(function (node) {
      node.setAttribute("aria-label", theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro");
      node.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    });
  }

  function currentTheme() {
    return root.classList.contains("dark") ? "dark" : "light";
  }

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-theme-toggle]");
    if (toggle) {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
      return;
    }

    var passwordButton = event.target.closest("[data-toggle-password]");
    if (passwordButton) {
      var wrapper = passwordButton.closest("[data-password-wrapper]");
      var input = wrapper ? wrapper.querySelector("input") : null;
      if (!input) return;
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      passwordButton.setAttribute("aria-pressed", show ? "true" : "false");
      passwordButton.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
    }
  });

  /* Confirm destructive actions without inline handlers. */
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form.matches("[data-confirm]") && !window.confirm(form.getAttribute("data-confirm"))) {
      event.preventDefault();
    }
  });

  applyTheme(currentTheme());
})();
