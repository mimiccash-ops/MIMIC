/**
 * MIMIC - Premium Trading Platform
 * Innovative UI/UX JavaScript System
 */

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    initLanguage();
    initMobileMenu();
    initUserMenu();
    initSections();
    initAnimations();
    initSounds();
    initTooltips();
    markActiveNav();
});

// ==================== MOBILE MENU ====================
let mobileMenuOpen = false;

function initMobileMenu() {
    const overlay = document.getElementById('mobileOverlay');
    if (overlay) {
        overlay.addEventListener('click', closeMobileMenu);
    }
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && mobileMenuOpen) {
            closeMobileMenu();
        }
    });
}

function toggleMobileMenu() {
    mobileMenuOpen = !mobileMenuOpen;
    
    const menu = document.getElementById('mobileMenu');
    const overlay = document.getElementById('mobileOverlay');
    const btn = document.querySelector('.mobile-menu-btn');
    
    if (mobileMenuOpen) {
        menu?.classList.add('active');
        overlay?.classList.add('active');
        btn?.classList.add('active');
        document.body.style.overflow = 'hidden';
    } else {
        menu?.classList.remove('active');
        overlay?.classList.remove('active');
        btn?.classList.remove('active');
        document.body.style.overflow = '';
    }
    
    playSound('click');
}

function closeMobileMenu() {
    mobileMenuOpen = false;
    
    const menu = document.getElementById('mobileMenu');
    const overlay = document.getElementById('mobileOverlay');
    const btn = document.querySelector('.mobile-menu-btn');
    
    menu?.classList.remove('active');
    overlay?.classList.remove('active');
    btn?.classList.remove('active');
    document.body.style.overflow = '';
}

// ==================== USER MENU ====================
let userMenuOpen = false;

function initUserMenu() {
    document.addEventListener('click', (e) => {
        const userMenu = document.querySelector('.user-menu');
        const dropdown = document.getElementById('userDropdown');
        
        if (userMenu && dropdown) {
            if (!userMenu.contains(e.target) && !dropdown.contains(e.target)) {
                closeUserMenu();
            }
        }
    });
}

function toggleUserMenu() {
    userMenuOpen = !userMenuOpen;
    
    const userMenu = document.querySelector('.user-menu');
    const dropdown = document.getElementById('userDropdown');
    
    if (userMenuOpen) {
        userMenu?.classList.add('active');
        dropdown?.classList.add('active');
    } else {
        userMenu?.classList.remove('active');
        dropdown?.classList.remove('active');
    }
    
    playSound('click');
}

function closeUserMenu() {
    userMenuOpen = false;
    
    const userMenu = document.querySelector('.user-menu');
    const dropdown = document.getElementById('userDropdown');
    
    userMenu?.classList.remove('active');
    dropdown?.classList.remove('active');
}

// ==================== ACTIVE NAVIGATION ====================
function markActiveNav() {
    const currentPath = window.location.pathname;
    
    document.querySelectorAll('.nav-pill, .mobile-nav-item').forEach(link => {
        const href = link.getAttribute('href');
        if (href === currentPath) {
            link.classList.add('active');
        }
    });
}

// ==================== SECTION NAVIGATION ====================
let currentSection = 'overview';

function initSections() {
    const savedSection = localStorage.getItem('activeSection') || 'overview';
    
    // Show saved section if exists
    if (document.querySelector(`.section-content[data-section="${savedSection}"]`)) {
        showSection(savedSection, false);
    } else if (document.querySelector('.section-content[data-section="overview"]')) {
        // Fallback to overview if saved section doesn't exist
        showSection('overview', false);
    }
    
    // Set initial active states for dropdown section links
    document.querySelectorAll('.dropdown-section-link').forEach(link => {
        link.classList.toggle('active', link.getAttribute('data-section') === (localStorage.getItem('activeSection') || 'overview'));
    });
}

function showSection(sectionId, animate = true) {
    currentSection = sectionId;
    localStorage.setItem('activeSection', sectionId);
    
    // Update category tabs
    document.querySelectorAll('.category-tab').forEach(tab => {
        tab.classList.toggle('active', tab.getAttribute('data-section') === sectionId);
    });
    
    // Update mobile nav items
    document.querySelectorAll('.mobile-section-link').forEach(link => {
        link.classList.toggle('active', link.getAttribute('data-section') === sectionId);
    });
    
    // Update dropdown section links
    document.querySelectorAll('.dropdown-section-link').forEach(link => {
        link.classList.toggle('active', link.getAttribute('data-section') === sectionId);
    });
    
    // Show/hide sections
    document.querySelectorAll('.section-content').forEach(section => {
        const isActive = section.getAttribute('data-section') === sectionId;
        section.classList.toggle('active', isActive);
    });
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    // Close mobile menu if open
    closeMobileMenu();
    
    playSound('click');
}

