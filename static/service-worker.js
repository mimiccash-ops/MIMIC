/**
 * MIMIC PWA Service Worker
 * Handles caching, offline functionality, and push notifications
 */

const CACHE_NAME = 'mimic-cache-v3';
const DYNAMIC_CACHE = 'mimic-dynamic-v3';
const OFFLINE_URL = '/offline.html';

// Static assets to cache on install
const STATIC_ASSETS = [
    '/',
    '/login',
    '/register',
    // CSS/JS files are versioned, so we don't cache them statically here
    // They will be cached dynamically when requested with their version parameter
    '/static/mimic-logo.svg',
    '/static/manifest.json',
    '/static/icons/icon-144x144.png',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
    '/static/icons/badge-72x72.png',
    // External resources (optional - can fail gracefully)
    'https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// URLs that should always go to network (no cache)
const NETWORK_ONLY = [
    '/api/',
    '/webhook',
    '/socket.io/',
    '/push/subscribe',
    '/push/unsubscribe',
    '/login',
    '/logout',
    '/register'
];

// URLs that should use cache-first strategy
// NOTE: Versioned files (?v=...) should always go to network first to get latest version
const CACHE_FIRST = [
    '/fonts/',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.svg',
    '.woff',
    '.woff2',
    '.ttf'
];

// Versioned static files - always check network first
const VERSIONED_FILES = [
    '/static/css/',
    '/static/js/'
];

// ==================== INSTALL EVENT ====================
self.addEventListener('install', (event) => {
    console.log('[SW] Installing Service Worker...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                // Cache static assets one by one to handle failures gracefully
                return Promise.allSettled(
                    STATIC_ASSETS.map(url => 
                        cache.add(url).catch(err => {
                            console.warn(`[SW] Failed to cache: ${url}`, err);
                        })
                    )
                );
            })
            .then(() => {
                console.log('[SW] Static assets cached');
                return self.skipWaiting();
            })
            .catch((error) => {
                console.error('[SW] Cache installation failed:', error);
            })
    );
});

// ==================== ACTIVATE EVENT ====================
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating Service Worker...');
    
    event.waitUntil(
        Promise.all([
            // Clean up old caches
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter(name => name !== CACHE_NAME && name !== DYNAMIC_CACHE)
                        .map(name => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            }),
            // Take control of all clients immediately
            self.clients.claim()
        ])
    );
});

// ==================== FETCH EVENT ====================
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }
    
    // Skip cross-origin requests except for known CDNs
    if (url.origin !== self.location.origin && 
        !url.origin.includes('fonts.googleapis.com') &&
        !url.origin.includes('fonts.gstatic.com') &&
        !url.origin.includes('cdnjs.cloudflare.com') &&
        !url.origin.includes('cdn.jsdelivr.net')) {
        return;
    }
    
    // Network-only for API and authentication
    if (NETWORK_ONLY.some(pattern => url.pathname.includes(pattern))) {
        event.respondWith(
            fetch(event.request).catch(() => {
                // Return a simple error response for API failures
                if (url.pathname.includes('/api/')) {
                    return new Response(
                        JSON.stringify({ error: 'Network unavailable' }),
                        { status: 503, headers: { 'Content-Type': 'application/json' } }
                    );
                }
                return caches.match(OFFLINE_URL);
            })
        );
        return;
    }
    
    // Network-first for versioned CSS/JS files (?v=...) - always get latest version
    const isVersioned = url.searchParams.has('v') || url.search.includes('?v=');
    const isVersionedStatic = isVersioned && VERSIONED_FILES.some(pattern => url.pathname.includes(pattern));
    
    if (isVersionedStatic) {
        event.respondWith(
            fetch(event.request)
                .then((networkResponse) => {
                    // Cache versioned files with their version in the cache key
                    if (networkResponse.ok) {
                        const responseClone = networkResponse.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => cache.put(event.request, responseClone));
                    }
                    return networkResponse;
                })
                .catch(() => {
                    // Fallback to cache if network fails
                    return caches.match(event.request);
                })
        );
        return;
    }
    
    // Cache-first for static assets (non-versioned)
    if (CACHE_FIRST.some(pattern => url.pathname.includes(pattern) || url.pathname.endsWith(pattern))) {
        event.respondWith(
            caches.match(event.request)
                .then((cachedResponse) => {
                    if (cachedResponse) {
                        // Return cached version and update in background
                        event.waitUntil(
                            fetch(event.request)
                                .then((networkResponse) => {
                                    if (networkResponse.ok) {
                                        caches.open(CACHE_NAME)
                                            .then(cache => cache.put(event.request, networkResponse));
                                    }
                                })
                                .catch(() => {})
                        );
                        return cachedResponse;
                    }
                    
                    // Fetch from network and cache
                    return fetch(event.request)
                        .then((networkResponse) => {
                            if (networkResponse.ok) {
                                const responseClone = networkResponse.clone();
                                caches.open(CACHE_NAME)
                                    .then(cache => cache.put(event.request, responseClone));
                            }
                            return networkResponse;
                        })
                        .catch(() => {
                            // Return offline fallback for HTML pages
                            if (event.request.headers.get('accept')?.includes('text/html')) {
                                return caches.match(OFFLINE_URL);
                            }
                        });
                })
        );
        return;
    }
    
    // Network-first for HTML pages (dashboard, etc.)
    event.respondWith(
        fetch(event.request)
            .then((networkResponse) => {
                // Cache successful HTML responses
                if (networkResponse.ok && event.request.headers.get('accept')?.includes('text/html')) {
                    const responseClone = networkResponse.clone();
                    caches.open(DYNAMIC_CACHE)
                        .then(cache => cache.put(event.request, responseClone));
                }
                return networkResponse;
            })
            .catch(() => {
                // Try cache, then offline page
                return caches.match(event.request)
                    .then(cachedResponse => {
                        if (cachedResponse) {
                            return cachedResponse;
                        }
                        // Return offline page for HTML requests
                        if (event.request.headers.get('accept')?.includes('text/html')) {
                            return caches.match(OFFLINE_URL);
                        }
                    });
            })
    );
});

