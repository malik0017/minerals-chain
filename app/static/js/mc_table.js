(function () {
  function init(tb) {
    var table = document.getElementById(tb.getAttribute('data-mc-for'));
    if (!table || !table.tBodies.length) return;
    var body = table.tBodies[0];
    var rows = Array.prototype.filter.call(body.rows, function (r) { return !r.classList.contains('mc-empty'); });
    var empty = body.querySelector('.mc-empty');
    var search = tb.querySelector('[data-mc-search]');
    var pills = tb.querySelectorAll('[data-mc-status]');
    var state = { status: '', q: '' };
    function has(r, s) { return !s || (' ' + (r.getAttribute('data-status') || '') + ' ').indexOf(' ' + s + ' ') > -1; }
    pills.forEach(function (p) {
      var s = p.getAttribute('data-mc-status');
      var n = rows.filter(function (r) { return has(r, s); }).length;
      var c = p.querySelector('[data-mc-count]');
      if (c) c.textContent = n;
      if (s && !n) p.classList.add('d-none');
    });
    function apply() {
      var q = state.q, shown = 0;
      rows.forEach(function (r) {
        var ok = has(r, state.status) && (!q || r.textContent.toLowerCase().indexOf(q) > -1);
        r.classList.toggle('d-none', !ok);
        if (ok) shown++;
      });
      if (empty) empty.classList.toggle('d-none', shown > 0);
      pills.forEach(function (p) { p.classList.toggle('active', p.getAttribute('data-mc-status') === state.status); });
    }
    pills.forEach(function (p) {
      p.addEventListener('click', function () { state.status = p.getAttribute('data-mc-status'); apply(); });
    });
    if (search) search.addEventListener('input', function () { state.q = search.value.trim().toLowerCase(); apply(); });
    document.querySelectorAll('[data-mc-target="' + table.id + '"]').forEach(function (k) {
      function go() { state.status = k.getAttribute('data-mc-set'); apply(); tb.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
      k.addEventListener('click', go);
      k.addEventListener('keydown', function (e) { if (e.key === 'Enter') go(); });
    });
    var sp = new URLSearchParams(location.search), initial = sp.get('show') || sp.get('status');
    if (initial) state.status = initial;
    apply();
  }
  document.addEventListener('DOMContentLoaded', function () { document.querySelectorAll('[data-mc-for]').forEach(init); });
})();