// ==================== LANGUAGE SYSTEM ====================
const translations = {
    en: {
        // Navigation
        'nav.dashboard': 'Dashboard',
        'nav.messages': 'Messages',
        'nav.settings': 'Settings',
        'nav.changePassword': 'Security',
        'nav.logout': 'Logout',
        'nav.login': 'Login',
        'nav.register': 'Register',
        'nav.copyTrading': 'Copy Trading',
        'nav.connected': 'Connected',
        
        // Sections
        'section.overview': 'Overview',
        'section.trading': 'Trading',
        'section.positions': 'Positions',
        'section.history': 'History',
        'section.stats': 'Statistics',
        'section.exchange': 'Exchange',
        'section.settings': 'Settings',
        'section.users': 'Users',
        'section.controls': 'Controls',
        'section.telegram': 'Telegram',
        
        // Dashboard
        'dash.master': 'MASTER',
        'dash.live': 'LIVE',
        'dash.nodes': 'Nodes',
        'dash.trades': 'Trades',
        'dash.masterPositions': 'Master Positions',
        'dash.openPositions': 'Open Positions',
        'dash.tradeHistory': 'Trade History',
        'dash.connectedExchanges': 'Connected Exchanges',
        'dash.addExchange': 'Add Exchange',
        'dash.selectExchange': 'Select Exchange...',
        'dash.accountLabel': 'Account Label (optional)',
        'dash.apiKey': 'API Key',
        'dash.apiSecret': 'API Secret',
        'dash.passphrase': 'Passphrase',
        'dash.submitRequest': 'Submit Request',
        'dash.telegramNotifications': 'Telegram Notifications',
        'dash.enabled': 'Enabled',
        'dash.disabled': 'Disabled',
        'dash.enableNotifications': 'Enable notifications',
        'dash.save': 'Save',
        'dash.email': 'Email Address',
        'dash.set': 'Set',
        'dash.notSet': 'Not Set',
        'dash.targetGoal': 'Target Goal',
        'dash.targetAmount': 'Target Amount',
        'dash.profileAvatar': 'Profile Avatar',
        'dash.change': 'Change',
        'dash.changePassword': 'Change Password',
        'dash.securitySettings': 'Security settings',
        'dash.noOpenPositions': 'No open positions',
        'dash.noHistory': 'No trade history yet',
        'dash.loadingExchanges': 'Loading exchanges...',
        'dash.noExchanges': 'No exchanges connected',
        'dash.chooseAvatar': 'Choose Avatar',
        'dash.saveAvatar': 'Save Avatar',
        'dash.growthDynamics': 'Growth Dynamics',
        'dash.tradingParameters': 'Trading Parameters',
        'dash.takeProfit': 'Take Profit',
        'dash.stopLoss': 'Stop Loss',
        'dash.result': 'Result',
        'dash.winRate': 'Win Rate',
        'dash.avgRoi': 'Avg ROI',
        'dash.emergencyExit': 'Emergency Exit',
        'dash.risk': 'Risk',
        'dash.leverage': 'Leverage',
        'dash.totalTrades': 'Total Trades',
        'dash.auto': 'AUTO',
        'dash.tradingParams': 'Trading Parameters',
        'dash.setByAdmin': 'Set by Admin',
        'dash.riskPercent': 'Risk %',
        'dash.leverageX': 'Leverage',
        'dash.maxPositions': 'Max Positions',
        'dash.minBalance': 'Min Balance',
        'dash.tradingParamsInfo': 'These parameters are configured by the administrator and apply to all trades.',
        'dash.changeAvatar': 'Change Avatar',
        'dash.chooseEmoji': 'Choose Emoji',
        'dash.orUploadImage': 'Or Upload Image',
        'dash.avatarInfo': 'Choose an emoji or upload an image',
        
        // Admin
        'admin.liveLogs': 'Live Logs',
        'admin.clearLogs': 'Clear',
        'admin.waitingSignals': 'Waiting for signals...',
        'admin.growth': 'Growth',
        'admin.masterPositions': 'Master Positions',
        'admin.exchangeConfig': 'Exchange Configuration',
        'admin.userExchanges': 'User Exchanges',
        'admin.pendingExchanges': 'Pending Exchanges',
        'admin.networkNodes': 'Network Nodes',
        'admin.closedTrades': 'Closed Trades',
        'admin.controlTerminal': 'Control Terminal',
        'admin.globalSettings': 'Global Settings',
        'admin.adminSettings': 'Admin Settings',
        'admin.terminal': 'Terminal',
        'admin.connectExchangeHint': 'Connect exchanges with your admin API keys first. Then users can add their own keys.',
        'admin.tableUser': 'User',
        'admin.tableStatus': 'Status',
        'admin.tableBalance': 'Balance',
        'admin.tableActions': 'Actions',
        'admin.tableTime': 'Time',
        'admin.tableNode': 'Node',
        'admin.tableSymbol': 'Symbol',
        'admin.tableSide': 'Side',
        'admin.tablePnl': 'PnL',
        'dash.loading': 'Loading...',
        
        // Buttons
        'btn.save': 'Save',
        'btn.cancel': 'Cancel',
        'btn.submit': 'Submit',
        'btn.close': 'Close',
        'btn.delete': 'Delete',
        'btn.edit': 'Edit',
        'btn.add': 'Add',
        'btn.start': 'Start',
        'btn.stop': 'Stop',
        'btn.pause': 'Pause',
        'btn.reload': 'Reload',
        'btn.panic': 'Panic',
        'btn.send': 'Send',
        
        // Status
        'status.online': 'Online',
        'status.offline': 'Offline',
        'status.active': 'Active',
        'status.inactive': 'Inactive',
        'status.pending': 'Pending',
        'status.approved': 'Approved',
        'status.rejected': 'Rejected',
        'status.trading': 'Trading',
        'status.ready': 'Ready',
        'status.awaiting': 'Awaiting',
        
        // Common
        'common.loading': 'Loading...',
        'common.error': 'Error',
        'common.success': 'Success',
        'common.confirm': 'Confirm',
        'common.yes': 'Yes',
        'common.no': 'No',
        'common.close': 'Close',
        'common.back': 'Back',
        'common.next': 'Next',
        'common.previous': 'Previous',
        
        // Auth
        'auth.welcomeBack': 'Welcome Back',
        'auth.signInToMimic': 'Sign in to your MIMIC account',
        'auth.systemReady': 'SYSTEM READY',
        'auth.usernamePhone': 'Username / Phone',
        'auth.password': 'Password',
        'auth.rememberMe': 'Remember me',
        'auth.forgotPassword': 'Forgot password?',
        'auth.dontHaveAccount': 'Don\'t have an account?',
        'auth.getStarted': 'Get Started',
        'auth.signIn': 'Sign In',
        'auth.sslTls': 'SSL/TLS',
        'auth.encrypted': 'Encrypted',
        'auth.secure': 'Secure',
        'auth.startMimicking': 'Start mimicking the best traders',
        'auth.stepProfile': 'Profile',
        'auth.stepSecurity': 'Security',
        'auth.stepApi': 'API',
        'auth.firstName': 'First Name',
        'auth.lastName': 'Last Name',
        'auth.phone': 'Phone (Username)',
        'auth.email': 'Email (for recovery)',
        'auth.emailRecommended': 'Recommended for account recovery',
        'auth.minChars': 'Minimum 6 characters',
        'auth.exchangeApi': 'Exchange API',
        'auth.selectExchange': 'Select Exchange',
        'auth.chooseExchange': '-- Choose your exchange --',
        'auth.noExchange': 'Don\'t have an exchange account?',
        'auth.createPartner': 'Register on your preferred exchange first',
        'auth.registerExchange': 'Register',
        'auth.apiKey': 'API Key',
        'auth.apiSecret': 'API Secret',
        'auth.passphrase': 'Passphrase',
        'auth.passphraseRequired': 'This exchange requires a passphrase',
        'auth.enterUsername': 'Enter your username...',
        'auth.enterPassword': '••••••••',
        'auth.firstNamePlaceholder': 'John',
        'auth.lastNamePlaceholder': 'Smith',
        'auth.phonePlaceholder': '+1 XXX XXX XXXX',
        'auth.emailPlaceholder': 'your@email.com',
        'auth.apiKeyPlaceholder': 'Your Exchange API Key',
        'auth.apiSecretPlaceholder': 'Secret Key',
        'auth.passphrasePlaceholder': 'API Passphrase (required for this exchange)',
        'auth.repeatPassword': 'Repeat password',
        'auth.securityTips': 'Important Security Tips:',
        'auth.enableFutures': 'Enable Futures Trading permissions',
        'auth.disableWithdrawals': 'Disable Withdrawals',
        'auth.enableIpWhitelist': 'Enable IP Whitelist for security',
        'auth.howItWorks': 'How it works:',
        'auth.step1': 'Your API keys will be verified',
        'auth.step2': 'Your request will be sent to the administrator',
        'auth.step3': 'Admin will decide whether to start trading',
        'auth.agreeTerms': 'I agree to the terms of service and understand the risks associated with cryptocurrency futures trading',
        'auth.haveAccount': 'Already have an account?',
        'auth.weakPassword': 'Weak password',
        'auth.mediumPassword': 'Medium password',
        'auth.strongPassword': 'Strong password',
        
        // Home page
        'home.automatedCopyTrading': 'Automated Copy Trading Platform',
        'home.tradeLikeTheBest': 'Trade Like The Best',
        'home.subtitle': 'Connect your exchange API and automatically mirror the trades of professional traders. No manual intervention required — fully automated profits.',
        'home.startTradingNow': 'Start Trading Now',
        'home.signIn': 'Sign In',
        'home.automatedTrading': 'Automated Trading',
        'home.signalLatency': 'Signal Latency',
        'home.transparency': 'Transparency',
        'home.coreFeatures': 'Core Features',
        'home.whyChooseMimic': 'Why Choose MIMIC?',
        'home.whyChooseSubtitle': 'Professional-grade copy trading with cutting-edge technology and zero compromise on security.',
        'home.lightningFast': 'Lightning Fast',
        'home.lightningFastDesc': 'Sub-second trade execution ensures you never miss an opportunity. Our system mirrors trades in real-time with minimal latency.',
        'home.maximumSecurity': 'Maximum Security',
        'home.maximumSecurityDesc': 'Your API keys are encrypted and stored securely. We never have withdrawal permissions — your funds always stay in your control.',
        'home.realTimeAnalytics': 'Real-time Analytics',
        'home.realTimeAnalyticsDesc': 'Track your portfolio performance with detailed statistics, trade history, and growth charts — all in one dashboard.',
        'home.customizableRisk': 'Customizable Risk',
        'home.customizableRiskDesc': 'Set your own risk parameters, leverage limits, and position sizes. Trade confidently with settings that match your strategy.',
        'home.instantNotifications': 'Instant Notifications',
        'home.instantNotificationsDesc': 'Get Telegram notifications for every trade, position update, and important system events. Stay informed 24/7.',
        'home.directSupport': 'Direct Support',
        'home.directSupportDesc': 'Built-in messaging system for direct communication with administrators. Get help when you need it, no third-party tickets.',
        'home.gettingStarted': 'Getting Started',
        'home.howItWorks': 'How It Works',
        'home.howItWorksSubtitle': 'Start copy trading in three simple steps. No complex setup required.',
        'home.createAccount': 'Create Your Account',
        'home.createAccountDesc': 'Register with your phone number and connect your exchange account using API keys. We support major exchanges including Binance, Bybit, OKX, and more.',
        'home.waitApproval': 'Wait for Approval',
        'home.waitApprovalDesc': 'Our team verifies your API keys and account setup. Once approved, your account will be activated and ready for automated trading.',
        'home.startMimicking': 'Start Mimicking',
        'home.startMimickingDesc': 'Once active, your account automatically mirrors the master trader\'s positions. Sit back and watch your portfolio grow with professional-level trades.',
        'home.supportedExchanges': 'Supported Exchanges',
        'home.tradeOnTopExchanges': 'Trade on Top Exchanges',
        'home.tradeOnTopExchangesSubtitle': 'Connect your favorite exchange and start copy trading instantly.',
        'home.available': 'Available',
        'home.readyToStart': 'Ready to Start Mimicking?',
        'home.readyToStartSubtitle': 'Join now and let professional traders work for you. Your journey to automated profits starts here.',
        'home.createFreeAccount': 'Create Free Account',
        
        // Additional dashboard
        'dash.target': 'Target',
        'dash.statistics': 'Statistics',
        'dash.messages': 'Messages',
        'dash.clickChange': 'Click "Change" to select a new avatar',
        'dash.trades': 'trades',
        'dash.users': 'users',
        'dash.live': 'Live',
        'dash.pending': 'Pending',
        'dash.active': 'Active',
        
        // Additional admin
        'admin.verifiedExchanges': 'Verified Exchanges',
        'admin.nodeSettings': 'Node Settings',
        'admin.updateCredentials': 'Update Credentials',
        'admin.connectExchange': 'Connect Exchange (Admin)',
        'admin.addExchange': 'Add Exchange',
        'admin.connectWithAdminKeys': 'Connect with YOUR admin API keys. Once verified, users can add their own keys to this exchange.',
        'admin.exchange': 'Exchange',
        'admin.adminApiKey': 'Admin API Key',
        'admin.adminApiSecret': 'Admin API Secret',
        'admin.verifyConnect': 'Verify & Connect',
        'admin.alreadyVerified': 'Already verified!',
        'admin.reverifyKeys': 'You can re-verify with new API keys if needed.',
        'admin.notConnectedYet': 'Not connected yet',
        'admin.enterAdminKeys': 'Enter your admin API keys to verify this exchange.',
        'admin.start': 'START',
        'admin.pause': 'PAUSE',
        'admin.reload': 'RELOAD',
        'admin.tradingPaused': 'TRADING PAUSED',
        'admin.closeAllPositions': 'Close ALL positions on ALL accounts?',
        'admin.irreversible': 'This is IRREVERSIBLE!',
        'admin.executingPanic': 'Executing panic exit...',
        'admin.closed': 'Closed',
        'admin.master': 'Master',
        'admin.slaves': 'Slaves',
        'admin.deleteExchange': 'Delete this exchange?',
        'admin.disconnectExchange': 'Disconnect',
        'admin.disconnectConfirm': 'Disconnect',
        'admin.disconnectConfirmText': 'This will also disable it for all users.',
        'admin.rejectExchange': 'Reject this exchange?',
        'admin.upload': 'Upload',
        'admin.emoji': 'Emoji',
        'admin.photo': 'Photo',
        'admin.selectMax2mb': 'Click to select (max 2MB)',
        'admin.avatar': 'Avatar',
        'admin.settingsFor': 'Settings for:',
        'admin.newUsername': 'New username',
        'admin.newPassword': 'New password',
        'admin.selectExchange': 'Select Exchange...',
        'admin.logsCleared': 'Logs cleared',
        
        // Additional status
        'status.long': 'LONG',
        'status.short': 'SHORT',
        
        // Additional buttons
        'btn.signIn': 'Sign In',
        'btn.startMimicking': 'Start Mimicking',
        'btn.upload': 'Upload',
        'btn.updateCredentials': 'Update Credentials',
        
        // Disclaimer
        'disclaimer.title': 'Risk Disclaimer',
        'disclaimer.acknowledged': 'MUST READ',
        'disclaimer.mainText': 'ATTENTION: Trading cryptocurrencies and futures involves SIGNIFICANT RISK. The volatile nature of crypto markets means prices can change rapidly and unpredictably. Copy trading does NOT eliminate risk — you are still responsible for your own investment decisions. Never invest more than you can afford to lose. Past performance is NOT indicative of future results.',
        'disclaimer.point1': 'Cryptocurrency trading involves substantial risk of loss and is not suitable for every investor.',
        'disclaimer.point2': 'Past performance does not guarantee future results. You may lose your entire investment.',
        'disclaimer.point3': 'Only invest what you can afford to lose. This is not financial advice.',
        'disclaimer.point4': 'Leverage amplifies both gains and losses. Use extreme caution with leveraged positions.',
        
        // Change Password page
        'auth.changePassword': 'Change Password',
        'auth.enterPasswordInfo': 'Update your account security credentials',
        'auth.secureSession': 'SECURE SESSION',
        'auth.currentPassword': 'Current Password',
        'auth.newPassword': 'New Password',
        'auth.enterCurrentPassword': 'Enter current password',
        'auth.passwordRequirements': 'Min 8 chars, uppercase, lowercase, number',
        'btn.saveChanges': 'Save Changes',
        'nav.backToDashboard': 'Back to Dashboard',
        'security.encrypted': 'Encrypted',
        'security.secure': 'Secure',
        
        // Forgot Password page
        'auth.resetPassword': 'Reset Password',
        'auth.chooseMethod': 'Choose how to receive your verification code',
        'auth.identifier': 'Email, phone or username',
        'auth.identifierPlaceholder': 'user@email.com or username',
        'auth.selectMethod': 'Select Method',
        'auth.receiveEmail': 'Receive code via email',
        'auth.receiveTelegram': 'Receive code via chat',
        'auth.notConfigured': 'Not configured',
        'auth.unavailable': 'Password reset unavailable',
        'auth.noMethodsConfigured': 'Neither Email nor Telegram are configured. Contact administrator for password reset.',
        'auth.emailRequired': 'Requires linked email',
        'auth.telegramWorks': 'Works if notifications enabled',
        'btn.sendCode': 'Send Code',
        'auth.backToSignIn': 'Back to Sign In',
        'auth.cantReset': 'Can\'t reset password?',
        'auth.contactSupport': 'Contact administrator through support for assistance.',
        
        // Reset Password page
        'auth.newPasswordTitle': 'New Password',
        'auth.enterCodeAndPassword': 'Enter verification code and new password',
        'auth.codeSentTo': 'Code sent to',
        'auth.codeSentTelegram': 'Code sent to Telegram',
        'auth.confirmationCode': 'Confirmation Code',
        'auth.confirmPassword': 'Confirm password',
        'auth.passwordsDontMatch': 'Passwords do not match',
        'auth.changePasswordBtn': 'Change Password',
        'auth.didntReceiveCode': 'Didn\'t receive the code?',
        'auth.resendCode': 'Send again',
        'auth.tryAnotherMethod': 'Try another method',
        
        // Notifications
        'notify.email': 'Email',
        'notify.telegram': 'Telegram',
        
        // Messages
        'messages.newMessage': 'New Message',
        'messages.subject': 'Subject',
        'messages.enterSubject': 'Enter message subject',
        'messages.content': 'Message',
        'messages.message': 'Message',
        'messages.enterMessage': 'Describe your question or issue...',
        'messages.enterMessageText': 'Enter message text...',
        'messages.enterReply': 'Enter your reply...',
        'messages.send': 'Send',
        'messages.reply': 'Reply',
        'messages.inbox': 'Inbox',
        'messages.sent': 'Sent',
        'messages.noMessages': 'No messages yet',
        'messages.compose': 'Compose',
        'messages.myMessages': 'My Messages',
        'messages.writeAdmin': 'Write to the administrator to get help',
        'messages.writeToAdmin': 'Write to Admin',
        'messages.writeToUser': 'Write to User',
        'messages.maxChars': 'Maximum 2000 characters',
        'messages.replies': 'replies',
        'messages.messageCenter': 'Message Center',
        'messages.total': 'Total',
        'messages.new': 'New',
        'messages.handled': 'Handled',
        'messages.repliesCount': 'Replies',
        'messages.userRequests': 'User Requests',
        'messages.all': 'All',
        'messages.unread': 'Unread',
        'messages.awaitingReply': 'Awaiting reply',
        'messages.noRequests': 'No requests',
        'messages.userMessagesAppear': 'User messages will appear here',
        'messages.recipient': 'Recipient',
        'messages.selectUser': 'Select user...',
        
        // Dashboard extras
        'dash.telegramChatId': 'Telegram Chat ID',
        'dash.emailPlaceholder': 'your@email.com',
        'dash.periodPnl': 'Period P&L',
        'dash.scanningPositions': 'Scanning for positions...',
        'dash.loadingConnections': 'Loading connections...',
        'dash.enableNotifications': 'Enable notifications',
        
        // Footer
        'footer.platform': 'Platform',
        'footer.home': 'Home',
        'footer.signIn': 'Sign In',
        'footer.getStarted': 'Get Started',
        'footer.exchanges': 'Exchanges',
        'footer.features': 'Features',
        'footer.copyTrading': 'Copy Trading',
        'footer.realTimeMirroring': 'Real-time Mirroring',
        'footer.riskManagement': 'Risk Management',
        'footer.telegramAlerts': 'Telegram Alerts',
        'footer.desc': 'Next-generation automated copy trading platform. Mirror professional traders in real-time.',
        'footer.trading': 'Trading',
        'footer.latency': 'Latency',
        'footer.automated': 'Automated',
        'footer.rights': 'All rights reserved.',
        'footer.warning': 'Trading involves risk. Not financial advice.',
        
        // Navigation extras
        'nav.community': 'Community',
        'nav.account': 'Account',
        'nav.admin': 'Admin',
        'nav.leaderboard': 'Leaderboard',
        'nav.tournaments': 'Tournaments',
        'nav.governance': 'Governance',
        'nav.apiKeys': 'API Keys',
        'nav.payouts': 'Payouts',
        
        // Leaderboard page
        'leaderboard.title': 'Leaderboard',
        'leaderboard.subtitle': 'Real-time performance tracking of our top copy traders. See who\'s leading the pack.',
        'leaderboard.totalUsers': 'Total Users',
        'leaderboard.totalVolume': 'Total Volume',
        'leaderboard.totalProfit': 'Total Profit',
        'leaderboard.totalTrades': 'Total Trades',
        'leaderboard.topCopiers': 'Top Copiers',
        'leaderboard.today': 'Today',
        'leaderboard.trader': 'Trader',
        'leaderboard.trades': 'Trades',
        'leaderboard.masterTrader': 'Master Trader',
        'leaderboard.30DayPerformance': '30 Day Performance',
        'leaderboard.totalPnl': 'Total PnL',
        'leaderboard.winRate': 'Win Rate',
        'leaderboard.readyToJoin': 'Ready to Join the Winners?',
        'leaderboard.readyToJoinSubtitle': 'Start copy trading today and automatically mirror the trades of our top performers. No experience required.',
        'leaderboard.copyNow': 'Copy Now — Start Free',
        'leaderboard.loadingLeaderboard': 'Loading leaderboard...',
        'leaderboard.noActivity': 'No trading activity yet. Be the first!',
        'leaderboard.failedToLoad': 'Failed to load data. Please try again.',
        'leaderboard.noBalanceHistory': 'No balance history available',
        
        // Tournament page
        'tournament.title': 'Weekly Tournament',
        'tournament.subtitle': 'Compete with traders worldwide. Join with $10, trade your best, and win a share of the prize pool. TOP-3 by ROI take it all!',
        'tournament.endsIn': 'Tournament Ends In',
        'tournament.startsIn': 'Tournament Starts In',
        'tournament.ended': 'Tournament Ended',
        'tournament.days': 'Days',
        'tournament.hours': 'Hours',
        'tournament.minutes': 'Minutes',
        'tournament.seconds': 'Seconds',
        'tournament.live': 'LIVE - Trading Active',
        'tournament.registrationOpen': 'Registration Open',
        'tournament.calculatingResults': 'Calculating Results...',
        'tournament.prizePool': 'Prize Pool',
        'tournament.participants': 'Participants',
        'tournament.entryFee': 'Entry Fee',
        'tournament.topRoi': 'Top ROI',
        'tournament.prizeDistribution': 'Prize Distribution',
        'tournament.1stPlace': '1st Place',
        'tournament.2ndPlace': '2nd Place',
        'tournament.3rdPlace': '3rd Place',
        'tournament.loginToJoin': 'Login to Join',
        'tournament.joinFor': 'Join for',
        'tournament.registrationClosed': 'Registration Closed',
        'tournament.joining': 'Joining...',
        'tournament.youreParticipating': 'You\'re participating!',
        'tournament.yourRank': 'Your Rank',
        'tournament.yourRoi': 'Your ROI',
        'tournament.yourPnl': 'Your PnL',
        'tournament.liveLeaderboard': 'Live Leaderboard',
        'tournament.realTime': 'Real-time',
        'tournament.rank': 'Rank',
        'tournament.roi': 'ROI',
        'tournament.pnl': 'PnL',
        'tournament.noParticipants': 'No participants yet. Be the first to join!',
        'tournament.noActiveTournament': 'No Active Tournament',
        'tournament.noActiveTournamentDesc': 'The next weekly tournament is being prepared. Check back soon or register to get notified when it starts!',
        'tournament.createAccount': 'Create Account',
        
        // Governance page
        'governance.title': 'Governance',
        'governance.subtitle': 'Shape the future of MIMIC. Elite members vote on new trading pairs, risk management changes, and exchange integrations.',
        'governance.checkingEligibility': 'Checking eligibility...',
        'governance.pleaseWait': 'Please wait while we verify your voting status.',
        'governance.loginRequired': 'Login Required',
        'governance.signInToSee': 'Sign in to see your voting eligibility.',
        'governance.youCanVote': 'You Can Vote!',
        'governance.eliteVoting': 'As an Elite member, your vote helps shape MIMIC\'s future.',
        'governance.votingLocked': 'Voting Locked',
        'governance.reachElite': 'Reach Elite level to unlock voting privileges.',
        'governance.active': 'Active',
        'governance.passed': 'Passed',
        'governance.rejected': 'Rejected',
        'governance.implemented': 'Implemented',
        'governance.newTradingPair': 'New Trading Pair',
        'governance.riskManagement': 'Risk Management',
        'governance.newExchange': 'New Exchange',
        'governance.featureRequest': 'Feature Request',
        'governance.other': 'Other',
        'governance.eliteOnly': 'Elite Only',
        'governance.yes': 'Yes',
        'governance.no': 'No',
        'governance.youVoted': 'You voted:',
        'governance.votes': 'votes',
        'governance.toPass': 'to pass',
        'governance.votingEnded': 'Voting ended',
        'governance.left': 'left',
        'governance.noProposals': 'No Proposals',
        'governance.noProposalsDesc': 'There are no proposals at this time.',
        'governance.createProposal': 'Create Proposal',
        'governance.proposalTitle': 'Proposal Title',
        'governance.description': 'Description',
        'governance.category': 'Category',
        'governance.votingDuration': 'Voting Duration (Days)',
        'governance.minVotesRequired': 'Min Votes Required',
        'governance.passThreshold': 'Pass Threshold (%)',
        'governance.cancel': 'Cancel',
        'governance.voteRecorded': 'Vote recorded',
        'governance.proposalCreated': 'Proposal created successfully!',
        
        // Index/Home extras
        'home.viewLeaderboard': 'View Leaderboard',
        'home.safetyPool': 'Safety Pool',
        'home.mirrorTraders247': 'Mirror Professional Traders 24/7',
        
        // Admin Dashboard
        'admin.title': 'Admin Panel',
        'admin.insuranceFund': 'Insurance Fund',
        'admin.verified': 'Verified',
        'admin.safetyPool': 'Safety Pool',
        'admin.feesToFund': '5% of fees → fund',
        'admin.slippageProtection': 'Slippage protection',
        'admin.tournaments': 'Tournaments',
        'admin.createManage': 'Create & manage',
        'admin.topTraders': 'Top traders',
        'admin.proposalsVotes': 'Proposals & votes',
        'admin.referralPayouts': 'Referral payouts',
        'admin.totalReferrals': 'Total Referrals',
        'admin.premiumUsers': 'Premium Users',
        'admin.pendingPayouts': 'Pending Payouts',
        'admin.platformRevenue': 'Platform Revenue',
        'admin.loadingExchangeBalances': 'Loading exchange balances...',
        'admin.connectedNodes': 'Connected Nodes',
        'admin.activePositions': 'Active Positions',
        'admin.systemLogs': 'System Logs',
        'admin.recentActivity': 'Recent Activity',
        'admin.noLogs': 'No logs available',
        'admin.user': 'User',
        'admin.balance': 'Balance',
        'admin.status': 'Status',
        'admin.actions': 'Actions',
        'admin.active': 'Active',
        'admin.paused': 'Paused',
        'admin.pause': 'Pause',
        'admin.resume': 'Resume',
        'admin.noNodes': 'No connected nodes',
        'admin.symbol': 'Symbol',
        'admin.side': 'Side',
        'admin.size': 'Size',
        'admin.entryPrice': 'Entry Price',
        'admin.pnl': 'PnL',
        'admin.noPositions': 'No active positions',
        'admin.masterExchanges': 'Master Exchanges',
        'admin.addMasterExchange': 'Add Master Exchange',
        'admin.userExchanges': 'User Exchanges',
        'admin.noExchanges': 'No exchanges connected',
        'admin.globalSettings': 'Global Settings',
        'admin.maxPositions': 'Max Positions',
        'admin.riskLevel': 'Risk Level',
        'admin.saveSettings': 'Save Settings',
        'admin.tradeHistory': 'Trade History',
        'admin.openPositions': 'Open Positions',
        'admin.closedTrades': 'Closed Trades',
        'admin.time': 'Time',
        'admin.type': 'Type',
        'admin.entry': 'Entry',
        'admin.exit': 'Exit',
        'admin.noTrades': 'No trades yet',
        'admin.testnet': 'Testnet',
        'admin.mainnet': 'Mainnet',
        'admin.apiKey': 'API Key',
        'admin.apiSecret': 'API Secret',
        'admin.connect': 'Connect',
        'admin.disconnect': 'Disconnect',
        'admin.exchangeConnected': 'Exchange connected successfully',
        'admin.exchangeDisconnected': 'Exchange disconnected',
        'admin.copyAll': 'Copy All',
        'admin.pauseAll': 'Pause All',
        'admin.resumeAll': 'Resume All',
        'admin.broadcast': 'Broadcast',
        'admin.sendNotification': 'Send Notification',
        'admin.notificationSent': 'Notification sent to all users',
        'admin.services': 'Services',
        'admin.serviceSettings': 'Service Settings',
        'admin.telegramBot': 'Telegram Bot',
        'admin.emailSmtp': 'Email/SMTP',
        'admin.plisioPayments': 'Plisio Payments',
        'admin.twitterX': 'Twitter/X',
        'admin.openaiSupport': 'OpenAI (Support Bot)',
        'admin.webPush': 'Web Push',
        'admin.enabled': 'Enabled',
        'admin.disabled': 'Disabled',
        'admin.configure': 'Configure',
        'admin.activeTournament': 'Active Tournament',
        
        // User Dashboard
        'user.title': 'Terminal',
        'user.portfolio': 'Portfolio',
        'user.totalBalance': 'Total Balance',
        'user.todayPnl': 'Today PnL',
        'user.allTimePnl': 'All-time PnL',
        'user.copyingActive': 'Copying Active',
        'user.copyingStopped': 'Copying Stopped',
        'user.startCopying': 'Start Copying',
        'user.stopCopying': 'Stop Copying',
        'user.myPositions': 'My Positions',
        'user.myTrades': 'My Trades',
        'user.noPositions': 'No positions open',
        'user.noTrades': 'No trades yet',
        'user.connectExchange': 'Connect Exchange',
        'user.exchangeSettings': 'Exchange Settings',
        'user.riskSettings': 'Risk Settings',
        'user.maxPositionSize': 'Max Position Size',
        'user.stopLoss': 'Stop Loss',
        'user.takeProfit': 'Take Profit',
        'user.notifications': 'Notifications',
        'user.telegramAlerts': 'Telegram Alerts',
        'user.emailAlerts': 'Email Alerts',
        'user.pushAlerts': 'Push Alerts',
        'user.referralProgram': 'Referral Program',
        'user.yourReferralCode': 'Your Referral Code',
        'user.referralEarnings': 'Referral Earnings',
        'user.totalReferred': 'Total Referred',
        'user.copyCode': 'Copy Code',
        'user.copied': 'Copied!',
        'user.subscription': 'Subscription',
        'user.currentPlan': 'Current Plan',
        'user.freePlan': 'Free Plan',
        'user.proPlan': 'Pro Plan',
        'user.elitePlan': 'Elite Plan',
        'user.upgradePlan': 'Upgrade Plan',
        'user.analytics': 'Analytics',
        'user.performance': 'Performance',
        'user.weeklyReport': 'Weekly Report',
        'user.monthlyReport': 'Monthly Report',
        'user.connections': 'Connections',
        'user.config': 'Config',
        'user.terminal': 'Terminal'
    },
    ua: {
        // Navigation
        'nav.dashboard': 'Панель',
        'nav.messages': 'Повідомлення',
        'nav.settings': 'Налаштування',
        'nav.changePassword': 'Безпека',
        'nav.logout': 'Вийти',
        'nav.login': 'Увійти',
        'nav.register': 'Реєстрація',
        'nav.copyTrading': 'Копі Трейдинг',
        'nav.connected': 'Підключено',
        
        // Sections
        'section.overview': 'Огляд',
        'section.trading': 'Торгівля',
        'section.positions': 'Позиції',
        'section.history': 'Історія',
        'section.stats': 'Статистика',
        'section.exchange': 'Біржа',
        'section.settings': 'Налаштування',
        'section.users': 'Користувачі',
        'section.controls': 'Управління',
        'section.telegram': 'Telegram',
        
        // Dashboard
        'dash.master': 'ГОЛОВНИЙ',
        'dash.live': 'ONLINE',
        'dash.nodes': 'Вузли',
        'dash.trades': 'Угоди',
        'dash.masterPositions': 'Головні позиції',
        'dash.openPositions': 'Відкриті позиції',
        'dash.tradeHistory': 'Історія угод',
        'dash.connectedExchanges': 'Підключені біржі',
        'dash.addExchange': 'Додати біржу',
        'dash.selectExchange': 'Виберіть біржу...',
        'dash.accountLabel': 'Назва акаунту (необов\'язково)',
        'dash.apiKey': 'API Ключ',
        'dash.apiSecret': 'API Секрет',
        'dash.passphrase': 'Парольна фраза',
        'dash.submitRequest': 'Відправити запит',
        'dash.telegramNotifications': 'Telegram сповіщення',
        'dash.enabled': 'Увімкнено',
        'dash.disabled': 'Вимкнено',
        'dash.enableNotifications': 'Увімкнути сповіщення',
        'dash.save': 'Зберегти',
        'dash.email': 'Електронна пошта',
        'dash.set': 'Встановлено',
        'dash.notSet': 'Не встановлено',
        'dash.targetGoal': 'Цільова мета',
        'dash.targetAmount': 'Сума цілі',
        'dash.profileAvatar': 'Аватар профілю',
        'dash.change': 'Змінити',
        'dash.changePassword': 'Змінити пароль',
        'dash.securitySettings': 'Налаштування безпеки',
        'dash.noOpenPositions': 'Немає відкритих позицій',
        'dash.noHistory': 'Історія порожня',
        'dash.loadingExchanges': 'Завантаження бірж...',
        'dash.noExchanges': 'Немає підключених бірж',
        'dash.chooseAvatar': 'Виберіть аватар',
        'dash.saveAvatar': 'Зберегти аватар',
        'dash.growthDynamics': 'Динаміка зростання',
        'dash.tradingParameters': 'Торгові параметри',
        'dash.takeProfit': 'Тейк-профіт',
        'dash.stopLoss': 'Стоп-лос',
        'dash.result': 'Результат',
        'dash.winRate': 'Вінрейт',
        'dash.avgRoi': 'Середній ROI',
        'dash.emergencyExit': 'Аварійний вихід',
        'dash.risk': 'Ризик',
        'dash.leverage': 'Кредитне плече',
        'dash.totalTrades': 'Всього угод',
        'dash.auto': 'АВТО',
        'dash.tradingParams': 'Торгові параметри',
        'dash.setByAdmin': 'Встановлено адміном',
        'dash.riskPercent': 'Ризик %',
        'dash.leverageX': 'Плече',
        'dash.maxPositions': 'Макс. позицій',
        'dash.minBalance': 'Мін. баланс',
        'dash.tradingParamsInfo': 'Ці параметри налаштовані адміністратором і застосовуються до всіх угод.',
        'dash.changeAvatar': 'Змінити аватар',
        'dash.chooseEmoji': 'Виберіть емодзі',
        'dash.orUploadImage': 'Або завантажте зображення',
        'dash.avatarInfo': 'Виберіть емодзі або завантажте зображення',
        
        // Admin
        'admin.liveLogs': 'Живі логи',
        'admin.clearLogs': 'Очистити',
        'admin.waitingSignals': 'Очікування сигналів...',
        'admin.growth': 'Зростання',
        'admin.masterPositions': 'Головні позиції',
        'admin.exchangeConfig': 'Конфігурація бірж',
        'admin.userExchanges': 'Біржі користувачів',
        'admin.pendingExchanges': 'Очікуючі біржі',
        'admin.networkNodes': 'Мережеві вузли',
        'admin.closedTrades': 'Закриті угоди',
        'admin.controlTerminal': 'Термінал управління',
        'admin.globalSettings': 'Глобальні налаштування',
        'admin.adminSettings': 'Налаштування адміна',
        'admin.terminal': 'Термінал',
        'admin.connectExchangeHint': 'Спочатку підключіть біржі з вашими адмін API ключами. Потім користувачі зможуть додати свої ключі.',
        'admin.tableUser': 'Користувач',
        'admin.tableStatus': 'Статус',
        'admin.tableBalance': 'Баланс',
        'admin.tableActions': 'Дії',
        'admin.tableTime': 'Час',
        'admin.tableNode': 'Вузол',
        'admin.tableSymbol': 'Символ',
        'admin.tableSide': 'Сторона',
        'admin.tablePnl': 'PnL',
        'dash.loading': 'Завантаження...',
        
        // Buttons
        'btn.save': 'Зберегти',
        'btn.cancel': 'Скасувати',
        'btn.submit': 'Відправити',
        'btn.close': 'Закрити',
        'btn.delete': 'Видалити',
        'btn.edit': 'Редагувати',
        'btn.add': 'Додати',
        'btn.start': 'Запустити',
        'btn.stop': 'Зупинити',
        'btn.pause': 'Пауза',
        'btn.reload': 'Перезавантажити',
        'btn.panic': 'Паніка',
        'btn.send': 'Надіслати',
        
        // Status
        'status.online': 'Онлайн',
        'status.offline': 'Офлайн',
        'status.active': 'Активний',
        'status.inactive': 'Неактивний',
        'status.pending': 'Очікування',
        'status.approved': 'Схвалено',
        'status.rejected': 'Відхилено',
        'status.trading': 'Торгівля',
        'status.ready': 'Готово',
        'status.awaiting': 'Очікування',
        
        // Common
        'common.loading': 'Завантаження...',
        'common.error': 'Помилка',
        'common.success': 'Успіх',
        'common.confirm': 'Підтвердити',
        'common.yes': 'Так',
        'common.no': 'Ні',
        'common.close': 'Закрити',
        'common.back': 'Назад',
        'common.next': 'Далі',
        'common.previous': 'Назад',
        
        // Auth
        'auth.welcomeBack': 'З поверненням',
        'auth.signInToMimic': 'Увійдіть до свого облікового запису MIMIC',
        'auth.systemReady': 'СИСТЕМА ГОТОВА',
        'auth.usernamePhone': 'Ім\'я користувача / Телефон',
        'auth.password': 'Пароль',
        'auth.rememberMe': 'Запам\'ятати мене',
        'auth.forgotPassword': 'Забули пароль?',
        'auth.dontHaveAccount': 'Немає облікового запису?',
        'auth.getStarted': 'Почніть',
        'auth.signIn': 'Увійти',
        'auth.sslTls': 'SSL/TLS',
        'auth.encrypted': 'Зашифровано',
        'auth.secure': 'Безпечно',
        'auth.startMimicking': 'Почніть копіювати найкращих трейдерів',
        'auth.stepProfile': 'Профіль',
        'auth.stepSecurity': 'Безпека',
        'auth.stepApi': 'API',
        'auth.firstName': 'Ім\'я',
        'auth.lastName': 'Прізвище',
        'auth.phone': 'Телефон (Ім\'я користувача)',
        'auth.email': 'Електронна пошта (для відновлення)',
        'auth.emailRecommended': 'Рекомендовано для відновлення облікового запису',
        'auth.minChars': 'Мінімум 6 символів',
        'auth.exchangeApi': 'API біржі',
        'auth.selectExchange': 'Виберіть біржу',
        'auth.chooseExchange': '-- Виберіть вашу біржу --',
        'auth.noExchange': 'Немає облікового запису на біржі?',
        'auth.createPartner': 'Спочатку зареєструйтеся на обраній біржі',
        'auth.registerExchange': 'Зареєструватися',
        'auth.apiKey': 'API Ключ',
        'auth.apiSecret': 'API Секрет',
        'auth.passphrase': 'Парольна фраза',
        'auth.passphraseRequired': 'Ця біржа вимагає парольну фразу',
        'auth.enterUsername': 'Введіть ім\'я користувача...',
        'auth.enterPassword': '••••••••',
        'auth.firstNamePlaceholder': 'Іван',
        'auth.lastNamePlaceholder': 'Петренко',
        'auth.phonePlaceholder': '+380 XX XXX XXXX',
        'auth.emailPlaceholder': 'ваш@email.com',
        'auth.apiKeyPlaceholder': 'Ваш API ключ біржі',
        'auth.apiSecretPlaceholder': 'Секретний ключ',
        'auth.passphrasePlaceholder': 'API пароль (обов\'язковий для цієї біржі)',
        'auth.repeatPassword': 'Повторіть пароль',
        'auth.securityTips': 'Важливі поради з безпеки:',
        'auth.enableFutures': 'Увімкніть дозволи на Ф\'ючерсну торгівлю',
        'auth.disableWithdrawals': 'Вимкніть Виведення коштів',
        'auth.enableIpWhitelist': 'Увімкніть Білий список IP для безпеки',
        'auth.howItWorks': 'Як це працює:',
        'auth.step1': 'Ваші API ключі будуть перевірені',
        'auth.step2': 'Ваш запит буде відправлено адміністратору',
        'auth.step3': 'Адмін вирішить, чи починати торгівлю',
        'auth.agreeTerms': 'Я погоджуюся з умовами використання та розумію ризики, пов\'язані з ф\'ючерсною торгівлею криптовалютами',
        'auth.haveAccount': 'Вже є обліковий запис?',
        'auth.weakPassword': 'Слабкий пароль',
        'auth.mediumPassword': 'Нормальний пароль',
        'auth.strongPassword': 'Сильний пароль! 💪',
        
        // Home page
        'home.automatedCopyTrading': 'Автоматизована платформа копі-трейдингу',
        'home.tradeLikeTheBest': 'Торгуйте як найкращі',
        'home.subtitle': 'Підключіть API вашої біржі та автоматично копіюйте угоди професійних трейдерів. Без ручного втручання — повністю автоматизований прибуток.',
        'home.startTradingNow': 'Почніть торгувати зараз',
        'home.signIn': 'Увійти',
        'home.automatedTrading': 'Автоматизована торгівля',
        'home.signalLatency': 'Затримка сигналу',
        'home.transparency': 'Прозорість',
        'home.coreFeatures': 'Основні функції',
        'home.whyChooseMimic': 'Чому обирати MIMIC?',
        'home.whyChooseSubtitle': 'Професійний копі-трейдинг з передовою технологією та нульовим компромісом щодо безпеки.',
        'home.lightningFast': 'Блискавична швидкість',
        'home.lightningFastDesc': 'Виконання угод за частки секунди гарантує, що ви ніколи не пропустите можливість. Наша система копіює угоди в реальному часі з мінімальною затримкою.',
        'home.maximumSecurity': 'Максимальна безпека',
        'home.maximumSecurityDesc': 'Ваші API ключі зашифровані та зберігаються безпечно. Ми ніколи не маємо дозволів на виведення — ваші кошти завжди під вашим контролем.',
        'home.realTimeAnalytics': 'Аналітика в реальному часі',
        'home.realTimeAnalyticsDesc': 'Відстежуйте продуктивність свого портфеля з детальною статистикою, історією угод та графіками зростання — все в одній панелі.',
        'home.customizableRisk': 'Налаштовуваний ризик',
        'home.customizableRiskDesc': 'Встановіть власні параметри ризику, обмеження кредитного плеча та розміри позицій. Торгуйте впевнено з налаштуваннями, що відповідають вашій стратегії.',
        'home.instantNotifications': 'Миттєві сповіщення',
        'home.instantNotificationsDesc': 'Отримуйте сповіщення Telegram для кожної угоди, оновлення позиції та важливих системних подій. Будьте в курсі 24/7.',
        'home.directSupport': 'Пряма підтримка',
        'home.directSupportDesc': 'Вбудована система повідомлень для прямого спілкування з адміністраторами. Отримайте допомогу, коли вона потрібна, без сторонніх квитків.',
        'home.gettingStarted': 'Початок роботи',
        'home.howItWorks': 'Як це працює',
        'home.howItWorksSubtitle': 'Почніть копі-трейдинг у три прості кроки. Складна настройка не потрібна.',
        'home.createAccount': 'Створіть свій обліковий запис',
        'home.createAccountDesc': 'Зареєструйтеся з номером телефону та підключіть обліковий запис біржі, використовуючи API ключі. Ми підтримуємо основні біржі, включаючи Binance, Bybit, OKX та інші.',
        'home.waitApproval': 'Очікуйте схвалення',
        'home.waitApprovalDesc': 'Наша команда перевіряє ваші API ключі та налаштування облікового запису. Після схвалення ваш обліковий запис буде активовано та готовий до автоматизованої торгівлі.',
        'home.startMimicking': 'Почніть копіювати',
        'home.startMimickingDesc': 'Після активації ваш обліковий запис автоматично копіює позиції головного трейдера. Відкиньтеся назад і спостерігайте, як ваш портфель зростає з професійними угодами.',
        'home.supportedExchanges': 'Підтримувані біржі',
        'home.tradeOnTopExchanges': 'Торгуйте на топових біржах',
        'home.tradeOnTopExchangesSubtitle': 'Підключіть улюблену біржу та почніть копі-трейдинг миттєво.',
        'home.available': 'Доступна',
        'home.readyToStart': 'Готові почати копіювати?',
        'home.readyToStartSubtitle': 'Приєднуйтеся зараз і дозвольте професійним трейдерам працювати на вас. Ваша подорож до автоматизованого прибутку починається тут.',
        'home.createFreeAccount': 'Створити безкоштовний обліковий запис',
        
        // Additional dashboard
        'dash.target': 'Ціль',
        'dash.statistics': 'Статистика',
        'dash.messages': 'Повідомлення',
        'dash.clickChange': 'Натисніть "Змінити", щоб вибрати новий аватар',
        'dash.trades': 'угод',
        'dash.users': 'користувачів',
        'dash.live': 'Онлайн',
        'dash.pending': 'Очікування',
        'dash.active': 'Активний',
        
        // Additional admin
        'admin.verifiedExchanges': 'Перевірені біржі',
        'admin.nodeSettings': 'Налаштування вузла',
        'admin.updateCredentials': 'Оновити облікові дані',
        'admin.connectExchange': 'Підключити біржу (Адмін)',
        'admin.addExchange': 'Додати біржу',
        'admin.connectWithAdminKeys': 'Підключіть з ВАШИМИ адмін API ключами. Після перевірки користувачі зможуть додати свої ключі до цієї біржі.',
        'admin.exchange': 'Біржа',
        'admin.adminApiKey': 'Адмін API Ключ',
        'admin.adminApiSecret': 'Адмін API Секрет',
        'admin.verifyConnect': 'Перевірити та підключити',
        'admin.alreadyVerified': 'Вже перевірено!',
        'admin.reverifyKeys': 'Ви можете повторно перевірити з новими API ключами, якщо потрібно.',
        'admin.notConnectedYet': 'Ще не підключено',
        'admin.enterAdminKeys': 'Введіть свої адмін API ключі для перевірки цієї біржі.',
        'admin.start': 'ЗАПУСТИТИ',
        'admin.pause': 'ПАУЗА',
        'admin.reload': 'ПЕРЕЗАВАНТАЖИТИ',
        'admin.tradingPaused': 'ТОРГІВЛЯ ПРИЗУПИНЕНА',
        'admin.closeAllPositions': 'Закрити ВСІ позиції на ВСІХ облікових записах?',
        'admin.irreversible': 'Це НЕЗВОРОТНО!',
        'admin.executingPanic': 'Виконання аварійного виходу...',
        'admin.closed': 'Закрито',
        'admin.master': 'Головний',
        'admin.slaves': 'Підлеглі',
        'admin.deleteExchange': 'Видалити цю біржу?',
        'admin.disconnectExchange': 'Відключити',
        'admin.disconnectConfirm': 'Відключити',
        'admin.disconnectConfirmText': 'Це також вимкне її для всіх користувачів.',
        'admin.rejectExchange': 'Відхилити цю біржу?',
        'admin.upload': 'Завантажити',
        'admin.emoji': 'Емодзі',
        'admin.photo': 'Фото',
        'admin.selectMax2mb': 'Натисніть, щоб вибрати (макс. 2 МБ)',
        'admin.avatar': 'Аватар',
        'admin.settingsFor': 'Налаштування для:',
        'admin.newUsername': 'Нове ім\'я користувача',
        'admin.newPassword': 'Новий пароль',
        'admin.selectExchange': 'Виберіть біржу...',
        'admin.logsCleared': 'Логи очищено',
        
        // Additional status
        'status.long': 'ДОВГА',
        'status.short': 'КОРОТКА',
        
        // Additional buttons
        'btn.signIn': 'Увійти',
        'btn.startMimicking': 'Почніть копіювати',
        'btn.upload': 'Завантажити',
        'btn.updateCredentials': 'Оновити облікові дані',
        
        // Disclaimer
        'disclaimer.title': 'Застереження про ризики',
        'disclaimer.acknowledged': 'ОБОВ\'ЯЗКОВО',
        'disclaimer.mainText': 'УВАГА: Торгівля криптовалютами та ф\'ючерсами пов\'язана зі ЗНАЧНИМ РИЗИКОМ. Волатильність крипторинків означає, що ціни можуть змінюватися швидко та непередбачувано. Копі-трейдинг НЕ усуває ризик — ви несете відповідальність за власні інвестиційні рішення. Ніколи не інвестуйте більше, ніж можете дозволити собі втратити. Минулі результати НЕ гарантують майбутніх прибутків.',
        'disclaimer.point1': 'Торгівля криптовалютами пов\'язана зі значним ризиком втрат і підходить не кожному інвестору.',
        'disclaimer.point2': 'Минулі результати не гарантують майбутніх прибутків. Ви можете втратити всю інвестицію.',
        'disclaimer.point3': 'Інвестуйте лише те, що можете дозволити собі втратити. Це не є фінансовою порадою.',
        'disclaimer.point4': 'Кредитне плече посилює як прибутки, так і збитки. Будьте вкрай обережні з позиціями з плечем.',
        
        // Change Password page
        'auth.changePassword': 'Змінити пароль',
        'auth.enterPasswordInfo': 'Оновіть облікові дані безпеки вашого акаунту',
        'auth.secureSession': 'БЕЗПЕЧНА СЕСІЯ',
        'auth.currentPassword': 'Поточний пароль',
        'auth.newPassword': 'Новий пароль',
        'auth.enterCurrentPassword': 'Введіть поточний пароль',
        'auth.passwordRequirements': 'Мін. 8 символів, великі, малі літери, цифра',
        'btn.saveChanges': 'Зберегти зміни',
        'nav.backToDashboard': 'Назад до панелі',
        'security.encrypted': 'Зашифровано',
        'security.secure': 'Безпечно',
        
        // Forgot Password page
        'auth.resetPassword': 'Скинути пароль',
        'auth.chooseMethod': 'Виберіть спосіб отримання коду підтвердження',
        'auth.identifier': 'Email, телефон або ім\'я користувача',
        'auth.identifierPlaceholder': 'user@email.com або ім\'я',
        'auth.selectMethod': 'Виберіть спосіб',
        'auth.receiveEmail': 'Отримати код на email',
        'auth.receiveTelegram': 'Отримати код у чаті',
        'auth.notConfigured': 'Не налаштовано',
        'auth.unavailable': 'Скидання паролю недоступне',
        'auth.noMethodsConfigured': 'Email та Telegram не налаштовані. Зверніться до адміністратора для скидання паролю.',
        'auth.emailRequired': 'Потрібен прив\'язаний email',
        'auth.telegramWorks': 'Працює, якщо сповіщення увімкнені',
        'btn.sendCode': 'Надіслати код',
        'auth.backToSignIn': 'Назад до входу',
        'auth.cantReset': 'Не можете скинути пароль?',
        'auth.contactSupport': 'Зверніться до адміністратора через підтримку для допомоги.',
        
        // Reset Password page
        'auth.newPasswordTitle': 'Новий пароль',
        'auth.enterCodeAndPassword': 'Введіть код підтвердження та новий пароль',
        'auth.codeSentTo': 'Код надіслано на',
        'auth.codeSentTelegram': 'Код надіслано в Telegram',
        'auth.confirmationCode': 'Код підтвердження',
        'auth.confirmPassword': 'Підтвердіть пароль',
        'auth.passwordsDontMatch': 'Паролі не співпадають',
        'auth.changePasswordBtn': 'Змінити пароль',
        'auth.didntReceiveCode': 'Не отримали код?',
        'auth.resendCode': 'Надіслати ще раз',
        'auth.tryAnotherMethod': 'Спробувати інший спосіб',
        
        // Notifications
        'notify.email': 'Email',
        'notify.telegram': 'Telegram',
        
        // Messages
        'messages.newMessage': 'Нове повідомлення',
        'messages.subject': 'Тема',
        'messages.enterSubject': 'Введіть тему повідомлення',
        'messages.content': 'Повідомлення',
        'messages.message': 'Повідомлення',
        'messages.enterMessage': 'Опишіть ваше питання або проблему...',
        'messages.enterMessageText': 'Введіть текст повідомлення...',
        'messages.enterReply': 'Введіть вашу відповідь...',
        'messages.send': 'Надіслати',
        'messages.reply': 'Відповісти',
        'messages.inbox': 'Вхідні',
        'messages.sent': 'Надіслані',
        'messages.noMessages': 'Повідомлень ще немає',
        'messages.compose': 'Написати',
        'messages.myMessages': 'Мої повідомлення',
        'messages.writeAdmin': 'Напишіть адміністратору, щоб отримати допомогу',
        'messages.writeToAdmin': 'Написати адміну',
        'messages.writeToUser': 'Написати користувачу',
        'messages.maxChars': 'Максимум 2000 символів',
        'messages.replies': 'відповідей',
        'messages.messageCenter': 'Центр повідомлень',
        'messages.total': 'Всього',
        'messages.new': 'Нові',
        'messages.handled': 'Оброблено',
        'messages.repliesCount': 'Відповіді',
        'messages.userRequests': 'Запити користувачів',
        'messages.all': 'Всі',
        'messages.unread': 'Непрочитані',
        'messages.awaitingReply': 'Очікує відповіді',
        'messages.noRequests': 'Немає запитів',
        'messages.userMessagesAppear': 'Повідомлення користувачів з\'являться тут',
        'messages.recipient': 'Отримувач',
        'messages.selectUser': 'Виберіть користувача...',
        
        // Dashboard extras
        'dash.telegramChatId': 'Telegram Chat ID',
        'dash.emailPlaceholder': 'ваш@email.com',
        'dash.periodPnl': 'PnL за період',
        'dash.scanningPositions': 'Сканування позицій...',
        'dash.loadingConnections': 'Завантаження підключень...',
        'dash.enableNotifications': 'Увімкнути сповіщення',
        
        // Footer
        'footer.platform': 'Платформа',
        'footer.home': 'Головна',
        'footer.signIn': 'Увійти',
        'footer.getStarted': 'Почати',
        'footer.exchanges': 'Біржі',
        'footer.features': 'Функції',
        'footer.copyTrading': 'Копі-трейдинг',
        'footer.realTimeMirroring': 'Копіювання в реальному часі',
        'footer.riskManagement': 'Управління ризиками',
        'footer.telegramAlerts': 'Сповіщення Telegram',
        'footer.desc': 'Автоматизована платформа копі-трейдингу нового покоління. Копіюйте професійних трейдерів в реальному часі.',
        'footer.trading': 'Торгівля',
        'footer.latency': 'Затримка',
        'footer.automated': 'Автоматизовано',
        'footer.rights': 'Всі права захищені.',
        'footer.warning': 'Торгівля пов\'язана з ризиком. Не є фінансовою порадою.',
        
        // Navigation extras
        'nav.community': 'Спільнота',
        'nav.account': 'Обліковий запис',
        'nav.admin': 'Адмін',
        'nav.leaderboard': 'Рейтинг',
        'nav.tournaments': 'Турніри',
        'nav.governance': 'Голосування',
        'nav.apiKeys': 'API Ключі',
        'nav.payouts': 'Виплати',
        
        // Leaderboard page
        'leaderboard.title': 'Рейтинг',
        'leaderboard.subtitle': 'Відстеження продуктивності наших топ-трейдерів у реальному часі. Дізнайтеся, хто лідирує.',
        'leaderboard.totalUsers': 'Всього користувачів',
        'leaderboard.totalVolume': 'Загальний обсяг',
        'leaderboard.totalProfit': 'Загальний прибуток',
        'leaderboard.totalTrades': 'Всього угод',
        'leaderboard.topCopiers': 'Топ копіювальників',
        'leaderboard.today': 'Сьогодні',
        'leaderboard.trader': 'Трейдер',
        'leaderboard.trades': 'Угоди',
        'leaderboard.masterTrader': 'Головний трейдер',
        'leaderboard.30DayPerformance': 'Результати за 30 днів',
        'leaderboard.totalPnl': 'Загальний PnL',
        'leaderboard.winRate': 'Відсоток перемог',
        'leaderboard.readyToJoin': 'Готові приєднатися до переможців?',
        'leaderboard.readyToJoinSubtitle': 'Почніть копі-трейдинг сьогодні та автоматично копіюйте угоди наших найкращих трейдерів. Досвід не потрібен.',
        'leaderboard.copyNow': 'Копіювати — Почати безкоштовно',
        'leaderboard.loadingLeaderboard': 'Завантаження рейтингу...',
        'leaderboard.noActivity': 'Ще немає торгової активності. Будьте першим!',
        'leaderboard.failedToLoad': 'Не вдалося завантажити дані. Спробуйте ще раз.',
        'leaderboard.noBalanceHistory': 'Історія балансу недоступна',
        
        // Tournament page
        'tournament.title': 'Щотижневий турнір',
        'tournament.subtitle': 'Змагайтеся з трейдерами з усього світу. Приєднуйтесь за $10, торгуйте на максимум і виграйте частину призового фонду. ТОП-3 за ROI забирають все!',
        'tournament.endsIn': 'Турнір закінчується через',
        'tournament.startsIn': 'Турнір починається через',
        'tournament.ended': 'Турнір завершено',
        'tournament.days': 'Днів',
        'tournament.hours': 'Годин',
        'tournament.minutes': 'Хвилин',
        'tournament.seconds': 'Секунд',
        'tournament.live': 'LIVE - Торгівля активна',
        'tournament.registrationOpen': 'Реєстрація відкрита',
        'tournament.calculatingResults': 'Підрахунок результатів...',
        'tournament.prizePool': 'Призовий фонд',
        'tournament.participants': 'Учасники',
        'tournament.entryFee': 'Вступний внесок',
        'tournament.topRoi': 'Топ ROI',
        'tournament.prizeDistribution': 'Розподіл призів',
        'tournament.1stPlace': '1 місце',
        'tournament.2ndPlace': '2 місце',
        'tournament.3rdPlace': '3 місце',
        'tournament.loginToJoin': 'Увійти для участі',
        'tournament.joinFor': 'Приєднатися за',
        'tournament.registrationClosed': 'Реєстрацію закрито',
        'tournament.joining': 'Приєднання...',
        'tournament.youreParticipating': 'Ви берете участь!',
        'tournament.yourRank': 'Ваш рейтинг',
        'tournament.yourRoi': 'Ваш ROI',
        'tournament.yourPnl': 'Ваш PnL',
        'tournament.liveLeaderboard': 'Рейтинг у реальному часі',
        'tournament.realTime': 'Реальний час',
        'tournament.rank': 'Ранг',
        'tournament.roi': 'ROI',
        'tournament.pnl': 'PnL',
        'tournament.noParticipants': 'Ще немає учасників. Будьте першим!',
        'tournament.noActiveTournament': 'Немає активного турніру',
        'tournament.noActiveTournamentDesc': 'Наступний щотижневий турнір готується. Перевірте пізніше або зареєструйтеся, щоб отримати сповіщення про старт!',
        'tournament.createAccount': 'Створити обліковий запис',
        
        // Governance page
        'governance.title': 'Голосування',
        'governance.subtitle': 'Формуйте майбутнє MIMIC. Елітні учасники голосують за нові торгові пари, зміни в управлінні ризиками та інтеграції бірж.',
        'governance.checkingEligibility': 'Перевірка права голосу...',
        'governance.pleaseWait': 'Будь ласка, зачекайте, поки ми перевіряємо ваш статус.',
        'governance.loginRequired': 'Потрібен вхід',
        'governance.signInToSee': 'Увійдіть, щоб побачити право голосу.',
        'governance.youCanVote': 'Ви можете голосувати!',
        'governance.eliteVoting': 'Як Елітний учасник, ваш голос допомагає формувати майбутнє MIMIC.',
        'governance.votingLocked': 'Голосування заблоковано',
        'governance.reachElite': 'Досягніть Елітного рівня, щоб розблокувати право голосу.',
        'governance.active': 'Активні',
        'governance.passed': 'Схвалено',
        'governance.rejected': 'Відхилено',
        'governance.implemented': 'Впроваджено',
        'governance.newTradingPair': 'Нова торгова пара',
        'governance.riskManagement': 'Управління ризиками',
        'governance.newExchange': 'Нова біржа',
        'governance.featureRequest': 'Запит функції',
        'governance.other': 'Інше',
        'governance.eliteOnly': 'Тільки для Еліти',
        'governance.yes': 'Так',
        'governance.no': 'Ні',
        'governance.youVoted': 'Ви проголосували:',
        'governance.votes': 'голосів',
        'governance.toPass': 'для схвалення',
        'governance.votingEnded': 'Голосування завершено',
        'governance.left': 'залишилось',
        'governance.noProposals': 'Немає пропозицій',
        'governance.noProposalsDesc': 'На даний момент немає пропозицій.',
        'governance.createProposal': 'Створити пропозицію',
        'governance.proposalTitle': 'Назва пропозиції',
        'governance.description': 'Опис',
        'governance.category': 'Категорія',
        'governance.votingDuration': 'Тривалість голосування (днів)',
        'governance.minVotesRequired': 'Мін. голосів',
        'governance.passThreshold': 'Поріг схвалення (%)',
        'governance.cancel': 'Скасувати',
        'governance.voteRecorded': 'Голос зараховано',
        'governance.proposalCreated': 'Пропозицію успішно створено!',
        
        // Index/Home extras
        'home.viewLeaderboard': 'Переглянути рейтинг',
        'home.safetyPool': 'Страховий пул',
        'home.mirrorTraders247': 'Копіюйте професійних трейдерів 24/7',
        
        // Admin Dashboard
        'admin.title': 'Панель адміністратора',
        'admin.insuranceFund': 'Страховий фонд',
        'admin.verified': 'Підтверджено',
        'admin.safetyPool': 'Страховий пул',
        'admin.feesToFund': '5% комісій → фонд',
        'admin.slippageProtection': 'Захист від прослизання',
        'admin.tournaments': 'Турніри',
        'admin.createManage': 'Створити та керувати',
        'admin.topTraders': 'Топ трейдери',
        'admin.proposalsVotes': 'Пропозиції та голоси',
        'admin.referralPayouts': 'Реферальні виплати',
        'admin.totalReferrals': 'Всього рефералів',
        'admin.premiumUsers': 'Преміум користувачі',
        'admin.pendingPayouts': 'Очікувані виплати',
        'admin.platformRevenue': 'Дохід платформи',
        'admin.loadingExchangeBalances': 'Завантаження балансів бірж...',
        'admin.connectedNodes': 'Підключені вузли',
        'admin.activePositions': 'Активні позиції',
        'admin.systemLogs': 'Системні логи',
        'admin.recentActivity': 'Остання активність',
        'admin.noLogs': 'Логи відсутні',
        'admin.user': 'Користувач',
        'admin.balance': 'Баланс',
        'admin.status': 'Статус',
        'admin.actions': 'Дії',
        'admin.active': 'Активний',
        'admin.paused': 'Призупинено',
        'admin.pause': 'Призупинити',
        'admin.resume': 'Відновити',
        'admin.noNodes': 'Немає підключених вузлів',
        'admin.symbol': 'Символ',
        'admin.side': 'Сторона',
        'admin.size': 'Розмір',
        'admin.entryPrice': 'Ціна входу',
        'admin.pnl': 'PnL',
        'admin.noPositions': 'Немає активних позицій',
        'admin.masterExchanges': 'Головні біржі',
        'admin.addMasterExchange': 'Додати головну біржу',
        'admin.userExchanges': 'Біржі користувачів',
        'admin.noExchanges': 'Біржі не підключені',
        'admin.globalSettings': 'Глобальні налаштування',
        'admin.maxPositions': 'Макс. позицій',
        'admin.riskLevel': 'Рівень ризику',
        'admin.saveSettings': 'Зберегти налаштування',
        'admin.tradeHistory': 'Історія угод',
        'admin.openPositions': 'Відкриті позиції',
        'admin.closedTrades': 'Закриті угоди',
        'admin.time': 'Час',
        'admin.type': 'Тип',
        'admin.entry': 'Вхід',
        'admin.exit': 'Вихід',
        'admin.noTrades': 'Угод ще немає',
        'admin.testnet': 'Тестова мережа',
        'admin.mainnet': 'Основна мережа',
        'admin.apiKey': 'API ключ',
        'admin.apiSecret': 'API секрет',
        'admin.connect': 'Підключити',
        'admin.disconnect': 'Відключити',
        'admin.exchangeConnected': 'Біржу успішно підключено',
        'admin.exchangeDisconnected': 'Біржу відключено',
        'admin.copyAll': 'Копіювати всіх',
        'admin.pauseAll': 'Призупинити всіх',
        'admin.resumeAll': 'Відновити всіх',
        'admin.broadcast': 'Розсилка',
        'admin.sendNotification': 'Надіслати сповіщення',
        'admin.notificationSent': 'Сповіщення надіслано всім користувачам',
        'admin.services': 'Сервіси',
        'admin.serviceSettings': 'Налаштування сервісів',
        'admin.telegramBot': 'Telegram бот',
        'admin.emailSmtp': 'Email/SMTP',
        'admin.plisioPayments': 'Plisio платежі',
        'admin.twitterX': 'Twitter/X',
        'admin.openaiSupport': 'OpenAI (Бот підтримки)',
        'admin.webPush': 'Web Push',
        'admin.enabled': 'Увімкнено',
        'admin.disabled': 'Вимкнено',
        'admin.configure': 'Налаштувати',
        'admin.activeTournament': 'Активний турнір',
        
        // User Dashboard
        'user.title': 'Термінал',
        'user.portfolio': 'Портфель',
        'user.totalBalance': 'Загальний баланс',
        'user.todayPnl': 'PnL сьогодні',
        'user.allTimePnl': 'PnL за весь час',
        'user.copyingActive': 'Копіювання активне',
        'user.copyingStopped': 'Копіювання зупинено',
        'user.startCopying': 'Почати копіювання',
        'user.stopCopying': 'Зупинити копіювання',
        'user.myPositions': 'Мої позиції',
        'user.myTrades': 'Мої угоди',
        'user.noPositions': 'Немає відкритих позицій',
        'user.noTrades': 'Угод ще немає',
        'user.connectExchange': 'Підключити біржу',
        'user.exchangeSettings': 'Налаштування біржі',
        'user.riskSettings': 'Налаштування ризиків',
        'user.maxPositionSize': 'Макс. розмір позиції',
        'user.stopLoss': 'Стоп-лосс',
        'user.takeProfit': 'Тейк-профіт',
        'user.notifications': 'Сповіщення',
        'user.telegramAlerts': 'Telegram сповіщення',
        'user.emailAlerts': 'Email сповіщення',
        'user.pushAlerts': 'Push сповіщення',
        'user.referralProgram': 'Реферальна програма',
        'user.yourReferralCode': 'Ваш реферальний код',
        'user.referralEarnings': 'Реферальний дохід',
        'user.totalReferred': 'Всього запрошено',
        'user.copyCode': 'Копіювати код',
        'user.copied': 'Скопійовано!',
        'user.subscription': 'Підписка',
        'user.currentPlan': 'Поточний план',
        'user.freePlan': 'Безкоштовний план',
        'user.proPlan': 'Pro план',
        'user.elitePlan': 'Elite план',
        'user.upgradePlan': 'Покращити план',
        'user.analytics': 'Аналітика',
        'user.performance': 'Продуктивність',
        'user.weeklyReport': 'Тижневий звіт',
        'user.monthlyReport': 'Місячний звіт',
        'user.connections': 'Підключення',
        'user.config': 'Конфігурація',
        'user.terminal': 'Термінал'
    }
};

