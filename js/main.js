// Language Support
const languages = {
    en: {
        nav: {
            trade: 'Trade',
            cases: 'Cases',
            wallet: 'Wallet',
            login: 'Login',
            dashboard: 'Dashboard'
        },
        home: {
            title: 'Trade CS2 Skins',
            subtitle: 'Like Never Before',
            description: 'Instant trades, automated bots, and exciting case openings. Join the future of CS2 skin trading.',
            startTrading: 'Start Trading',
            openCases: 'Open Cases'
        },
        trade: {
            yourInventory: 'Your Inventory',
            botInventory: 'Bot Inventory',
            searchSkins: 'Search skins...',
            allTypes: 'All Types',
            priceRange: 'Price Range',
            floatValue: 'Float Value',
            makeTrade: 'Make Trade Offer'
        },
        cases: {
            balance: 'Balance',
            addFunds: 'Add Funds',
            openCase: 'Open Case',
            recentDrops: 'Recent Drops'
        },
        wallet: {
            availableBalance: 'Available Balance',
            pendingWithdrawals: 'Pending Withdrawals',
            totalTraded: 'Total Traded',
            deposit: 'Deposit',
            withdraw: 'Withdraw',
            amount: 'Amount',
            selectPayment: 'Select Payment Method'
        }
    },
    pt: {
        nav: {
            trade: 'Trocar',
            cases: 'Caixas',
            wallet: 'Carteira',
            login: 'Entrar',
            dashboard: 'Painel'
        },
        home: {
            title: 'Troque Skins CS2',
            subtitle: 'Como Nunca Antes',
            description: 'Trocas instantâneas, bots automatizados e abertura de caixas emocionante. Junte-se ao futuro das trocas de skins CS2.',
            startTrading: 'Começar a Trocar',
            openCases: 'Abrir Caixas'
        },
        trade: {
            yourInventory: 'Seu Inventário',
            botInventory: 'Inventário do Bot',
            searchSkins: 'Procurar skins...',
            allTypes: 'Todos os Tipos',
            priceRange: 'Faixa de Preço',
            floatValue: 'Valor Float',
            makeTrade: 'Fazer Oferta de Troca'
        },
        cases: {
            balance: 'Saldo',
            addFunds: 'Adicionar Fundos',
            openCase: 'Abrir Caixa',
            recentDrops: 'Drops Recentes'
        },
        wallet: {
            availableBalance: 'Saldo Disponível',
            pendingWithdrawals: 'Saques Pendentes',
            totalTraded: 'Total Negociado',
            deposit: 'Depositar',
            withdraw: 'Sacar',
            amount: 'Valor',
            selectPayment: 'Selecionar Método de Pagamento'
        }
    }
};

// Steam API Integration
class SteamAPI {
    constructor() {
        this.baseUrl = window.location.origin;
    }

    async getUserInventory(steamId) {
        try {
            // Check if user is authenticated
            if (!steamId || !sessionStorage.getItem('authenticated')) {
                window.location.href = '/login.html';
                return null;
            }

            const response = await fetch(`${this.baseUrl}/api/inventory/${steamId}`);
            if (!response.ok) {
                throw new Error('Failed to fetch inventory');
            }
            const data = await response.json();
            return this.formatInventoryData(data);
        } catch (error) {
            console.error('Error fetching inventory:', error);
            showErrorMessage('Failed to load inventory. Please try again.');
            return null;
        }
    }

    formatInventoryData(data) {
        if (!data.result || !data.result.items) {
            return [];
        }

        return data.result.items.map(item => ({
            id: item.id,
            name: item.market_hash_name,
            type: item.type,
            wear: item.wear,
            price: parseFloat(item.price || 0),
            imageUrl: `https://community.cloudflare.steamstatic.com/economy/image/${item.icon_url}/360fx360f`
        }));
    }

