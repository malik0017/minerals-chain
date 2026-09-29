/*
 * app/static/js/lang_sync.js — Batch R1
 *
 * ONE language mechanism for the whole platform. The server is the single
 * source of truth: users.preferred_language (or the mc_lang cookie before
 * login) decides <html lang> and <html dir> on every render, and the
 * TranslationMiddleware translates the page. This script only makes every
 * language / direction control on the page go through that one path:
 *
 *   header language menu, profile-menu language submenu, the Personalize
 *   page "Language & text direction" buttons, AND the theme's own
 *   "Change layout text direction" LTR/RTL switch (#btn-layout-dir-rtl)
 *   → GET /language/set?lang=ar|en → saved on the account → page reloads
 *     translated and in the right direction.
 *
 * Why this replaces language_switcher.js: that script kept its OWN
 * language/direction in localStorage and re-applied dir="ltr" on every page
 * load, overriding the server's dir="rtl" — which is exactly why choosing
 * Arabic changed a few words but never flipped the layout. It also stops the
 * theme's direction switch from flipping ONLY the layout (Arabic reading
 * right-to-left with English text left in place).
 */
(function () {
  "use strict";

  var html = document.documentElement;

  function serverLang() {
    return (html.getAttribute("lang") || "en").slice(0, 2) === "ar" ? "ar" : "en";
  }

  function switchTo(lang) {
    if (lang !== "ar" && lang !== "en") return;
    if (lang === serverLang()) return;
    var next = window.location.pathname + window.location.search;
    window.location.href = "/language/set?lang=" + lang + "&next=" + encodeURIComponent(next);
  }

  // 1. Remove stale client-side overrides left by the old switcher / theme so
  //    nothing can fight the server-rendered direction again.
  try {
    ["language", "direction", "adminuiuxdirectionmode"].forEach(function (k) {
      window.localStorage.removeItem(k);
    });
  } catch (e) { /* storage blocked — nothing to clean */ }
  html.setAttribute("dir", serverLang() === "ar" ? "rtl" : "ltr");

  document.addEventListener("DOMContentLoaded", function () {
    var isAr = serverLang() === "ar";

    // 2. Theme LTR/RTL switches reflect the real state…
    ["btn-layout-dir-rtl", "btn-layout-dir-rtl-page", "btn-layout-RTL"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.checked = isAr;
    });
  });

  // 3. …and changing one switches LANGUAGE + direction together. Capture
  //    phase on document runs before the theme's own jQuery handler, which
  //    would otherwise flip only dir.
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (!t || !t.id) return;
    if (t.id === "btn-layout-dir-rtl" || t.id === "btn-layout-dir-rtl-page" || t.id === "btn-layout-RTL") {
      e.stopImmediatePropagation();
      switchTo(t.checked ? "ar" : "en");
    }
  }, true);

  // 4. Any element with data-lang="ar|en" (buttons, menu items) switches too.
  document.addEventListener("click", function (e) {
    var el = e.target.closest ? e.target.closest("[data-lang]") : null;
    if (!el) return;
    e.preventDefault();
    switchTo(el.getAttribute("data-lang"));
  }, true);
})();
