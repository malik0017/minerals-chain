(function () {
  function portalModals(root) {
    (root || document).querySelectorAll('.modal').forEach(function (m) {
      if (m.parentElement !== document.body) document.body.appendChild(m);
    });
  }

  document.addEventListener('show.bs.modal', function (e) {
    if (e.target && e.target.parentElement !== document.body) document.body.appendChild(e.target);
  }, true);

  function liveFilter(form) {
    var targetId = form.getAttribute('data-mc-ajax');
    var region = document.getElementById(targetId);
    if (!region) return;
    var timer = null, ctrl = null;

    function url(extra) {
      var params = new URLSearchParams(new FormData(form));
      Array.from(params.keys()).forEach(function (k) { if (!params.get(k)) params.delete(k); });
      if (extra) Object.keys(extra).forEach(function (k) { params.set(k, extra[k]); });
      var q = params.toString();
      return (form.getAttribute('action') || location.pathname) + (q ? '?' + q : '');
    }

    function load(href, push) {
      if (ctrl) ctrl.abort();
      ctrl = window.AbortController ? new AbortController() : null;
      region.classList.add('mc-loading');
      fetch(href, { headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin', signal: ctrl ? ctrl.signal : undefined })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(function (html) {
          var doc = new DOMParser().parseFromString(html, 'text/html');
          var fresh = doc.getElementById(targetId);
          if (!fresh) { location.href = href; return; }
          region.innerHTML = fresh.innerHTML;
          portalModals(region);
          if (push) history.replaceState(null, '', href);
          region.dispatchEvent(new CustomEvent('mc:refreshed', { bubbles: true }));
        })
        .catch(function (err) { if (!err || err.name !== 'AbortError') location.href = href; })
        .finally(function () { region.classList.remove('mc-loading'); });
    }

    form.addEventListener('submit', function (e) { e.preventDefault(); load(url(), true); });
    form.querySelectorAll('select, input[type=date], input[type=checkbox], input[type=radio]').forEach(function (el) {
      el.addEventListener('change', function () { load(url(), true); });
    });
    form.querySelectorAll('input[type=text], input[type=search], input:not([type])').forEach(function (el) {
      el.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(function () { load(url(), true); }, 350);
      });
    });
    var reset = form.querySelector('[data-mc-reset]');
    if (reset) reset.addEventListener('click', function (e) {
      e.preventDefault();
      form.querySelectorAll('input, select').forEach(function (el) {
        if (el.type === 'hidden') return;
        if (el.tagName === 'SELECT') el.selectedIndex = 0; else el.value = '';
      });
      load(url(), true);
    });
    region.addEventListener('click', function (e) {
      var a = e.target.closest('.pagination a.page-link');
      if (!a || !region.contains(a)) return;
      e.preventDefault();
      load(a.href, true);
      region.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    portalModals(document);
    document.querySelectorAll('form[data-mc-ajax]').forEach(liveFilter);
  });
})();
