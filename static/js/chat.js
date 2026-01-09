/**
 * MIMIC Live Chat - WebSocket Real-Time Chat + AI Support Bot
 * Socket.IO based chat for subscribers + RAG-powered AI support
 * 🗨️ SOCIAL TRADING FEED + 🤖 AI SUPPORT 🗨️
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
        this.messages = [];
        this.unreadCount = 0;
        this.contextMenu = null;
        
        // Support mode properties
        this.mode = 'chat'; // 'chat' or 'support'
        this.supportSessionId = null;
        this.supportMessages = [];
        this.supportAvailable = false;
        this.isTyping = false;
        
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
                <button class="chat-toggle-btn" id="chatToggleBtn" aria-label="Open Chat">
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
                                <div class="chat-header-title" id="chatHeaderTitle">Live Chat</div>
                                <div class="chat-header-subtitle">
                                    <span class="online-dot" id="chatOnlineDot"></span>
                                    <span id="chatOnlineCount">Connecting...</span>
                                </div>
                            </div>
                        </div>
                        <div class="chat-header-actions">
                            <button class="chat-mode-btn" id="chatModeBtn" title="Switch to AI Support">
                                <i class="fas fa-robot"></i>
                            </button>
                            <button class="chat-close-btn" id="chatCloseBtn" aria-label="Close Chat">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Mode tabs -->
                    <div class="chat-mode-tabs" id="chatModeTabs">
                        <button class="chat-mode-tab active" data-mode="chat" id="tabChat">
                            <i class="fas fa-comments"></i> Live Chat
                        </button>
                        <button class="chat-mode-tab" data-mode="support" id="tabSupport">
                            <i class="fas fa-robot"></i> AI Support
                        </button>
                    </div>
                    
                    <div class="chat-messages" id="chatMessages">
                        <div class="chat-status" id="chatStatus">
                            <div class="chat-status-icon">💬</div>
                            <div class="chat-status-text">Loading chat...</div>
                        </div>
                    </div>
                    
                    <div class="chat-input-container" id="chatInputContainer">
                        <form class="chat-input-form" id="chatInputForm">
                            <input type="text" 
                                   class="chat-input" 
                                   id="chatInput" 
                                   placeholder="Type a message..." 
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
                    <span>Delete Message</span>
                </div>
                <div class="chat-context-divider"></div>
                <div class="chat-context-item" data-action="mute">
                    <i class="fas fa-volume-mute"></i>
                    <span>Mute User (1hr)</span>
                </div>
                <div class="chat-context-item danger" data-action="ban">
                    <i class="fas fa-ban"></i>
                    <span>Ban User</span>
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
            modeBtn: document.getElementById('chatModeBtn'),
            modeTabs: document.getElementById('chatModeTabs'),
            tabChat: document.getElementById('tabChat'),
            tabSupport: document.getElementById('tabSupport'),
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
        
        // Check if support bot is available
        this.checkSupportStatus();
    }
    
    bindEvents() {
        // Toggle chat window
        this.elements.toggleBtn.addEventListener('click', () => this.toggleChat());
        this.elements.closeBtn.addEventListener('click', () => this.closeChat());
        
        // Mode switching
        this.elements.modeBtn.addEventListener('click', () => this.toggleMode());
        this.elements.tabChat.addEventListener('click', () => this.switchMode('chat'));
        this.elements.tabSupport.addEventListener('click', () => this.switchMode('support'));
        
        // Send message
        this.elements.inputForm.addEventListener('submit', (e) => {
            e.preventDefault();
            if (this.mode === 'support') {
                this.sendSupportMessage();
            } else {
                this.sendMessage();
            }
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
    
    async checkSupportStatus() {
        try {
            const response = await fetch('/api/support/status');
            const data = await response.json();
            
            if (data.success && data.available) {
                this.supportAvailable = true;
                this.elements.modeBtn.style.display = 'block';
                this.elements.modeTabs.style.display = 'flex';
            } else {
                // Hide support options if not available
                this.elements.modeBtn.style.display = 'none';
                this.elements.modeTabs.style.display = 'none';
            }
        } catch (err) {
            console.log('Support bot not available');
            this.elements.modeBtn.style.display = 'none';
            this.elements.modeTabs.style.display = 'none';
        }
    }
    
    toggleMode() {
        if (this.mode === 'chat') {
            this.switchMode('support');
        } else {
            this.switchMode('chat');
        }
    }
    
    switchMode(newMode) {
        if (this.mode === newMode) return;
        
        this.mode = newMode;
        
        // Update tabs
        this.elements.tabChat.classList.toggle('active', newMode === 'chat');
        this.elements.tabSupport.classList.toggle('active', newMode === 'support');
        
        // Update header
        if (newMode === 'support') {
            this.elements.headerIcon.innerHTML = '<i class="fas fa-robot"></i>';
            this.elements.headerTitle.textContent = 'AI Support';
            this.elements.onlineCount.textContent = 'Ask me anything!';
            this.elements.onlineDot.style.background = '#9b59b6'; // Purple for AI
            this.elements.modeBtn.innerHTML = '<i class="fas fa-comments"></i>';
            this.elements.modeBtn.title = 'Switch to Live Chat';
            this.elements.input.placeholder = 'Ask a question about MIMIC...';
            
            // Show support messages
            this.renderSupportMessages();
            
            // Enable input for support (no subscription required)
            this.elements.input.disabled = false;
            this.elements.sendBtn.disabled = false;
        } else {
            this.elements.headerIcon.innerHTML = '<i class="fas fa-comments"></i>';
            this.elements.headerTitle.textContent = 'Live Chat';
            this.elements.onlineCount.textContent = this.canChat ? 'General Room' : 'Connecting...';
            this.elements.onlineDot.style.background = '#2ecc71'; // Green for online
            this.elements.modeBtn.innerHTML = '<i class="fas fa-robot"></i>';
            this.elements.modeBtn.title = 'Switch to AI Support';
            this.elements.input.placeholder = 'Type a message...';
            
            // Show chat messages
            this.renderMessages();
            
            // Restore chat input state
            if (this.canChat) {
                this.enableInput();
            } else {
                this.disableInput();
            }
        }
    }
    
    async checkChatStatus() {
        try {
            const response = await fetch('/api/chat/status');
            const data = await response.json();
            
            if (data.success) {
                this.canChat = data.can_chat;
                this.isAdmin = data.is_admin;
                
                if (data.can_chat) {
                    this.initSocket();
                } else if (data.is_banned) {
                    this.showBannedStatus(data.ban_type, data.ban_reason, data.ban_expires_at);
                } else if (!data.has_subscription) {
                    this.showSubscriptionRequired();
                }
            }
        } catch (err) {
            console.error('Chat status check failed:', err);
            this.showErrorStatus('Unable to connect to chat');
        }
    }
    
    initSocket() {
        // Use existing Socket.IO connection or create new one
        if (typeof socket !== 'undefined' && socket.connected) {
            this.socket = socket;
        } else {
            this.socket = io();
        }
        
        this.isConnected = true;
        
        // Socket event handlers
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
        this.elements.onlineCount.textContent = 'General Room';
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
        
        // Join chat room if connected
        if (this.socket && this.canChat) {
            this.socket.emit('join_chat', { room: this.room });
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
            msgEl.querySelector('.chat-bubble').innerHTML = '<i>Message deleted</i>';
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
    
    // ==================== AI Support Bot Methods ====================
    
    async sendSupportMessage() {
        const text = this.elements.input.value.trim();
        if (!text || this.isTyping) return;
        
        // Clear input immediately
        this.elements.input.value = '';
        
        // Add user message to display
        const userMsg = {
            role: 'user',
            content: text,
            created_at: new Date().toISOString()
        };
        this.supportMessages.push(userMsg);
        this.appendSupportMessage(userMsg);
        this.scrollToBottom();
        
        // Show typing indicator
        this.showTypingIndicator();
        
        try {
            const response = await fetch('/api/support/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    session_id: this.supportSessionId
                })
            });
            
            const data = await response.json();
            
            this.hideTypingIndicator();
            
            if (data.success) {
                // Save session ID for conversation continuity
                this.supportSessionId = data.session_id;
                
                // Add AI response
                const aiMsg = {
                    role: 'assistant',
                    content: data.answer,
                    confidence: data.confidence,
                    sources: data.sources,
                    needs_human_review: data.needs_human_review,
                    created_at: new Date().toISOString()
                };
                this.supportMessages.push(aiMsg);
                this.appendSupportMessage(aiMsg);
            } else {
                // Show error message
                this.appendSupportMessage({
                    role: 'system',
                    content: data.error || 'Sorry, I encountered an error. Please try again.',
                    created_at: new Date().toISOString()
                });
            }
            
            this.scrollToBottom();
            
        } catch (err) {
            this.hideTypingIndicator();
            console.error('Support chat error:', err);
            this.appendSupportMessage({
                role: 'system',
                content: 'Failed to connect to AI Support. Please try again later.',
                created_at: new Date().toISOString()
            });
            this.scrollToBottom();
        }
    }
    
    renderSupportMessages() {
        this.elements.messages.innerHTML = '';
        
        if (this.supportMessages.length === 0) {
            // Show welcome message for support
            this.elements.messages.innerHTML = `
                <div class="chat-status support-welcome">
                    <div class="chat-status-icon">🤖</div>
                    <div class="chat-status-text">
                        <strong>AI Support Bot</strong><br>
                        Ask me anything about the MIMIC platform!<br><br>
                        <small>Try questions like:</small>
                        <ul class="support-suggestions">
                            <li onclick="mimicChat.askSuggestion('How do I connect my Binance account?')">How do I connect my Binance account?</li>
                            <li onclick="mimicChat.askSuggestion('What is DCA?')">What is DCA?</li>
                            <li onclick="mimicChat.askSuggestion('How does the referral system work?')">How does the referral system work?</li>
                        </ul>
                    </div>
                </div>
            `;
            return;
        }
        
        this.supportMessages.forEach(msg => this.appendSupportMessage(msg));
    }
    
    appendSupportMessage(msg) {
        const isUser = msg.role === 'user';
        const isSystem = msg.role === 'system';
        const isAssistant = msg.role === 'assistant';
        
        let confidenceHtml = '';
        if (isAssistant && msg.confidence !== undefined) {
            const confPercent = Math.round(msg.confidence * 100);
            let confClass = 'high';
            if (msg.confidence < 0.6) confClass = 'low';
            else if (msg.confidence < 0.8) confClass = 'medium';
            
            confidenceHtml = `
                <div class="support-confidence ${confClass}">
                    <span class="confidence-bar" style="width: ${confPercent}%"></span>
                    <span class="confidence-text">${confPercent}% confidence</span>
                </div>
            `;
            
            if (msg.needs_human_review) {
                confidenceHtml += `
                    <div class="support-review-note">
                        <i class="fas fa-user-clock"></i> 
                        This has been flagged for human review
                    </div>
                `;
            }
        }
        
        const msgHTML = `
            <div class="chat-message support-message ${isUser ? 'own' : ''} ${isSystem ? 'system' : ''}">
                <div class="chat-avatar">
                    ${isUser ? '<span>👤</span>' : isSystem ? '<span>⚠️</span>' : '<span>🤖</span>'}
                </div>
                <div class="chat-message-content">
                    <div class="chat-message-header">
                        <span class="chat-username">${isUser ? 'You' : isSystem ? 'System' : 'AI Support'}</span>
                        <span class="chat-timestamp">${this.formatTime(msg.created_at)}</span>
                    </div>
                    <div class="chat-bubble">${this.formatSupportContent(msg.content)}</div>
                    ${confidenceHtml}
                </div>
            </div>
        `;
        
        this.elements.messages.insertAdjacentHTML('beforeend', msgHTML);
    }
    
    askSuggestion(question) {
        this.elements.input.value = question;
        this.sendSupportMessage();
    }
    
    showTypingIndicator() {
        this.isTyping = true;
        const indicator = document.createElement('div');
        indicator.className = 'chat-message support-message typing-indicator';
        indicator.id = 'typingIndicator';
        indicator.innerHTML = `
            <div class="chat-avatar"><span>🤖</span></div>
            <div class="chat-message-content">
                <div class="chat-bubble typing">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                </div>
            </div>
        `;
        this.elements.messages.appendChild(indicator);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        this.isTyping = false;
        const indicator = document.getElementById('typingIndicator');
        if (indicator) indicator.remove();
    }
    
    formatTime(isoString) {
        if (!isoString) return '';
        const date = new Date(isoString);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    formatSupportContent(content) {
        // Escape HTML first
        let formatted = this.escapeHtml(content);
        
        // Convert markdown-like formatting
        // Bold: **text** -> <strong>text</strong>
        formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        
        // Code: `code` -> <code>code</code>
        formatted = formatted.replace(/`(.+?)`/g, '<code>$1</code>');
        
        // Links: [text](url) -> <a href="url">text</a>
        formatted = formatted.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>');
        
        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');
        
        return formatted;
    }
    
    renderMessages() {
        // Clear current messages
        this.elements.messages.innerHTML = '';
        this.elements.status.style.display = 'none';
        
        if (this.messages.length === 0) {
            this.elements.messages.innerHTML = `
                <div class="chat-status">
                    <div class="chat-status-icon">💬</div>
                    <div class="chat-status-text">No messages yet. Start the conversation!</div>
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
                            ${isAdminMsg ? '<span class="admin-badge">Admin</span>' : ''}
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
        this.elements.input.placeholder = 'Type a message...';
    }
    
    disableInput() {
        this.elements.input.disabled = true;
        this.elements.sendBtn.disabled = true;
        this.elements.input.placeholder = 'Chat disabled';
    }
    
    showSubscriptionRequired() {
        this.elements.status.innerHTML = `
            <div class="chat-status-icon">🔒</div>
            <div class="chat-status-text">
                <strong>Subscription Required</strong><br>
                Upgrade to a paid plan to access live chat with fellow traders.
            </div>
            <a href="/subscribe" class="chat-status-btn">View Plans</a>
        `;
        this.elements.status.style.display = 'flex';
        this.elements.messages.innerHTML = '';
        this.elements.messages.appendChild(this.elements.status);
        this.disableInput();
    }
    
    showBannedStatus(banType, reason, expiresAt) {
        const expireText = expiresAt 
            ? `<br><small>Expires: ${new Date(expiresAt).toLocaleString()}</small>`
            : '';
        
        this.elements.status.innerHTML = `
            <div class="chat-status-icon">🚫</div>
            <div class="chat-status-text">
                <strong>You are ${banType === 'ban' ? 'banned' : 'muted'}</strong><br>
                ${reason || 'Chat rule violation'}
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
                if (confirm('Are you sure you want to ban this user from chat?')) {
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
                this.showToast(data.error || 'Failed to delete message', 'error');
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
    // Only initialize if user is logged in (check for common auth indicators)
    if (document.querySelector('.user-menu') || document.querySelector('[data-user-id]')) {
        mimicChat = new MimicChat();
    }
});