let currentLang = 'en';

function initLanguage() {
    currentLang = localStorage.getItem('lang') || 'en';
    updateLanguageUI();
    applyTranslations();
}

function toggleLanguage() {
    currentLang = currentLang === 'en' ? 'ua' : 'en';
    localStorage.setItem('lang', currentLang);
    updateLanguageUI();
    applyTranslations();
    
    playSound('click');
}

function updateLanguageUI() {
    document.querySelectorAll('.lang-flag').forEach(flag => {
        flag.textContent = currentLang === 'ua' ? '🇺🇦' : '🇺🇸';
    });
    
    document.querySelectorAll('.lang-code').forEach(code => {
        code.textContent = currentLang === 'ua' ? 'UA' : 'EN';
    });
}

function t(key) {
    return translations[currentLang]?.[key] || translations['en']?.[key] || key;
}

function applyTranslations() {
    // Translate all elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const translation = t(key);
        if (translation && translation !== key) {
            // Check if element has HTML content (icons, etc.)
            const hasHTML = el.innerHTML.includes('<');
            if (hasHTML) {
                // Preserve HTML structure, replace text content
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = el.innerHTML;
                const textContent = tempDiv.textContent || tempDiv.innerText || '';
                const trimmedText = textContent.trim();
                
                if (trimmedText) {
                    // Get English text for comparison
                    const enText = translations['en'][key] || '';
                    
                    // Replace text while preserving HTML
                    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
                    const textNodes = [];
                    let node;
                    while (node = walker.nextNode()) {
                        const nodeText = node.textContent.trim();
                        if (nodeText && (nodeText === trimmedText || nodeText === enText || nodeText === translation)) {
                            textNodes.push(node);
                        }
                    }
                    if (textNodes.length > 0) {
                        // Replace first text node
                        textNodes[0].textContent = translation;
                        // Remove other matching text nodes to avoid duplicates
                        for (let i = 1; i < textNodes.length; i++) {
                            const nodeText = textNodes[i].textContent.trim();
                            if (nodeText === trimmedText || nodeText === enText || nodeText === translation) {
                                textNodes[i].textContent = '';
                            }
                        }
                    } else {
                        // Fallback: replace innerHTML but keep structure
                        if (el.innerHTML.includes(trimmedText)) {
                            el.innerHTML = el.innerHTML.replace(trimmedText, translation);
                        } else if (el.innerHTML.includes(enText)) {
                            el.innerHTML = el.innerHTML.replace(enText, translation);
                        }
                    }
                }
            } else {
                // Simple text replacement
                el.textContent = translation;
            }
        }
    });
    
    // Translate placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const translation = t(key);
        if (translation && translation !== key) {
            el.placeholder = translation;
        }
    });
    
    // Translate titles
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        const translation = t(key);
        if (translation && translation !== key) {
            el.title = translation;
        }
    });
    
    // Translate aria-labels
    document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
        const key = el.getAttribute('data-i18n-aria-label');
        const translation = t(key);
        if (translation && translation !== key) {
            el.setAttribute('aria-label', translation);
        }
    });
    
    // Translate button text (including those with icons) - improved matching
    document.querySelectorAll('button, a.btn-primary, a.btn-secondary, .btn-primary, .btn-secondary').forEach(btn => {
        const originalText = btn.textContent.trim();
        if (!originalText) return;
        
        // Try to find matching translation
        Object.keys(translations['en']).forEach(key => {
            const enText = translations['en'][key];
            if (originalText === enText || originalText.includes(enText)) {
                const translatedText = translations[currentLang][key];
                if (translatedText && translatedText !== enText) {
                    // Check if button has icon
                    if (btn.innerHTML.includes('<i')) {
                        // Preserve icon, replace text
                        const iconMatch = btn.innerHTML.match(/<i[^>]*>.*?<\/i>/);
                        if (iconMatch) {
                            btn.innerHTML = iconMatch[0] + ' ' + translatedText;
                        } else {
                            btn.textContent = translatedText;
                        }
                    } else {
                        btn.textContent = translatedText;
                    }
                }
            }
        });
    });
    
    // Translate common text patterns in spans, divs, p tags without data-i18n
    const commonTexts = ['Overview', 'Statistics', 'Positions', 'History', 'Exchange', 'Settings', 'Users', 'Controls', 
                         'Dashboard', 'Messages', 'Login', 'Register', 'Save', 'Cancel', 'Submit', 'Delete', 'Edit', 'Add',
                         'Loading...', 'No open positions', 'No trade history yet', 'Live', 'Active', 'Pending'];
    
    commonTexts.forEach(text => {
        const key = Object.keys(translations['en']).find(k => translations['en'][k] === text);
        if (key) {
            const translation = t(key);
            if (translation && translation !== text) {
                document.querySelectorAll(`span:not([data-i18n]), div:not([data-i18n]), p:not([data-i18n])`).forEach(el => {
                    if (el.textContent.trim() === text && !el.closest('[data-i18n]')) {
                        el.textContent = translation;
                    }
                });
            }
        }
    });
    
    // Force update after a short delay to catch dynamically added content
    setTimeout(() => {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = t(key);
            if (translation && translation !== key) {
                const currentText = el.textContent.trim();
                const enText = translations['en'][key];
                const uaText = translations['ua'][key];
                // Only update if still showing wrong language text
                if ((currentLang === 'ua' && currentText === enText) || 
                    (currentLang === 'en' && currentText === uaText) ||
                    (!currentText.includes(translation) && !el.innerHTML.includes(translation) && currentText)) {
                    if (!el.innerHTML.includes('<')) {
                        el.textContent = translation;
                    } else {
                        // Try to update text nodes
                        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
                        let node;
                        while (node = walker.nextNode()) {
                            const nodeText = node.textContent.trim();
                            if (nodeText === enText || nodeText === uaText) {
                                node.textContent = translation;
                                break;
                            }
                        }
                    }
                }
            }
        });
    }, 200);
    
    // Also re-apply after a longer delay for any late-loaded content
    setTimeout(() => {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = t(key);
            if (translation && translation !== key) {
                const currentText = el.textContent.trim();
                const enText = translations['en'][key];
                const uaText = translations['ua'][key];
                if ((currentLang === 'ua' && currentText === enText) || 
                    (currentLang === 'en' && currentText === uaText)) {
                    if (!el.innerHTML.includes('<')) {
                        el.textContent = translation;
                    }
                }
            }
        });
    }, 1000);
}

