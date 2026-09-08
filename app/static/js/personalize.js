
(function () {
  'use strict';

  var KEYS = {
    theme: 'adminuiuxtheme',
    background: 'adminuiuxbackground',
    sidebar: 'adminuiuxsidebarfilled',
    layout: 'adminuiuxlayoutmode'
  };

  // Every theme class AdminUIUX ships, plus ours. Used to clear before set.
  var THEMES = [
    'theme-blue', 'theme-indigo', 'theme-purple', 'theme-pink', 'theme-red',
    'theme-orange', 'theme-yellow', 'theme-green', 'theme-teal', 'theme-cyan',
    'theme-grey', 'theme-brown', 'theme-chocolate', 'theme-black',
    'theme-rsr', 'theme-rsr-graphite', 'theme-rsr-midnight',
    'theme-rsr-sand', 'theme-rsr-oxblood'
  ];

  var BACKGROUNDS = [
    'bg-default', 'bg-white', 'bg-r-gradient',
    'bg-gradient-1', 'bg-gradient-2', 'bg-gradient-3', 'bg-gradient-4',
    'bg-gradient-5', 'bg-gradient-6', 'bg-gradient-7', 'bg-gradient-8',
    'bg-gradient-9', 'bg-gradient-10'
  ];

  var SIDEBARS = [
    'adminuiux-sidebar-standard',
    'adminuiux-sidebar-iconic',
    'adminuiux-sidebar-boxed'
  ];

  var DEFAULT_THEME = 'theme-rsr';

  // ---- storage ------------------------------------------------------------
  function save(key, value) {
    try { localStorage.setItem(key, value); } catch (e) {}
    // Keep the cookie in sync — app.js and any other script still read it.
    try {
      var d = new Date();
      d.setFullYear(d.getFullYear() + 1);
      document.cookie = key + '=' + encodeURIComponent(value) +
                        ';expires=' + d.toUTCString() + ';path=/;SameSite=Lax';
    } catch (e) {}
  }

  function load(key) {
    try {
      var v = localStorage.getItem(key);
      if (v !== null && v !== '') return v;
    } catch (e) {}
    var m = document.cookie.match('(^|;)\\s*' + key + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : null;
  }

  // ---- helpers ------------------------------------------------------------
  function body() { return document.body; }

  function clearClasses(el, list) {
    list.forEach(function (c) {
      c.split(/\s+/).forEach(function (part) {
        if (part) el.classList.remove(part);
      });
    });
  }

  function addClasses(el, value) {
    String(value || '').split(/\s+/).forEach(function (part) {
      if (part) el.classList.add(part);
    });
  }

  function markActive(container, value) {
    var boxes = document.querySelectorAll(container + ' .select-box, ' +
                                          container + ' .gradient-box');
    Array.prototype.forEach.call(boxes, function (box) {
      box.classList.toggle('active', box.getAttribute('data-title') === value);
    });
  }

  function announce(name, value) {
    // Charts and any other listener can react without polling.
    document.dispatchEvent(new CustomEvent('rsr:personalize', {
      detail: { setting: name, value: value }
    }));
  }

  // ---- 1. colours ---------------------------------------------------------
  function applyTheme(value, persist) {
    var b = body();
    clearClasses(b, THEMES);            // the fix: clear before adding
    addClasses(b, value);
    b.setAttribute('data-theme', value);
    if (persist) save(KEYS.theme, value);
    markActive('.theme-select', value);
    announce('theme', value);
  }

  // ---- 2. backgrounds -----------------------------------------------------
  function applyBackground(value, persist) {
    var targets = document.querySelectorAll('.main-bg, body');
    Array.prototype.forEach.call(targets, function (el) {
      clearClasses(el, BACKGROUNDS);
      if (value && value !== 'bg-default') addClasses(el, value);
      // app.js sets an inline --adminuiux-main-bg with a broken relative
      // url("../../..."). Clear it so the class-based gradients can show.
      el.style.removeProperty('--adminuiux-main-bg');
    });
    if (persist) save(KEYS.background, value);
    markActive('.theme-background', value);
    announce('background', value);
  }

  // ---- 3. sidebar layout --------------------------------------------------
  function applySidebar(value, persist) {
    var b = body();
    clearClasses(b, SIDEBARS);
    addClasses(b, value);
    b.setAttribute('data-sidebarlayout', value);
    if (persist) save(KEYS.sidebar, value);
    markActive('.sidebar-layout', value);
    announce('sidebar', value);
    window.dispatchEvent(new Event('resize'));  // let charts re-measure
  }

  // ---- 4. light / dark ----------------------------------------------------
  function applyMode(value, persist) {
    var mode = (value === 'dark-mode') ? 'dark' : 'light';
    document.documentElement.setAttribute('data-bs-theme', mode);
    document.documentElement.classList.toggle('dark', mode === 'dark');
    body().classList.toggle('dark-mode', mode === 'dark');
    if (persist) save(KEYS.layout, value);
    announce('mode', mode);
  }

  // ---- binding ------------------------------------------------------------
  function bind(container, handler) {
    var root = document.querySelector(container);
    if (!root) return;

    root.addEventListener('click', function (ev) {
      var box = ev.target.closest('.select-box, .gradient-box');
      if (!box || !root.contains(box)) return;
      var value = box.getAttribute('data-title');
      if (!value) return;
      ev.preventDefault();
      handler(value, true);
    });
  }

  function restore() {
    applyTheme(load(KEYS.theme) || body().getAttribute('data-theme') || DEFAULT_THEME, false);

    var bg = load(KEYS.background);
    if (bg) applyBackground(bg, false); else markActive('.theme-background', 'bg-default');

    var sb = load(KEYS.sidebar);
    if (sb) applySidebar(sb, false);

    var mode = load(KEYS.layout);
    if (mode) applyMode(mode, false);
  }

  function init() {
    restore();

    bind('.theme-select', applyTheme);
    bind('.theme-background', applyBackground);
    bind('.sidebar-layout', applySidebar);

    document.querySelectorAll('.theme-select .select-box[data-title=""]')
      .forEach(function (box) {
        box.addEventListener('click', function () { applyTheme(DEFAULT_THEME, true); });
      });


    function syncModeFromBody() {
      var dark = document.body.classList.contains('dark-mode');
      document.documentElement.setAttribute('data-bs-theme', dark ? 'dark' : 'light');
      document.documentElement.classList.toggle('dark', dark);
      save(KEYS.layout, dark ? 'dark-mode' : 'light-mode');
      announce('mode', dark ? 'dark' : 'light');
    }

    syncModeFromBody();

    if (window.MutationObserver) {
      try {
        new window.MutationObserver(function () { syncModeFromBody(); })
          .observe(document.body, { attributes: true, attributeFilter: ['class'] });
      } catch (e) { /* fall back to the initial sync only */ }
    }

    // Keep multiple open tabs in step.
    window.addEventListener('storage', function (ev) {
      if (ev.key === KEYS.theme) applyTheme(ev.newValue, false);
      if (ev.key === KEYS.background) applyBackground(ev.newValue, false);
      if (ev.key === KEYS.sidebar) applySidebar(ev.newValue, false);
      if (ev.key === KEYS.layout) applyMode(ev.newValue, false);
    });
  }

  // Run after app.js has had its turn, so our class cleanup is the last word.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(init, 0); });
  } else {
    setTimeout(init, 0);
  }

  window.RSRPersonalize = {
    setTheme: function (v) { applyTheme(v, true); },
    setBackground: function (v) { applyBackground(v, true); },
    setSidebar: function (v) { applySidebar(v, true); },
    setMode: function (v) { applyMode(v, true); },
    current: function () {
      return {
        theme: load(KEYS.theme),
        background: load(KEYS.background),
        sidebar: load(KEYS.sidebar),
        mode: load(KEYS.layout)
      };
    }
  };
})();
