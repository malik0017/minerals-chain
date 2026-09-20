/*
 * app/static/js/personalize.js
 */
(function () {
  "use strict";

  var STORAGE_KEY = "mc_personalize";
  var THEME_COLORS = [
    "blue", "indigo", "purple", "pink", "red", "orange", "yellow",
    "green", "teal", "cyan", "grey", "brown", "chocolate", "black",
  ];
  var BACKGROUNDS = ["theme", "gradient-1", "gradient-2", "gradient-3", "gradient-4",
    "gradient-5", "gradient-6", "gradient-7", "gradient-8", "gradient-9", "gradient-10"];
  var SIDEBAR_FILLS = ["bg", "white", "theme", "accent"];
  var HEADER_FILLS = ["bg", "white", "black", "theme", "accent"];
  var SIDEBAR_LAYOUTS = ["iconic", "boxed", "iconic-boxed"];
  var HEADER_LAYOUTS = ["boxed"];
  var BG_IMAGE_BASE = "/static/img/backgorund-image/backgorund-image-";

  function loadPrefs() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function savePrefs(prefs) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch (e) {
      /* localStorage unavailable (private browsing etc.) — preference
         just won't persist across page loads; nothing else breaks. */
    }
  }

  function removeClassesWithPrefix(el, prefix) {
    var toRemove = [];
    el.classList.forEach(function (c) {
      if (c.indexOf(prefix) === 0) toRemove.push(c);
    });
    toRemove.forEach(function (c) {
      el.classList.remove(c);
    });
  }

  function applyPrefs(prefs) {
    var html = document.documentElement;

    removeClassesWithPrefix(html, "theme-");
    if (prefs.themeColor && THEME_COLORS.indexOf(prefs.themeColor) !== -1) {
      html.classList.add("theme-" + prefs.themeColor);
    }

    removeClassesWithPrefix(html, "bg-gradient-");
    html.classList.remove("bg-r-gradient", "bg-white");
    if (prefs.background && BACKGROUNDS.indexOf(prefs.background) !== -1) {
      html.classList.add(
        prefs.background === "theme" ? "bg-r-gradient" : "bg-" + prefs.background
      );
    } else if (prefs.background === "white") {
      html.classList.add("bg-white");
    }

    removeClassesWithPrefix(html, "adminuiux-sidebar-fill-");
    if (prefs.sidebarFill && SIDEBAR_FILLS.indexOf(prefs.sidebarFill) !== -1) {
      html.classList.add("adminuiux-sidebar-fill-" + prefs.sidebarFill);
    }

    removeClassesWithPrefix(html, "adminuiux-header-fill-");
    if (prefs.headerFill && HEADER_FILLS.indexOf(prefs.headerFill) !== -1) {
      html.classList.add("adminuiux-header-fill-" + prefs.headerFill);
    }

    html.classList.remove("adminuiux-sidebar-iconic", "adminuiux-sidebar-boxed");
    if (prefs.sidebarLayout && SIDEBAR_LAYOUTS.indexOf(prefs.sidebarLayout) !== -1) {
      if (prefs.sidebarLayout === "iconic-boxed") {
        html.classList.add("adminuiux-sidebar-iconic", "adminuiux-sidebar-boxed");
      } else {
        html.classList.add("adminuiux-sidebar-" + prefs.sidebarLayout);
      }
    }

    removeClassesWithPrefix(html, "adminuiux-header-boxed");
    if (prefs.headerLayout && HEADER_LAYOUTS.indexOf(prefs.headerLayout) !== -1) {
      html.classList.add("adminuiux-header-" + prefs.headerLayout);
    }

    if (prefs.bgImage) {
      html.style.setProperty("--adminuiux-main-bg", "url(" + BG_IMAGE_BASE + prefs.bgImage + ".jpg)");
    } else {
      html.style.removeProperty("--adminuiux-main-bg");
    }

    if (prefs.colorMode === "dark") {
      html.classList.add("dark");
      html.setAttribute("data-bs-theme", "dark");
    } else {
      html.classList.remove("dark");
      html.setAttribute("data-bs-theme", "light");
    }
  }

  // Apply as early as possible (called inline from base.html's <head>,
  // before the rest of the page — including this file — has loaded).
  window.__mcApplyPersonalize = function () {
    applyPrefs(loadPrefs());
  };

  function setPreference(key, value) {
    var prefs = loadPrefs();
    prefs[key] = value;
    savePrefs(prefs);
    applyPrefs(prefs);
  }

  function resetPreference(key) {
    var prefs = loadPrefs();
    delete prefs[key];
    savePrefs(prefs);
    applyPrefs(prefs);
  }

  // Wires up the Personalize page's swatches/buttons — only relevant
  // on that page, but harmless to attach everywhere (no-ops if the
  // elements aren't present).
  document.addEventListener("DOMContentLoaded", function () {
    var prefs = loadPrefs();
    applyPrefs(prefs);

    document.querySelectorAll("[data-personalize-theme-color]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.getAttribute("data-personalize-theme-color");
        v === "none" ? resetPreference("themeColor") : setPreference("themeColor", v);
        markActive("[data-personalize-theme-color]", btn);
      });
    });
    document.querySelectorAll("[data-personalize-background]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.getAttribute("data-personalize-background");
        v === "none" ? resetPreference("background") : setPreference("background", v);
        markActive("[data-personalize-background]", btn);
      });
    });
    document.querySelectorAll("[data-personalize-sidebar-fill]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.getAttribute("data-personalize-sidebar-fill");
        v === "none" ? resetPreference("sidebarFill") : setPreference("sidebarFill", v);
        markActive("[data-personalize-sidebar-fill]", btn);
      });
    });
    document.querySelectorAll("[data-personalize-header-fill]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.getAttribute("data-personalize-header-fill");
        v === "none" ? resetPreference("headerFill") : setPreference("headerFill", v);
        markActive("[data-personalize-header-fill]", btn);
      });
    });
    document.querySelectorAll("[data-personalize-sidebar-layout]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.getAttribute("data-personalize-sidebar-layout");
        v === "none" ? resetPreference("sidebarLayout") : setPreference("sidebarLayout", v);
        markActive("[data-personalize-sidebar-layout]", btn);
      });
    });
    document.querySelectorAll("[data-personalize-header-layout]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.getAttribute("data-personalize-header-layout");
        v === "none" ? resetPreference("headerLayout") : setPreference("headerLayout", v);
        markActive("[data-personalize-header-layout]", btn);
      });
    });
    document.querySelectorAll("[data-personalize-bg-image]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.getAttribute("data-personalize-bg-image");
        v === "none" ? resetPreference("bgImage") : setPreference("bgImage", v);
        markActive("[data-personalize-bg-image]", btn);
      });
    });

    var darkSwitch = document.getElementById("personalize-color-mode");
    if (darkSwitch) {
      darkSwitch.checked = prefs.colorMode === "dark";
      darkSwitch.addEventListener("change", function () {
        setPreference("colorMode", darkSwitch.checked ? "dark" : "light");
      });
    }

    // Reflect currently-active choices on page load (adds a visual
    // "selected" ring to the matching swatch/button, if present).
    ["themeColor", "background", "sidebarFill", "headerFill", "sidebarLayout", "headerLayout", "bgImage"].forEach(function (key) {
      var attr = {
        themeColor: "data-personalize-theme-color",
        background: "data-personalize-background",
        sidebarFill: "data-personalize-sidebar-fill",
        headerFill: "data-personalize-header-fill",
        sidebarLayout: "data-personalize-sidebar-layout",
        headerLayout: "data-personalize-header-layout",
        bgImage: "data-personalize-bg-image",
      }[key];
      var value = prefs[key] || "none";
      var el = document.querySelector("[" + attr + '="' + value + '"]');
      if (el) markActive(attr, el);
    });

    function markActive(selector, activeEl) {
      document.querySelectorAll("[" + selector.replace(/[\[\]]/g, "") + "]").forEach(function (el) {
        el.classList.remove("personalize-active");
      });
      activeEl.classList.add("personalize-active");
    }
  });
})();
