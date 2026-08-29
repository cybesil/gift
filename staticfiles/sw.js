const CACHE_NAME = 'gift-empire-v2'; // bump this so the old SW/cache gets replaced
const STATIC_ASSETS = [
  '/',
];

self.addEventListener('install', event => {
  self.skipWaiting(); // activate the new SW immediately instead of waiting
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const requestUrl = new URL(event.request.url);

  // Let cross-origin requests (Cloudinary images, etc.) go straight to network,
  // untouched by the service worker
  if (requestUrl.origin !== self.location.origin) {
    return;
  }

  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match(event.request)
    )
  );
});