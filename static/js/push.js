/**
 * MIMIC Push Notifications Handler
 * Handles Web Push notification subscription and management
 */

// ==================== PUSH NOTIFICATION MANAGER ====================
const PushManager = {
    // State
    isSupported: false,
    isSubscribed: false,
    subscription: null,
    registration: null,
    vapidPublicKey: null,
    
    // ==================== INITIALIZATION ====================
    async init() {
        console.log('[Push] Initializing push notifications...');
        
        // Check if push is supported
        if (!('serviceWorker' in navigator)) {
            console.warn('[Push] Service Workers not supported');
            return false;
        }
        
        if (!('PushManager' in window)) {
            console.warn('[Push] Push notifications not supported');
            return false;
        }
        
        if (!('Notification' in window)) {
            console.warn('[Push] Notifications not supported');
            return false;
        }
        
        this.isSupported = true;
        
        try {
            // Get VAPID public key from server
            await this.fetchVapidKey();
            
            // Wait for service worker
            this.registration = await navigator.serviceWorker.ready;
            console.log('[Push] Service Worker ready');
            
            // Check current subscription
            await this.checkSubscription();
            
            // Update UI
            this.updateUI();
            
            return true;
        } catch (error) {
            console.error('[Push] Initialization failed:', error);
            return false;
        }
    },
    
    // ==================== VAPID KEY ====================
    async fetchVapidKey() {
        try {
            const response = await fetch('/api/push/vapid-key');
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.publicKey) {
                    this.vapidPublicKey = data.publicKey;
                    console.log('[Push] VAPID public key fetched');
                } else {
                    console.info('[Push] Push notifications not configured on server');
                    this.isSupported = false;
                    return;
                }
            } else if (response.status === 503) {
                // Push notifications not configured - this is OK, just disable push
                console.info('[Push] Push notifications not configured (503)');
                this.isSupported = false;
                return;
            } else {
                throw new Error('Failed to fetch VAPID key');
            }
        } catch (error) {
            console.warn('[Push] VAPID key fetch failed - push disabled:', error.message);
            this.isSupported = false;
        }
    },
    
    // ==================== SUBSCRIPTION MANAGEMENT ====================
    async checkSubscription() {
        try {
            this.subscription = await this.registration.pushManager.getSubscription();
            this.isSubscribed = !!this.subscription;
            console.log('[Push] Subscription status:', this.isSubscribed);
            return this.isSubscribed;
        } catch (error) {
            console.error('[Push] Check subscription failed:', error);
            return false;
        }
    },
    
    async subscribe() {
        if (!this.isSupported) {
            showToast('Push notifications are not supported on this browser', 'warning');
            return false;
        }
        
        // Request notification permission
        const permission = await this.requestPermission();
        if (permission !== 'granted') {
            showToast('Notification permission denied', 'error');
            return false;
        }
        
        try {
            // Convert VAPID key to Uint8Array
            const applicationServerKey = this.urlBase64ToUint8Array(this.vapidPublicKey);
            
            // Subscribe to push
            this.subscription = await this.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });
            
            console.log('[Push] Subscribed:', this.subscription);
            
            // Send subscription to server
            await this.sendSubscriptionToServer(this.subscription);
            
            this.isSubscribed = true;
            this.updateUI();
            
            showToast('Push notifications enabled! 🔔', 'success');
            return true;
        } catch (error) {
            console.error('[Push] Subscribe failed:', error);
            showToast('Failed to enable push notifications', 'error');
            return false;
        }
    },
    
    async unsubscribe() {
        if (!this.subscription) {
            return true;
        }
        
        try {
            // Unsubscribe from push
            await this.subscription.unsubscribe();
            
            // Remove from server
            await this.removeSubscriptionFromServer(this.subscription);
            
            this.subscription = null;
            this.isSubscribed = false;
            this.updateUI();
            
            showToast('Push notifications disabled', 'info');
            return true;
        } catch (error) {
            console.error('[Push] Unsubscribe failed:', error);
            showToast('Failed to disable push notifications', 'error');
            return false;
        }
    },
    
    // ==================== PERMISSION ====================
    async requestPermission() {
        if (Notification.permission === 'granted') {
            return 'granted';
        }
        
        if (Notification.permission === 'denied') {
            console.warn('[Push] Notifications blocked by user');
            return 'denied';
        }
        
        // Request permission
        const permission = await Notification.requestPermission();
        console.log('[Push] Permission:', permission);
        return permission;
    },
    
    getPermissionStatus() {
        return Notification.permission;
    },
    
    // ==================== SERVER COMMUNICATION ====================
    async sendSubscriptionToServer(subscription) {
        try {
            const response = await fetch('/api/push/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    subscription: subscription.toJSON(),
                    userAgent: navigator.userAgent,
                    language: navigator.language
                })
            });
            
            if (!response.ok) {
                throw new Error('Server rejected subscription');
            }
            
            const data = await response.json();
            console.log('[Push] Subscription saved to server:', data);
            return true;
        } catch (error) {
            console.error('[Push] Save subscription failed:', error);
            throw error;
        }
    },
    
    async removeSubscriptionFromServer(subscription) {
        try {
            const response = await fetch('/api/push/unsubscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    endpoint: subscription.endpoint
                })
            });
            
            if (!response.ok) {
                throw new Error('Server failed to remove subscription');
            }
            
            console.log('[Push] Subscription removed from server');
            return true;
        } catch (error) {
            console.error('[Push] Remove subscription failed:', error);
            throw error;
        }
    },
    
    // ==================== UI UPDATES ====================
    updateUI() {
        // Update push toggle button
        const toggleBtn = document.getElementById('pushToggleBtn');
        const statusText = document.getElementById('pushStatusText');
        const statusIcon = document.getElementById('pushStatusIcon');
        
        if (toggleBtn) {
            if (!this.isSupported) {
                toggleBtn.disabled = true;
                toggleBtn.innerHTML = '<i class="fas fa-bell-slash"></i> Not Supported';
                toggleBtn.classList.add('disabled');
            } else if (this.isSubscribed) {
                toggleBtn.innerHTML = '<i class="fas fa-bell"></i> Disable Notifications';
                toggleBtn.classList.remove('btn-primary');
                toggleBtn.classList.add('btn-secondary');
            } else {
                toggleBtn.innerHTML = '<i class="fas fa-bell"></i> Enable Notifications';
                toggleBtn.classList.add('btn-primary');
                toggleBtn.classList.remove('btn-secondary');
            }
        }
        
        if (statusText) {
            if (!this.isSupported) {
                statusText.textContent = 'Not Supported';
                statusText.className = 'status-disabled';
            } else if (this.isSubscribed) {
                statusText.textContent = 'Enabled';
                statusText.className = 'status-enabled';
            } else {
                statusText.textContent = 'Disabled';
                statusText.className = 'status-disabled';
            }
        }
        
        if (statusIcon) {
            if (this.isSubscribed) {
                statusIcon.className = 'fas fa-bell text-green';
            } else {
                statusIcon.className = 'fas fa-bell-slash text-muted';
            }
        }
        
        // Dispatch custom event for other components
        document.dispatchEvent(new CustomEvent('pushStatusChanged', {
            detail: {
                supported: this.isSupported,
                subscribed: this.isSubscribed
            }
        }));
    },
    
    // ==================== HELPERS ====================
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');
        
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    },
    
    // ==================== TEST NOTIFICATION ====================
    async sendTestNotification() {
        if (!this.isSubscribed) {
            showToast('Please enable push notifications first', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/push/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                showToast('Test notification sent!', 'success');
            } else {
                throw new Error('Failed to send test notification');
            }
        } catch (error) {
            console.error('[Push] Test notification failed:', error);
            showToast('Failed to send test notification', 'error');
        }
    }
};

