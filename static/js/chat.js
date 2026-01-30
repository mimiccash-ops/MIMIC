/**
 * MIMIC Live Chat - WebSocket Real-Time Chat
 * Socket.IO based chat for subscribers
 * 🗨️ SOCIAL TRADING FEED 🗨️
 */

class MimicChat {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.isOpen = false;
        this.room = 'general';
        this.userId = null;
        this.username = null;
        this.isAdmin = false;
        this.canChat = false;
        this.isAuthenticated = false; // Track if user is logged in
        this.messages = [];
        this.unreadCount = 0;
        this.contextMenu = null;
        this.pendingJoin = false;
        
        this.elements = {};
        
        this.init();
    }
    
    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }
    
    setup() {
        // Check if Socket.IO is available
        if (typeof io === 'undefined') {
            console.error('Socket.IO not loaded');
            return;
        }
        
        this.createChatWidget();
        this.bindEvents();
        this.checkChatStatus();
    }
    
    createChatWidget() {
        // Create chat widget HTML
        const widgetHTML = `
            <div class="chat-widget" id="chatWidget">
                <button class="chat-toggle-btn" id="chatToggleBtn" aria-label="Відкрити чат">
                    <i class="fas fa-comments"></i>
                    <span class="chat-unread-badge" id="chatUnreadBadge" style="display: none;">0</span>
                </button>
                
                <div class="chat-window" id="chatWindow">
                    <div class="chat-header">
                        <div class="chat-header-info">
                            <div class="chat-header-icon" id="chatHeaderIcon">
                                <i class="fas fa-comments"></i>
                            </div>
                            <div>
                                <div class="chat-header-title" id="chatHeaderTitle">Живий чат</div>
                                <div class="chat-header-subtitle">
                                    <span class="online-dot" id="chatOnlineDot"></span>
                                    <span id="chatOnlineCount">Підключення...</span>
                                </div>
                            </div>
                        </div>
                        <div class="chat-header-actions">
                            <button class="chat-close-btn" id="chatCloseBtn" aria-label="Закрити чат">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                    
                    <div class="chat-messages" id="chatMessages">
                        <div class="chat-status" id="chatStatus">
                            <div class="chat-status-icon">💬</div>
                            <div class="chat-status-text">Завантаження чату...</div>
                        </div>
                    </div>
                    
                    <div class="chat-input-container" id="chatInputContainer">
                        <form class="chat-input-form" id="chatInputForm">
                            <input type="text" 
                                   class="chat-input" 
                                   id="chatInput" 
                                   placeholder="Напиши повідомлення..." 
                                   maxlength="500"
                                   autocomplete="off"
                                   disabled>
                            <button type="submit" class="chat-send-btn" id="chatSendBtn" disabled>
                                <i class="fas fa-paper-plane"></i>
                            </button>
                        </form>
                    </div>
                </div>
            </div>
            
            <div class="chat-context-menu" id="chatContextMenu">
                <div class="chat-context-item" data-action="delete">
                    <i class="fas fa-trash"></i>
                    <span>Видалити повідомлення</span>
                </div>
                <div class="chat-context-divider"></div>
                <div class="chat-context-item" data-action="mute">
                    <i class="fas fa-volume-mute"></i>
                    <span>Заглушити (1 год)</span>
                </div>
                <div class="chat-context-item danger" data-action="ban">
                    <i class="fas fa-ban"></i>
                    <span>Заблокувати</span>
                </div>
            </div>
        `;
        
        // Append to body
        document.body.insertAdjacentHTML('beforeend', widgetHTML);
        
        // Cache elements
        this.elements = {
            widget: document.getElementById('chatWidget'),
            toggleBtn: document.getElementById('chatToggleBtn'),
            unreadBadge: document.getElementById('chatUnreadBadge'),
            window: document.getElementById('chatWindow'),
            closeBtn: document.getElementById('chatCloseBtn'),
            headerIcon: document.getElementById('chatHeaderIcon'),
            headerTitle: document.getElementById('chatHeaderTitle'),
            onlineDot: document.getElementById('chatOnlineDot'),
            messages: document.getElementById('chatMessages'),
            status: document.getElementById('chatStatus'),
            inputContainer: document.getElementById('chatInputContainer'),
            inputForm: document.getElementById('chatInputForm'),
            input: document.getElementById('chatInput'),
            sendBtn: document.getElementById('chatSendBtn'),
            onlineCount: document.getElementById('chatOnlineCount'),
            contextMenu: document.getElementById('chatContextMenu')
        };
        
    }
    
    bindEvents() {
        // Toggle chat window
        this.elements.toggleBtn.addEventListener('click', () => this.toggleChat());
        this.elements.closeBtn.addEventListener('click', () => this.closeChat());
        
        // Send message
        this.elements.inputForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        
        // Close context menu on click outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.chat-context-menu')) {
                this.hideContextMenu();
            }
        });
        
        // Context menu actions
        this.elements.contextMenu.querySelectorAll('.chat-context-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const action = e.currentTarget.dataset.action;
                this.handleContextAction(action);
            });
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.closeChat();
            }
        });
    }
    
    async checkChatStatus() {
        try {
            const response = await fetch('/api/chat/status');
            const data = await response.json();
            
            if (data.success) {
                this.canChat = data.can_chat;
                this.isAdmin = data.is_admin;
                this.isAuthenticated = data.is_authenticated !== false; // Default true for backward compat
                
                if (data.can_chat) {
                    this.initSocket();
                } else if (data.is_banned) {
                    this.showBannedStatus(data.ban_type, data.ban_reason, data.ban_expires_at);
                } else if (!this.isAuthenticated) {
                    this.showLoginRequired();
                } else if (!data.has_subscription) {
                    this.showSubscriptionRequired();
                }
            }
        } catch (err) {
            console.error('Chat status check failed:', err);
            this.isAuthenticated = false;
            this.showLoginRequired();
        }
    }
    
    initSocket() {
        // Use existing Socket.IO connection or create new one
        if (typeof socket !== 'undefined' && socket.connected) {
            this.socket = socket;
        } else {
            // Create new socket with reconnection throttling
            this.socket = io({
                reconnection: true,
                reconnectionAttempts: 10,
                reconnectionDelay: 1000,
                reconnectionDelayMax: 30000,
                timeout: 20000,
                // Start with polling for maximum proxy compatibility, then upgrade
                transports: ['polling', 'websocket']
            });
        }
        
        this.isConnected = true;
        
        // Socket event handlers
        this.socket.on('connect', () => {
            this.isConnected = true;
            if (this.isOpen || this.pendingJoin) {
                this.socket.emit('join_chat', { room: this.room });
                this.pendingJoin = false;
            }
        });
        this.socket.on('connect_error', (err) => {
            console.error('Chat socket connection error:', err);
            this.isConnected = false;
            this.showErrorStatus('Не вдалося підключитися до чату. Оновіть сторінку.');
            this.disableInput();
        });
        this.socket.on('chat_joined', (data) => this.onChatJoined(data));
        this.socket.on('new_message', (msg) => this.onNewMessage(msg));
        this.socket.on('user_joined', (data) => this.onUserJoined(data));
        this.socket.on('user_left', (data) => this.onUserLeft(data));
        this.socket.on('message_deleted', (data) => this.onMessageDeleted(data));
        this.socket.on('whale_alert', (data) => this.onWhaleAlert(data));
        this.socket.on('chat_error', (data) => this.onChatError(data));
        this.socket.on('chat_muted', (data) => this.onMuted(data));
        this.socket.on('chat_banned', (data) => this.onBanned(data));
        this.socket.on('chat_unbanned', (data) => this.onUnbanned(data));
        this.socket.on('force_leave_chat', () => this.onForceLeave());
        
        // Enable input
        this.enableInput();
        this.elements.onlineCount.textContent = 'Загальна кімната';
        
        if (this.isOpen || this.pendingJoin) {
            this.socket.emit('join_chat', { room: this.room });
            this.pendingJoin = false;
        }
    }
    
    toggleChat() {
        if (this.isOpen) {
            this.closeChat();
        } else {
            this.openChat();
        }
    }
    
    openChat() {
        this.isOpen = true;
        this.elements.window.classList.add('open');
        this.elements.toggleBtn.classList.add('active');
        
        // Reset unread count
        this.unreadCount = 0;
        this.updateUnreadBadge();
        
        // Join chat room if connected, otherwise mark as pending
        if (this.socket && this.canChat) {
            this.socket.emit('join_chat', { room: this.room });
            this.pendingJoin = false;
        } else {
            this.pendingJoin = true;
        }
        
        // Focus input
        setTimeout(() => this.elements.input.focus(), 100);
    }
    
    closeChat() {
        this.isOpen = false;
        this.elements.window.classList.remove('open');
        this.elements.toggleBtn.classList.remove('active');
        
        // Leave chat room
        if (this.socket) {
            this.socket.emit('leave_chat', { room: this.room });
        }
    }
    
    onChatJoined(data) {
        this.userId = data.user?.id;
        this.username = data.user?.username;
        this.isAdmin = data.user?.is_admin;
        
        // Clear messages and add history
        this.messages = data.messages || [];
        this.renderMessages();
        
        // Scroll to bottom
        this.scrollToBottom();
    }
    
    onNewMessage(msg) {
        this.messages.push(msg);
        this.appendMessage(msg);
        
        // Increment unread if chat is closed
        if (!this.isOpen) {
            this.unreadCount++;
            this.updateUnreadBadge();
        }
        
        this.scrollToBottom();
    }
    
    onUserJoined(data) {
        // Could show a subtle notification
        console.log(`${data.username} joined the chat`);
    }
    
    onUserLeft(data) {
        console.log(`${data.username} left the chat`);
    }
    
    onMessageDeleted(data) {
        const msgEl = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (msgEl) {
            msgEl.style.opacity = '0.5';
            msgEl.querySelector('.chat-bubble').innerHTML = '<i>Повідомлення видалено</i>';
        }
        
        // Remove from local array
        this.messages = this.messages.filter(m => m.id !== data.message_id);
    }
    
    onWhaleAlert(data) {
        // Show whale notification
        this.showWhaleNotification(data);
    }
    
    onChatError(data) {
        this.showErrorStatus(data.message);
        if (data.ban_type) {
            this.disableInput();
        }
    }
    
    onMuted(data) {
        this.showBannedStatus('mute', data.message, data.expires_at);
        this.disableInput();
    }
    
    onBanned(data) {
        this.showBannedStatus('ban', data.message, null);
        this.disableInput();
    }
    
    onUnbanned(data) {
        this.canChat = true;
        this.enableInput();
        this.showToast(data.message, 'success');
    }
    
    onForceLeave() {
        this.closeChat();
        this.canChat = false;
        this.disableInput();
    }
    
    sendMessage() {
        const text = this.elements.input.value.trim();
        if (!text || !this.canChat) return;
        
        this.socket.emit('send_message', {
            room: this.room,
            message: text
        });
        
        this.elements.input.value = '';
    }
    
    renderMessages() {
        // Clear current messages
        this.elements.messages.innerHTML = '';
        this.elements.status.style.display = 'none';
        
        if (this.messages.length === 0) {
            this.elements.messages.innerHTML = `
                <div class="chat-status">
                    <div class="chat-status-icon">💬</div>
                    <div class="chat-status-text">Ще немає повідомлень. Розпочни розмову!</div>
                </div>
            `;
            return;
        }
        
        this.messages.forEach(msg => this.appendMessage(msg));
    }
    
    appendMessage(msg) {
        const isOwn = msg.user_id === this.userId;
        const isSystem = msg.message_type === 'system' || msg.message_type === 'whale_alert';
        const isAdminMsg = msg.message_type === 'admin';
        
        const msgHTML = `
            <div class="chat-message ${isOwn ? 'own' : ''} ${msg.message_type}" 
                 data-message-id="${msg.id}"
                 data-user-id="${msg.user_id}"
                 data-username="${msg.username}"
                 ${this.isAdmin ? 'oncontextmenu="mimicChat.showContextMenu(event, ' + msg.id + ', ' + msg.user_id + ')"' : ''}>
                ${!isSystem ? `
                    <div class="chat-avatar">
                        ${msg.avatar_type === 'image' && msg.avatar 
                            ? `<img src="/static/avatars/${msg.avatar}" alt="">`
                            : `<span>${msg.avatar || '🧑‍💻'}</span>`
                        }
                    </div>
                ` : ''}
                <div class="chat-message-content">
                    ${!isSystem ? `
                        <div class="chat-message-header">
                            <span class="chat-username ${isAdminMsg ? 'admin' : ''}">${msg.username}</span>
                            ${isAdminMsg ? '<span class="admin-badge">Адмін</span>' : ''}
                            <span class="chat-timestamp">${msg.timestamp}</span>
                        </div>
                    ` : ''}
                    <div class="chat-bubble">${this.escapeHtml(msg.message)}</div>
                </div>
            </div>
        `;
        
        this.elements.messages.insertAdjacentHTML('beforeend', msgHTML);
    }
    
    scrollToBottom() {
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }
    
    updateUnreadBadge() {
        if (this.unreadCount > 0) {
            this.elements.unreadBadge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
            this.elements.unreadBadge.style.display = 'flex';
        } else {
            this.elements.unreadBadge.style.display = 'none';
        }
    }
    
    enableInput() {
        this.elements.input.disabled = false;
        this.elements.sendBtn.disabled = false;
        this.elements.input.placeholder = 'Напиши повідомлення...';
    }
    
    disableInput() {
        this.elements.input.disabled = true;
        this.elements.sendBtn.disabled = true;
        this.elements.input.placeholder = 'Чат вимкнено';
    }

    showLoginRequired() {
        this.elements.status.innerHTML = `
            <div class="chat-status-icon">🔒</div>
            <div class="chat-status-text">
                <strong>Потрібен вхід</strong><br>
                Увійдіть, щоб користуватись чатом.
            </div>
            <a href="/login" class="chat-status-btn">Увійти</a>
        `;
        this.elements.status.style.display = 'flex';
        this.elements.messages.innerHTML = '';
        this.elements.messages.appendChild(this.elements.status);
        this.disableInput();
    }
    
    showSubscriptionRequired() {
        // This should not happen as chat is now free for all users
        // But keep as fallback with a generic connection error message
        this.elements.status.innerHTML = `
            <div class="chat-status-icon">⚠️</div>
            <div class="chat-status-text">
                <strong>Помилка підключення</strong><br>
                Не вдалося підключитися до чату. Оновіть сторінку.
            </div>
            <button onclick="location.reload()" class="chat-status-btn">Оновити</button>
        `;
        this.elements.status.style.display = 'flex';
        this.elements.messages.innerHTML = '';
        this.elements.messages.appendChild(this.elements.status);
        this.disableInput();
    }
    
    showBannedStatus(banType, reason, expiresAt) {
        const expireText = expiresAt 
            ? `<br><small>Закінчується: ${new Date(expiresAt).toLocaleString('uk-UA')}</small>`
            : '';
        
        this.elements.status.innerHTML = `
            <div class="chat-status-icon">🚫</div>
            <div class="chat-status-text">
                <strong>Тебе ${banType === 'ban' ? 'заблоковано' : 'заглушено'}</strong><br>
                ${reason || 'Порушення правил чату'}
                ${expireText}
            </div>
        `;
        this.elements.status.style.display = 'flex';
        this.elements.messages.innerHTML = '';
        this.elements.messages.appendChild(this.elements.status);
        this.disableInput();
    }
    
    showErrorStatus(message) {
        this.elements.status.innerHTML = `
            <div class="chat-status-icon">⚠️</div>
            <div class="chat-status-text">${message}</div>
        `;
        this.elements.status.style.display = 'flex';
    }
    
    // Admin functions
    showContextMenu(e, messageId, userId) {
        e.preventDefault();
        if (!this.isAdmin) return;
        
        this.selectedMessageId = messageId;
        this.selectedUserId = userId;
        
        const menu = this.elements.contextMenu;
        menu.style.left = `${e.pageX}px`;
        menu.style.top = `${e.pageY}px`;
        menu.classList.add('show');
    }
    
    hideContextMenu() {
        this.elements.contextMenu.classList.remove('show');
    }
    
    handleContextAction(action) {
        this.hideContextMenu();
        
        switch (action) {
            case 'delete':
                this.deleteMessage(this.selectedMessageId);
                break;
            case 'mute':
                this.muteUser(this.selectedUserId, 60); // 60 minutes
                break;
            case 'ban':
                if (confirm('Ти впевнений, що хочеш заблокувати цього користувача в чаті?')) {
                    this.banUser(this.selectedUserId);
                }
                break;
        }
    }
    
    async deleteMessage(messageId) {
        try {
            const response = await fetch('/api/admin/chat/delete_message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message_id: messageId })
            });
            const data = await response.json();
            if (!data.success) {
                this.showToast(data.error || 'Не вдалося видалити повідомлення', 'error');
            }
        } catch (err) {
            console.error('Delete message error:', err);
        }
    }
    
    async muteUser(userId, duration) {
        try {
            const response = await fetch('/api/admin/chat/mute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, duration: duration })
            });
            const data = await response.json();
            if (data.success) {
                this.showToast(data.message, 'success');
            } else {
                this.showToast(data.error || 'Failed to mute user', 'error');
            }
        } catch (err) {
            console.error('Mute user error:', err);
        }
    }
    
    async banUser(userId) {
        try {
            const response = await fetch('/api/admin/chat/ban', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            });
            const data = await response.json();
            if (data.success) {
                this.showToast(data.message, 'success');
            } else {
                this.showToast(data.error || 'Failed to ban user', 'error');
            }
        } catch (err) {
            console.error('Ban user error:', err);
        }
    }
    
    showWhaleNotification(data) {
        const notification = document.createElement('div');
        notification.className = 'whale-notification';
        notification.innerHTML = `
            <div class="whale-notification-content">
                <span class="whale-notification-icon">🐋</span>
                <span class="whale-notification-text">${data.message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Remove after animation
        setTimeout(() => notification.remove(), 5000);
    }
    
    showToast(message, type = 'info') {
        // Use existing toast function if available
        if (typeof showToast === 'function') {
            showToast(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize chat when script loads
let mimicChat;
document.addEventListener('DOMContentLoaded', () => {
    // Initialize chat widget for all users
    mimicChat = new MimicChat();
});
