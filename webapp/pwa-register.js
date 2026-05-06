(() => {
  'use strict';
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/webapp/service-worker.js').catch(() => {});
  });
})();