// ==================== PWA INSTALL MANAGER ====================
const PWAInstallManager = {
    deferredPrompt: null,
    isInstalled: false,
    installBanner: null,
    
    init() {
        console.log('[PWA] Initializing PWA install manager...');
        
        // Check if already installed
        this.checkInstallState();
        
        // Listen for install prompt
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('[PWA] beforeinstallprompt fired');
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallPromotion();
        });
        
        // Listen for successful install
        window.addEventListener('appinstalled', () => {
            console.log('[PWA] App installed successfully');
            this.isInstalled = true;
            this.hideInstallPromotion();
            this.deferredPrompt = null;
            showToast('MIMIC installed successfully! 🎉', 'success');
            if (typeof celebrateSuccess === 'function') {
                celebrateSuccess();
            }
        });
        
        // Setup install button handler
        this.setupInstallButton();
    },
    
    checkInstallState() {
        // Check if running as PWA
        if (window.matchMedia('(display-mode: standalone)').matches) {
            this.isInstalled = true;
            console.log('[PWA] Running as installed PWA');
            return;
        }
        
        // iOS Safari check
        if (window.navigator.standalone === true) {
            this.isInstalled = true;
            console.log('[PWA] Running as installed PWA (iOS)');
        }
    },
    
    showInstallPromotion() {
        // Don't show if already installed or dismissed recently
        if (this.isInstalled) return;
        
        const dismissedAt = localStorage.getItem('pwaInstallDismissed');
        if (dismissedAt) {
            const daysSinceDismissed = (Date.now() - parseInt(dismissedAt)) / (1000 * 60 * 60 * 24);
            if (daysSinceDismissed < 7) {
                console.log('[PWA] Install prompt dismissed recently');
                return;
            }
        }
        
        // Show install banner after delay
        setTimeout(() => {
            this.createInstallBanner();
        }, 3000);
    },
    
    hideInstallPromotion() {
        if (this.installBanner) {
            this.installBanner.classList.add('hidden');
            setTimeout(() => {
                this.installBanner?.remove();
                this.installBanner = null;
            }, 300);
        }
    },
    
    createInstallBanner() {
        if (this.installBanner) return;
        
        this.installBanner = document.createElement('div');
        this.installBanner.id = 'pwaInstallBanner';
        this.installBanner.className = 'pwa-install-banner';
        this.installBanner.innerHTML = `
            <div class="pwa-install-content">
                <div class="pwa-install-icon">
                    <img src="/static/mimic-logo.svg" alt="MIMIC" width="48" height="48">
                </div>
                <div class="pwa-install-text">
                    <strong>Install MIMIC</strong>
                    <span>Add to home screen for quick access</span>
                </div>
                <div class="pwa-install-actions">
                    <button id="pwaInstallBtn" class="pwa-install-btn">
                        <i class="fas fa-download"></i> Install
                    </button>
                    <button id="pwaDismissBtn" class="pwa-dismiss-btn">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.installBanner);
        
        // Setup event handlers
        document.getElementById('pwaInstallBtn')?.addEventListener('click', () => {
            this.promptInstall();
        });
        
        document.getElementById('pwaDismissBtn')?.addEventListener('click', () => {
            this.dismissInstall();
        });
        
        // Add show animation
        requestAnimationFrame(() => {
            this.installBanner.classList.add('show');
        });
    },
    
    async promptInstall() {
        if (!this.deferredPrompt) {
            // Show iOS instructions or manual install guide
            this.showManualInstallInstructions();
            return;
        }
        
        // Show native install prompt
        this.deferredPrompt.prompt();
        
        const { outcome } = await this.deferredPrompt.userChoice;
        console.log('[PWA] Install outcome:', outcome);
        
        if (outcome === 'accepted') {
            this.hideInstallPromotion();
        }
        
        this.deferredPrompt = null;
    },
    
    dismissInstall() {
        localStorage.setItem('pwaInstallDismissed', Date.now().toString());
        this.hideInstallPromotion();
    },
    
    showManualInstallInstructions() {
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        const isAndroid = /Android/.test(navigator.userAgent);
        
        let instructions = '';
        
        if (isIOS) {
            instructions = `
                <div class="install-instructions">
                    <h4>Install on iOS</h4>
                    <ol>
                        <li>Tap the <strong>Share</strong> button <i class="fas fa-share-square"></i></li>
                        <li>Scroll down and tap <strong>"Add to Home Screen"</strong></li>
                        <li>Tap <strong>"Add"</strong> to confirm</li>
                    </ol>
                </div>
            `;
        } else if (isAndroid) {
            instructions = `
                <div class="install-instructions">
                    <h4>Install on Android</h4>
                    <ol>
                        <li>Tap the <strong>Menu</strong> button <i class="fas fa-ellipsis-v"></i></li>
                        <li>Tap <strong>"Add to Home screen"</strong></li>
                        <li>Tap <strong>"Add"</strong> to confirm</li>
                    </ol>
                </div>
            `;
        } else {
            instructions = `
                <div class="install-instructions">
                    <h4>Install MIMIC</h4>
                    <p>Look for the install icon in your browser's address bar or menu.</p>
                </div>
            `;
        }
        
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'install-modal-overlay';
        modal.innerHTML = `
            <div class="install-modal">
                <button class="install-modal-close">&times;</button>
                <div class="install-modal-header">
                    <img src="/static/mimic-logo.svg" alt="MIMIC" width="64" height="64">
                    <h3>Install MIMIC App</h3>
                </div>
                ${instructions}
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close handlers
        modal.querySelector('.install-modal-close')?.addEventListener('click', () => {
            modal.remove();
        });
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    },
    
    setupInstallButton() {
        // Handle any install buttons in the page
        document.addEventListener('click', (e) => {
            if (e.target.closest('[data-install-pwa]')) {
                e.preventDefault();
                this.promptInstall();
            }
        });
    }
};