// ==================== PUSH NOTIFICATION EVENT ====================
self.addEventListener('push', (event) => {
    console.log('[SW] Push notification received');
    
    let data = {
        title: 'MIMIC Trading',
        body: 'New notification',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/badge-72x72.png',
        tag: 'mimic-notification',
        data: { url: '/dashboard' }
    };
    
    if (event.data) {
        try {
            const payload = event.data.json();
            data = { ...data, ...payload };
        } catch (e) {
            data.body = event.data.text();
        }
    }
    
    const options = {
        body: data.body,
        icon: data.icon || '/static/icons/icon-192x192.png',
        badge: data.badge || '/static/icons/badge-72x72.png',
        tag: data.tag || 'mimic-notification',
        data: data.data || { url: '/dashboard' },
        vibrate: [100, 50, 100],
        requireInteraction: data.requireInteraction || false,
        actions: data.actions || [
            { action: 'open', title: 'Open', icon: '/static/icons/action-open.png' },
            { action: 'dismiss', title: 'Dismiss', icon: '/static/icons/action-dismiss.png' }
        ],
        timestamp: Date.now(),
        silent: false
    };
    
    // Add trade-specific styling
    if (data.type === 'trade_opened' || data.type === 'trade_closed') {
        options.actions = [
            { action: 'view_trade', title: 'View Trade' },
            { action: 'dismiss', title: 'Dismiss' }
        ];
    }
    
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// ==================== NOTIFICATION CLICK EVENT ====================
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notification clicked:', event.action);
    
    event.notification.close();
    
    const action = event.action;
    const data = event.notification.data || {};
    let targetUrl = data.url || '/dashboard';
    
    // Handle specific actions
    if (action === 'view_trade' && data.tradeId) {
        targetUrl = `/dashboard?trade=${data.tradeId}`;
    } else if (action === 'dismiss') {
        return; // Just close the notification
    }
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Check if app is already open
                for (const client of clientList) {
                    if (client.url.includes(self.location.origin) && 'focus' in client) {
                        client.navigate(targetUrl);
                        return client.focus();
                    }
                }
                // Open new window
                if (clients.openWindow) {
                    return clients.openWindow(targetUrl);
                }
            })
    );
});

// ==================== NOTIFICATION CLOSE EVENT ====================
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] Notification closed');
    // Could track analytics here
});

// ==================== MESSAGE EVENT ====================
self.addEventListener('message', (event) => {
    console.log('[SW] Message received:', event.data);
    
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then(cacheNames => {
                return Promise.all(
                    cacheNames.map(name => caches.delete(name))
                );
            })
        );
    }
    
    if (event.data.type === 'GET_VERSION') {
        event.ports[0].postMessage({ version: CACHE_NAME });
    }
});

// ==================== BACKGROUND SYNC ====================
self.addEventListener('sync', (event) => {
    console.log('[SW] Background sync:', event.tag);
    
    if (event.tag === 'sync-trades') {
        event.waitUntil(syncTrades());
    }
});

async function syncTrades() {
    // Sync any pending trade data when back online
    try {
        const cache = await caches.open(DYNAMIC_CACHE);
        const response = await fetch('/api/sync', { method: 'POST' });
        console.log('[SW] Trades synced successfully');
    } catch (error) {
        console.error('[SW] Sync failed:', error);
    }
}

// ==================== PERIODIC SYNC ====================
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'update-prices') {
        event.waitUntil(updatePriceData());
    }
});

async function updatePriceData() {
    try {
        const response = await fetch('/api/prices');
        const data = await response.json();
        
        // Notify clients about updated prices
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({
                type: 'PRICE_UPDATE',
                data: data
            });
        });
    } catch (error) {
        console.error('[SW] Price update failed:', error);
    }
}

console.log('[SW] Service Worker loaded');