// Export function to re-apply translations (useful for dynamically added content)
window.reapplyTranslations = applyTranslations;

window.t = t;
window.currentLang = currentLang;

// ==================== PERFORMANCE DETECTION ====================
const isMobile = window.innerWidth <= 768 || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
const isLowPerformance = isMobile || navigator.hardwareConcurrency <= 4 || window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ==================== ANIMATIONS ====================
function initAnimations() {
    // Skip heavy animations on mobile/low-performance devices
    if (isLowPerformance) {
        console.log('🚀 Performance mode: Heavy animations disabled');
        return;
    }
    
    // Intersection Observer for scroll animations
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.1, rootMargin: '50px' });
    
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });
    
    // Staggered animations for children
    document.querySelectorAll('.stagger-children').forEach(container => {
        Array.from(container.children).forEach((child, index) => {
            child.style.animationDelay = `${index * 0.05}s`;
        });
    });
    
    // Parallax effect on scroll - only on desktop
    if (!isMobile) {
        let ticking = false;
        window.addEventListener('scroll', () => {
            if (!ticking) {
                window.requestAnimationFrame(() => {
                    updateParallax();
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });
    }
}

function updateParallax() {
    // Skip on mobile
    if (isMobile) return;
    
    const scrolled = window.scrollY;
    
    document.querySelectorAll('.app-glow').forEach((glow, index) => {
        const speed = index === 0 ? 0.3 : 0.2;
        glow.style.transform = `translateY(${scrolled * speed}px)`;
    });
}

// ==================== SOUNDS ====================
let soundEnabled = true;
const sounds = {};

function initSounds() {
    soundEnabled = localStorage.getItem('soundEnabled') !== 'false';
    
    // Lazy load sounds
    sounds.click = null;
    sounds.success = null;
    sounds.notification = null;
}

function playSound(type) {
    if (!soundEnabled) return;
    
    // Create sound only when needed
    if (!sounds[type]) {
        const soundData = {
            click: 'UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdH2FgoGCgYB+fH18fYGGi4mHhYOBgYGBgYGCgoOEhYaGhoaFhIOCgYB/fn18e3p5eHd3d3d4eXp7fH1+f4CBgoOEhIWFhYWFhYWEhIOCgYB/fn18e3p5eHd3d3d4eXp7fH1+f4CBgoOEhIWFhYWFhYWEg4KBgH59fHt6eXl4d3d3eHl6e3x9fn+AgYKDhISFhQ==',
            success: 'UklGRjIFAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQ4FAAB/f39/f39/f39/gICAgICAgICAgYGBgYGCgoKCg4ODg4SEhISFhYWGhoaHh4eIiIiJiYmKioqLi4uMjIyNjY2Ojo6Pj4+QkJCRkZGSkpKTk5OUlJSVlZWWlpaXl5eYmJiZmZmampqbm5ucnJydnZ2enp6fn5+goKChoaGioqKjo6OkpKSlpaWmpqanp6eoqKipqamqqqqrq6usrKytra2urq6vr6+wsLCxsbGysrKzs7O0tLS1tbW2tra3t7e4uLi5ubm6urq7u7u8vLy9vb2+vr6/v7/AwMDBwcHCwsLDw8PExMTFxcXGxsbHx8fIyMjJycnKysrLy8vMzMzNzc3Ozs7Pz8/Q0NDR0dHS0tLT09PU1NTV1dXW1tbX19fY2NjZ2dna2trb29vc3Nzd3d3e3t7f39/g4ODh4eHi4uLj4+Pk5OTl5eXm5ubn5+fo6Ojp6enq6urr6+vs7Ozt7e3u7u7v7+/w8PDx8fHy8vLz8/P09PT19fX29vb39/f4+Pj5+fn6+vr7+/v8/Pz9/f3+/v7///8=',
            notification: 'UklGRl9FAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YTtFAACAgICAgICAgICAgICBgYGBgoKCg4ODhISEhYWGhoaHh4iIiImJiYqKiouLjIyMjY2Ojo6Pj5CQkJGRkpKSk5OUlJSVlZaWlpeXmJiYmZmampubm5ycnZ2dnp6fn5+goKGhoaKio6OjpKSlpaampqenqKioqamqqqqrrKysra2urq6vr7CwsLGxsrKys7O0tLS1tba2tre3uLi4ubm6urq7u7y8vL29vr6+v7/AwMDBwcLCwsPDxMTExcXGxsbHx8jIyMnJysrKy8vMzMzNzc7Ozs/P0NDQ0dHS0tLT09TU1NXV1tbW19fY2NjZ2dra2tvb3Nzc3d3e3t7f3+Dg4OHh4uLi4+Pk5OTl5ebm5ufn6Ojo6enq6urr6+zs7O3t7u7u7+/w8PDx8fLy8vPz9PT09fX29vb39/j4+Pn5+vr6+/v8/Pz9/f7+/v///w=='
        };
        
        if (soundData[type]) {
            sounds[type] = new Audio('data:audio/wav;base64,' + soundData[type]);
            sounds[type].volume = 0.2;
        }
    }
    
    if (sounds[type]) {
        sounds[type].currentTime = 0;
        sounds[type].play().catch(() => {});
    }
}

function toggleSound() {
    soundEnabled = !soundEnabled;
    localStorage.setItem('soundEnabled', soundEnabled);
    
    document.querySelectorAll('.sound-icon').forEach(icon => {
        icon.className = soundEnabled ? 'fas fa-volume-up sound-icon' : 'fas fa-volume-mute sound-icon';
    });
    
    playSound('click');
}

// ==================== TOOLTIPS ====================
function initTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach(el => {
        el.addEventListener('mouseenter', showTooltip);
        el.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(e) {
    const text = e.target.getAttribute('data-tooltip');
    if (!text) return;
    
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip-popup';
    tooltip.textContent = text;
    tooltip.style.cssText = `
        position: fixed;
        background: var(--color-surface);
        border: 1px solid var(--color-border);
        color: var(--text-primary);
        padding: 8px 12px;
        border-radius: var(--radius-sm);
        font-size: 0.75rem;
        z-index: 9999;
        pointer-events: none;
        box-shadow: var(--shadow-card);
        white-space: nowrap;
    `;
    
    document.body.appendChild(tooltip);
    
    const rect = e.target.getBoundingClientRect();
    tooltip.style.left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2 + 'px';
    tooltip.style.top = rect.top - tooltip.offsetHeight - 8 + 'px';
    
    e.target._tooltip = tooltip;
}

function hideTooltip(e) {
    if (e.target._tooltip) {
        e.target._tooltip.remove();
        delete e.target._tooltip;
    }
}

// ==================== TOAST NOTIFICATIONS ====================
function showToast(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    const colors = {
        success: 'var(--neon-green)',
        error: 'var(--neon-red)',
        warning: 'var(--neon-yellow)',
        info: 'var(--neon-cyan)'
    };
    
    toast.innerHTML = `
        <i class="fas ${icons[type] || icons.info}" style="font-size: 1.125rem; color: ${colors[type] || colors.info}"></i>
        <span style="flex: 1; font-size: 0.875rem;">${message}</span>
        <button onclick="this.parentElement.remove()" style="background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 4px;">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    container.appendChild(toast);
    
    playSound(type === 'success' ? 'success' : 'notification');
    
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ==================== UTILITY FUNCTIONS ====================
function formatNumber(num, decimals = 2) {
    return num.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

function formatCurrency(num, currency = '$') {
    return currency + formatNumber(num);
}

function formatPercent(num) {
    const sign = num >= 0 ? '+' : '';
    return sign + formatNumber(num) + '%';
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success', 2000);
    }).catch(() => {
        showToast('Failed to copy', 'error', 2000);
    });
}

function animateCounter(element, start, end, duration = 1000, prefix = '', suffix = '') {
    // On mobile, just set the value directly without animation
    if (isLowPerformance) {
        element.textContent = prefix + formatNumber(end) + suffix;
        return;
    }
    
    const startTime = performance.now();
    
    const update = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Ease out cubic
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = start + (end - start) * easeOut;
        
        element.textContent = prefix + formatNumber(current) + suffix;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    };
    
    requestAnimationFrame(update);
}

function celebrateSuccess() {
    // Skip confetti on mobile/low-performance devices
    if (isLowPerformance) return;
    
    if (typeof confetti !== 'undefined') {
        confetti({
            particleCount: 50, // Reduced from 100
            spread: 60,
            origin: { y: 0.6 },
            colors: ['#00d4ff', '#ff00d4', '#00ff88', '#ffd000'],
            disableForReducedMotion: true
        });
    }
}

// ==================== RIPPLE EFFECT ====================
document.addEventListener('click', (e) => {
    // Skip ripple effect on mobile
    if (isMobile) return;
    
    const btn = e.target.closest('.btn-primary, .btn-secondary');
    if (!btn) return;
    
    const ripple = document.createElement('span');
    ripple.style.cssText = `
        position: absolute;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,0.4) 0%, transparent 70%);
        width: 20px;
        height: 20px;
        pointer-events: none;
        animation: ripple 0.6s ease-out;
    `;
    
    const rect = btn.getBoundingClientRect();
    ripple.style.left = (e.clientX - rect.left - 10) + 'px';
    ripple.style.top = (e.clientY - rect.top - 10) + 'px';
    
    btn.style.position = 'relative';
    btn.style.overflow = 'hidden';
    btn.appendChild(ripple);
    
    setTimeout(() => ripple.remove(), 600);
    
    playSound('click');
});

// Add keyframes dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes ripple {
        0% { transform: scale(0); opacity: 0.8; }
        100% { transform: scale(6); opacity: 0; }
    }
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// ==================== TYPING DISCLAIMER ANIMATION ====================
let disclaimerTyped = false;
let typingInterval = null;

function initDisclaimerTyping() {
    const disclaimerText = document.getElementById('disclaimerText');
    const typingCursor = document.getElementById('typingCursor');
    const disclaimerTime = document.getElementById('disclaimerTime');
    
    if (!disclaimerText) return;
    
    // Set timestamp
    if (disclaimerTime) {
        const now = new Date();
        disclaimerTime.textContent = now.toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
    }
    
    // Intersection Observer to start typing when visible
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !disclaimerTyped) {
                disclaimerTyped = true;
                startTypingAnimation();
                observer.disconnect();
            }
        });
    }, { threshold: 0.3 });
    
    const disclaimer = document.getElementById('disclaimer');
    if (disclaimer) {
        observer.observe(disclaimer);
    }
}

function startTypingAnimation() {
    const disclaimerText = document.getElementById('disclaimerText');
    const typingCursor = document.getElementById('typingCursor');
    
    if (!disclaimerText) return;
    
    // Get the translated text
    const fullText = t('disclaimer.mainText');
    
    // Words/phrases to highlight
    const highlights = {
        en: {
            danger: ['SIGNIFICANT RISK', 'NOT', 'ATTENTION:', 'RISK'],
            warning: ['copy trading', 'responsible', 'Never invest', 'Past performance'],
            info: ['volatile', 'rapidly', 'unpredictably']
        },
        ua: {
            danger: ['ЗНАЧНИМ РИЗИКОМ', 'НЕ', 'УВАГА:', 'РИЗИК'],
            warning: ['Копі-трейдинг', 'відповідальність', 'Ніколи не інвестуйте', 'Минулі результати'],
            info: ['Волатильність', 'швидко', 'непередбачувано']
        }
    };
    
    let currentIndex = 0;
    const typingSpeed = 25; // ms per character
    
    // Clear any existing interval
    if (typingInterval) {
        clearInterval(typingInterval);
    }
    
    disclaimerText.innerHTML = '';
    
    typingInterval = setInterval(() => {
        if (currentIndex < fullText.length) {
            // Get the current visible text
            let displayText = fullText.substring(0, currentIndex + 1);
            
            // Apply highlights
            const lang = currentLang === 'ua' ? 'ua' : 'en';
            const highlightRules = highlights[lang];
            
            // Apply danger highlights
            highlightRules.danger.forEach(word => {
                const regex = new RegExp(`(${escapeRegex(word)})`, 'gi');
                displayText = displayText.replace(regex, '<span class="danger">$1</span>');
            });
            
            // Apply warning highlights  
            highlightRules.warning.forEach(word => {
                const regex = new RegExp(`(${escapeRegex(word)})`, 'gi');
                displayText = displayText.replace(regex, '<span class="highlight">$1</span>');
            });
            
            // Apply info highlights
            highlightRules.info.forEach(word => {
                const regex = new RegExp(`(${escapeRegex(word)})`, 'gi');
                displayText = displayText.replace(regex, '<span class="info">$1</span>');
            });
            
            disclaimerText.innerHTML = displayText;
            currentIndex++;
            
            // Play subtle typing sound occasionally
            if (currentIndex % 10 === 0 && !isLowPerformance) {
                // Visual feedback instead of sound for typing
            }
        } else {
            // Typing complete
            clearInterval(typingInterval);
            typingInterval = null;
            
            // Keep cursor blinking
            if (typingCursor) {
                typingCursor.style.animation = 'cursorBlink 1s step-end infinite';
            }
        }
    }, typingSpeed);
}

// Helper to escape regex special characters
function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Restart typing animation when language changes
function restartDisclaimerTyping() {
    disclaimerTyped = false;
    if (typingInterval) {
        clearInterval(typingInterval);
        typingInterval = null;
    }
    
    const disclaimerText = document.getElementById('disclaimerText');
    if (disclaimerText) {
        disclaimerText.innerHTML = '';
    }
    
    // Check if disclaimer is in view
    const disclaimer = document.getElementById('disclaimer');
    if (disclaimer) {
        const rect = disclaimer.getBoundingClientRect();
        const isVisible = rect.top < window.innerHeight && rect.bottom > 0;
        
        if (isVisible) {
            disclaimerTyped = true;
            setTimeout(startTypingAnimation, 300);
        } else {
            // Set up observer again
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting && !disclaimerTyped) {
                        disclaimerTyped = true;
                        startTypingAnimation();
                        observer.disconnect();
                    }
                });
            }, { threshold: 0.3 });
            observer.observe(disclaimer);
        }
    }
}

// Override toggleLanguage to also restart disclaimer typing
const originalToggleLanguage = toggleLanguage;
window.toggleLanguage = function() {
    currentLang = currentLang === 'en' ? 'ua' : 'en';
    localStorage.setItem('lang', currentLang);
    updateLanguageUI();
    applyTranslations();
    restartDisclaimerTyping();
    playSound('click');
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(initDisclaimerTyping, 500);
});

// ==================== GLOBAL EXPORTS ====================
window.toggleMobileMenu = toggleMobileMenu;
window.closeMobileMenu = closeMobileMenu;
window.toggleUserMenu = toggleUserMenu;
window.toggleLanguage = toggleLanguage;
window.toggleSound = toggleSound;
window.showSection = showSection;
window.showToast = showToast;
window.playSound = playSound;
window.formatNumber = formatNumber;
window.formatCurrency = formatCurrency;
window.formatPercent = formatPercent;
window.animateCounter = animateCounter;
window.celebrateSuccess = celebrateSuccess;
window.copyToClipboard = copyToClipboard;