// ==================== SERVICE WORKER MANAGER ====================
const ServiceWorkerManager = {
    registration: null,
    
    async init() {
        if (!('serviceWorker' in navigator)) {
            console.warn('[SW] Service Workers not supported');
            return false;
        }
        
        try {
            this.registration = await navigator.serviceWorker.register('/service-worker.js', {
                scope: '/'
            });
            
            console.log('[SW] Service Worker registered:', this.registration);
            
            // Handle updates
            this.registration.addEventListener('updatefound', () => {
                const newWorker = this.registration.installing;
                console.log('[SW] New service worker installing...');
                
                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        this.notifyUpdate();
                    }
                });
            });
            
            // Check for updates periodically
            setInterval(() => {
                this.registration.update();
            }, 60 * 60 * 1000); // Check every hour
            
            return true;
        } catch (error) {
            console.error('[SW] Registration failed:', error);
            return false;
        }
    },
    
    notifyUpdate() {
        // Show update notification
        const updateBanner = document.createElement('div');
        updateBanner.className = 'sw-update-banner';
        updateBanner.innerHTML = `
            <div class="sw-update-content">
                <i class="fas fa-sync-alt"></i>
                <span>A new version is available</span>
                <button id="swUpdateBtn" class="sw-update-btn">Refresh</button>
            </div>
        `;
        
        document.body.appendChild(updateBanner);
        
        document.getElementById('swUpdateBtn')?.addEventListener('click', () => {
            this.skipWaiting();
        });
    },
    
    skipWaiting() {
        if (this.registration?.waiting) {
            this.registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
        window.location.reload();
    },
    
    async clearCache() {
        if (this.registration?.active) {
            this.registration.active.postMessage({ type: 'CLEAR_CACHE' });
            showToast('Cache cleared', 'success');
        }
    },
    
    getVersion() {
        return new Promise((resolve) => {
            if (!this.registration?.active) {
                resolve('unknown');
                return;
            }
            
            const channel = new MessageChannel();
            channel.port1.onmessage = (e) => {
                resolve(e.data.version);
            };
            
            this.registration.active.postMessage(
                { type: 'GET_VERSION' },
                [channel.port2]
            );
        });
    }
};

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize Service Worker
    await ServiceWorkerManager.init();
    
    // Initialize PWA Install Manager
    PWAInstallManager.init();
    
    // Initialize Push Notifications
    await PushManager.init();
    
    // Handle push toggle button
    document.getElementById('pushToggleBtn')?.addEventListener('click', async () => {
        if (PushManager.isSubscribed) {
            await PushManager.unsubscribe();
        } else {
            await PushManager.subscribe();
        }
    });
    
    // Handle test notification button
    document.getElementById('pushTestBtn')?.addEventListener('click', async () => {
        await PushManager.sendTestNotification();
    });
});

// ==================== GLOBAL EXPORTS ====================
window.PushManager = PushManager;
window.PWAInstallManager = PWAInstallManager;
window.ServiceWorkerManager = ServiceWorkerManager;