    async depositSkins(steamId, items) {
        try {
            const response = await fetch(`${this.baseUrl}/api/trade/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    steamId,
                    itemsToReceive: items,
                    itemsToGive: []
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to create trade offer');
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error depositing skins:', error);
            showErrorMessage('Failed to create trade offer. Please try again.');
            return null;
        }
    }

    async createTradeOffer(steamId, itemsToGive, itemsToReceive) {
        try {
            const response = await fetch(`${this.baseUrl}/api/trade/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    steamId,
                    itemsToGive,
                    itemsToReceive
                })
            });

            if (!response.ok) {
                throw new Error('Failed to create trade offer');
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error creating trade offer:', error);
            showErrorMessage('Failed to create trade offer. Please try again.');
            return null;
        }
    }

    async getRecentDrops() {
        try {
            const response = await fetch(`${this.baseUrl}/api/recent-drops`);
            if (!response.ok) {
                throw new Error('Failed to fetch recent drops');
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching recent drops:', error);
            return [];
        }
    }

    async getCaseItems(caseId) {
        try {
            const response = await fetch(`${this.baseUrl}/api/case/${caseId}/items`);
            if (!response.ok) {
                throw new Error('Failed to fetch case items');
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching case items:', error);
            return [];
        }
    }
}

// Language Management
class LanguageManager {
    constructor() {
        this.currentLang = 'en';
        this.languages = languages;
    }

    async detectUserLanguage() {
        try {
            // Try to get language from browser
            const browserLang = navigator.language.split('-')[0];
            
            // Try to get language from IP geolocation
            const response = await fetch('https://ipapi.co/json/');
            const data = await response.json();
            const geoLang = data.languages.split(',')[0].split('-')[0];

            // Use browser language if supported, otherwise geolocation language, or fall back to English
            this.currentLang = this.languages[browserLang] ? browserLang :
                             this.languages[geoLang] ? geoLang : 'en';
        } catch (error) {
            console.error('Error detecting language:', error);
            this.currentLang = 'en';
        }

        this.updatePageLanguage();
    }

    setLanguage(lang) {
        if (this.languages[lang]) {
            this.currentLang = lang;
            this.updatePageLanguage();
            localStorage.setItem('preferredLanguage', lang);
        }
    }

    updatePageLanguage() {
        const translations = this.languages[this.currentLang];
        
        // Update all elements with data-lang attribute
        document.querySelectorAll('[data-lang]').forEach(element => {
            const key = element.dataset.lang;
            const keys = key.split('.');
            let translation = translations;
            
            for (const k of keys) {
                translation = translation[k];
                if (!translation) break;
            }

            if (translation) {
                if (element.tagName === 'INPUT' && element.getAttribute('type') === 'placeholder') {
                    element.placeholder = translation;
                } else {
                    element.textContent = translation;
                }
            }
        });
    }
}

// Initialize language support and Steam integration
document.addEventListener('DOMContentLoaded', () => {
    // Initialize language manager
    const langManager = new LanguageManager();
    
    // Check for saved language preference
    const savedLang = localStorage.getItem('preferredLanguage');
    if (savedLang) {
        langManager.setLanguage(savedLang);
    } else {
        langManager.detectUserLanguage();
    }

    // Initialize Steam API
    const steamAPI = new SteamAPI();

    // Add language selector event listeners
    document.querySelectorAll('.lang-select').forEach(button => {
        button.addEventListener('click', () => {
            langManager.setLanguage(button.dataset.lang);
        });
    });

    // Handle Steam login button if present
    const steamLoginBtn = document.getElementById('steamLoginBtn');
    const errorContainer = document.getElementById('errorContainer');
    const errorMessage = document.getElementById('errorMessage');
    
    if (steamLoginBtn) {
        steamLoginBtn.addEventListener('click', () => {
            if (errorContainer) errorContainer.classList.add('hidden');
            // Show loading state
            steamLoginBtn.innerHTML = `
                <i class="fas fa-spinner fa-spin text-2xl"></i>
                <span class="font-semibold ml-3" data-lang="login.connecting">Connecting to Steam...</span>
            `;
            
            // Redirect to our backend auth endpoint
            window.location.href = '/auth/steam';
        });

        // Check for error parameter
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('error')) {
            const errorType = urlParams.get('error');
            const errorMessages = {
                'api_key': 'Steam API key not configured. Please contact the administrator.',
                'invalid_response': 'Invalid response from Steam. Please try again.',
                'no_steam_id': 'Could not retrieve your Steam ID. Please try again.',
                'api_error': 'Error connecting to Steam API. Please try again later.',
                'storage': 'Error storing login data. Please enable cookies and try again.',
                'default': 'Authentication failed. Please try again.'
            };
            
            if (errorContainer && errorMessage) {
                errorMessage.textContent = errorMessages[errorType] || errorMessages.default;
                errorContainer.classList.remove('hidden');
                // Reset button state
                steamLoginBtn.innerHTML = `
                    <i class="fab fa-steam text-2xl"></i>
                    <span class="font-semibold" data-lang="login.steamButton">Sign in through Steam</span>
                `;
            } else {
                showErrorMessage(errorMessages[errorType] || errorMessages.default);
            }
        }
    }

    // Handle logout button if present
    const logoutBtn = document.querySelector('a[href="#"][data-action="logout"]');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            sessionStorage.removeItem('authenticated');
            window.location.href = '/logout';
        });
    }

    // Check authentication status on protected pages
    const protectedPages = ['/dashboard.html', '/trade.html', '/boxes.html', '/wallet.html'];
    if (protectedPages.includes(window.location.pathname) && !sessionStorage.getItem('authenticated')) {
        window.location.href = '/login.html';
    }
});

// UI Update Functions
function showErrorMessage(message) {
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 cyber-border rounded-lg p-4 bg-black/90 backdrop-blur-md text-red-500';
    toast.innerHTML = `
        <i class="fas fa-exclamation-circle mr-2"></i>
        ${message}
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function updateInventoryUI(inventory) {
    const inventoryContainer = document.querySelector('.user-inventory');
    if (!inventoryContainer) return;

    inventoryContainer.innerHTML = inventory.map(item => `
        <div class="cyber-border rounded-lg p-2 bg-black/50 relative skin-card group">
            <img src="${item.imageUrl}" alt="${item.name}" class="w-full rounded">
            <div class="skin-details opacity-0 transform translate-y-2 transition-all absolute inset-0 bg-black/80 rounded flex flex-col items-center justify-center p-2">
                <p class="text-sm font-semibold text-cyber-blue">${item.name}</p>
                <p class="text-xs text-gray-400">${item.type}</p>
                <p class="text-sm font-bold mt-1">$${item.price}</p>
                <p class="text-xs text-gray-400">Float: ${item.float}</p>
            </div>
        </div>
    `).join('');
}
