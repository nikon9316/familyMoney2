const CACHE_NAME = 'family-finance-v5-5-4';
const APP_SHELL = [
  '/webapp/index.html', '/webapp/style.css', '/webapp/pwa-register.js',
  '/webapp/app.js', '/webapp/offline-db.js',
  '/webapp/manifest.webmanifest', '/webapp/vendor/chart.umd.min.js',
  '/webapp/icons/icon-192.svg', '/webapp/icons/icon-512.svg'
];
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(req).catch(() => new Response(JSON.stringify({ok:false, offline:true, error:'Нет интернета. Данные API доступны после подключения.'}), {status:503, headers:{'Content-Type':'application/json'}})));
    return;
  }
  event.respondWith(caches.match(req).then((cached) => cached || fetch(req).then((res) => { const copy=res.clone(); caches.open(CACHE_NAME).then((cache)=>cache.put(req,copy)); return res; }).catch(() => caches.match('/webapp/index.html'))));
});
