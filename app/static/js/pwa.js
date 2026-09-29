(function () {
  if (!('serviceWorker' in navigator) || location.protocol === 'file:') return;
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
  });
  var deferred = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferred = e;
    document.querySelectorAll('[data-pwa-install]').forEach(function (el) { el.classList.remove('d-none'); });
  });
  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-pwa-install]');
    if (!el || !deferred) return;
    e.preventDefault();
    deferred.prompt();
    deferred.userChoice.finally(function () { deferred = null; el.classList.add('d-none'); });
  });
})();
