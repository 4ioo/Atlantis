// One-time migration worker: remove the previous offline cache and unregister.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  const keys = await caches.keys();
  await Promise.all(keys.filter(key => key.startsWith('sama-sky-')).map(key => caches.delete(key)));
  await self.registration.unregister();
})()));