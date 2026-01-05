/**
 * Ultra-fast Price Grid Rendering
 * Optimized for HFT with minimal DOM manipulation
 * Pro Terminal Edition - Watchlist System
 */

class PriceGrid {
    constructor() {
        this.gridContainer = document.getElementById('widget-grid');
        this.widgets = new Map(); // symbol -> widget element
        this.optionRows = new Map(); // optionSymbol -> row element

        // Watchlist System
        this.watchlists = [
            {
                name: "Bank Nifty",
                icon: "📊",
                symbols: ["BANKNIFTY", "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK",
                    "SBIN", "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "PNB", "AUBANK"],
                editable: false
            },
            {
                name: "NFO Stocks",
                icon: "🏢",
                symbols: [], // Will be populated from market data
                editable: false
            },
            {
                name: "Custom",
                icon: "⭐",
                symbols: [],
                editable: true
            }
        ];
        this.currentWatchlistIndex = 0;
        this.sortBy = 'change'; // 'change', 'name', 'price'
        this.sortAsc = false;

        // Load saved watchlists
        this.loadWatchlists();

        // Market Watch Data
        this.marketData = []; // Store all stock data for sorting
        this.marketList = document.getElementById('market-list');
        this.watchlistTabs = document.getElementById('watchlist-tabs');

        // Bank Nifty Hero
        this.bankniftyPrice = document.getElementById('banknifty-price');
        this.bankniftyChange = document.getElementById('banknifty-change');

        // Positions and Orders
        this.positions = {};
        this.positionsTableBody = document.getElementById('positions-table-body');
        this.ordersLog = document.getElementById('orders-log');
        this.posCountBadge = document.getElementById('pos-count');

        // Init
        this.initModeToggle();
        this.initAutoTradeToggle();
        this.initSimulationControls();
        this.initAutoTradeToggle();
        this.initSimulationControls();
        this.initThresholdSlider();
        this.initTimeframeControl();
        this.initWatchlistControls();
        this.startOrderSync(); // Start polling for orders

        // Config
        this.lotSizes = { 'BANKNIFTY': 15, 'NIFTY': 50 };
        this.loadConfig();

        // Render loop
        setInterval(() => this.renderMarketWatch(), 2000);

        // Initial render of tabs
        this.renderWatchlistTabs();
    }

    // Watchlist Methods
    switchWatchlist(index) {
        this.currentWatchlistIndex = index;
        this.renderWatchlistTabs();
        this.renderMarketWatch();
    }

    renderWatchlistTabs() {
        if (!this.watchlistTabs) return;

        const html = this.watchlists.map((wl, i) => `
            <button class="wl-tab ${i === this.currentWatchlistIndex ? 'active' : ''}" 
                    onclick="window.priceGrid.switchWatchlist(${i})">
                ${wl.icon} ${wl.name}
            </button>
        `).join('');

        this.watchlistTabs.innerHTML = html;
    }

    initWatchlistControls() {
        // Sort dropdown
        const sortSelect = document.getElementById('wl-sort');
        if (sortSelect) {
            sortSelect.addEventListener('change', (e) => {
                this.sortBy = e.target.value;
                this.renderMarketWatch();
            });
        }

        // Fetch NFO symbols from server
        this.fetchNfoSymbols();
    }

    async fetchNfoSymbols() {
        try {
            const res = await fetch('/api/nfo/symbols');
            const data = await res.json();
            if (data.symbols && data.symbols.length > 0) {
                this.watchlists[1].symbols = data.symbols;
                console.log(`📊 Loaded ${data.count} NFO symbols`);
                this.renderMarketWatch();
            }
        } catch (e) {
            console.error('Failed to fetch NFO symbols:', e);
        }
    }

    sortWatchlistData(items) {
        const sorted = [...items];
        switch (this.sortBy) {
            case 'name':
                sorted.sort((a, b) => a.symbol.localeCompare(b.symbol));
                break;
            case 'price':
                sorted.sort((a, b) => (b.ltp || 0) - (a.ltp || 0));
                break;
            case 'change':
            default:
                sorted.sort((a, b) => (a.percent_change || 0) - (b.percent_change || 0));
                break;
        }
        return this.sortAsc ? sorted.reverse() : sorted;
    }

    renderMarketWatch() {
        if (!this.marketList) return;

        const currentWL = this.watchlists[this.currentWatchlistIndex];
        let watchlistSymbols = currentWL.symbols;

        // Build list: combine watchlist symbols with their market data (if available)
        let items = watchlistSymbols.map(symbol => {
            // Find market data for this symbol
            const data = this.marketData.find(d => d.symbol === symbol);
            return {
                symbol: symbol,
                ltp: data?.ltp || 0,
                percent_change: data?.percent_change || 0,
                trend: data?.trend || '-',
                hasData: !!data
            };
        });

        // Sort
        items = this.sortWatchlistData(items);

        const html = items.map(d => `
            <div class="mw-row ${this.widgets.has(d.symbol) ? 'active-watch' : ''} ${!d.hasData ? 'no-data' : ''}" 
                 onclick="window.priceGrid.toggleWidget('${d.symbol}')">
                <div>
                    <span class="mw-sym">${d.symbol}</span>
                    <span class="mw-trend">${d.trend}</span>
                </div>
                <div>
                    <div class="mw-price">${d.hasData ? this.formatPrice(d.ltp) : '--'}</div>
                    <span class="mw-chg ${this.getChangeClass(d.percent_change)}">
                        ${d.hasData ? (d.percent_change || 0).toFixed(2) + '%' : '--'}
                    </span>
                </div>
            </div>
        `).join('');

        this.marketList.innerHTML = html || '<div class="empty-list">No symbols in watchlist</div>';
    }

    addToWatchlist(symbol, watchlistIndex = 2) {
        const wl = this.watchlists[watchlistIndex];
        if (wl && wl.editable && !wl.symbols.includes(symbol)) {
            wl.symbols.push(symbol);
            this.saveWatchlists();
            this.renderMarketWatch();
        }
    }

    removeFromWatchlist(symbol, watchlistIndex = 2) {
        const wl = this.watchlists[watchlistIndex];
        if (wl && wl.editable) {
            wl.symbols = wl.symbols.filter(s => s !== symbol);
            this.saveWatchlists();
            this.renderMarketWatch();
        }
    }

    saveWatchlists() {
        try {
            // Only save custom watchlist (index 2)
            localStorage.setItem('customWatchlist', JSON.stringify(this.watchlists[2].symbols));
        } catch (e) { console.error('Failed to save watchlists:', e); }
    }

    loadWatchlists() {
        try {
            const saved = localStorage.getItem('customWatchlist');
            if (saved) {
                this.watchlists[2].symbols = JSON.parse(saved);
            }
        } catch (e) { console.error('Failed to load watchlists:', e); }
    }


    toggleWidget(symbol) {
        if (this.widgets.has(symbol)) {
            this.closeWidget(symbol);
        } else {
            this.openWidget(symbol);
        }
        this.renderMarketWatch(); // Update active state styling
    }

    openWidget(symbol) {
        if (this.widgets.has(symbol)) return; // Already open

        // Find data in marketData to initialize
        const data = this.marketData.find(d => d.symbol === symbol) || { ltp: 0, change: 0, percent_change: 0 };
        const widget = this.createWidget(symbol, data);
        this.gridContainer.appendChild(widget);

        // Save to localStorage
        this.saveOpenWidgets();

        // If no live data, subscribe to WebSocket feed on-demand
        if (!data.ltp || data.ltp === 0) {
            this.subscribeToSymbol(symbol);
        }
    }

    async subscribeToSymbol(symbol) {
        try {
            console.log(`📡 Subscribing to ${symbol}...`);
            const res = await fetch(`/api/subscribe/${symbol}`, { method: 'POST' });
            const result = await res.json();

            if (result.status === 'ok') {
                console.log(`✅ Subscribed to ${symbol} (token: ${result.token})`);
            } else if (result.status === 'already_subscribed') {
                console.log(`ℹ️ Already subscribed to ${symbol}`);
            } else {
                console.error(`❌ Failed to subscribe to ${symbol}:`, result.message);
            }
        } catch (e) {
            console.error(`❌ Subscribe error for ${symbol}:`, e);
        }
    }

    closeWidget(symbol) {
        const widget = this.widgets.get(symbol);
        if (widget) {
            widget.remove();
            this.widgets.delete(symbol);

            // Save to localStorage
            this.saveOpenWidgets();

            // Clean up related option rows from memory/map
            // (Note: option row elements are inside the widget, so they are removed from DOM, 
            // but we should remove from this.optionRows map to prevent leaks/errors)
            for (const [key, val] of this.optionRows.entries()) {
                if (key.startsWith(symbol + '_')) {
                    this.optionRows.delete(key);
                }
            }
        }
    }

    createWidget(symbol, data) {
        const widget = document.createElement('div');
        widget.className = 'stock-widget';
        widget.dataset.symbol = symbol;

        widget.innerHTML = `
            <div class="widget-header">
                <div class="header-main">
                    <span class="header-symbol">${symbol}</span>
                    <span class="header-trend">--</span>
                </div>
                <div class="header-right">
                     <div class="header-price-row">
                        <span class="header-price">${this.formatPrice(data.ltp)}</span>
                        <span class="header-change ${this.getChangeClass(data.percent_change)}">
                            ${(data.percent_change || 0).toFixed(2)}%
                        </span>
                    </div>
                    <button class="btn-close-widget" onclick="window.priceGrid.closeWidget('${symbol}')">×</button>
                </div>
            </div>
            
            <div class="widget-actions">
                <button onclick="window.priceGrid.trade('${symbol}', 'BUY', window.priceGrid.getLotSize('${symbol}'))" class="btn-action btn-buy">BUY</button>
                <button onclick="window.priceGrid.trade('${symbol}', 'SELL', window.priceGrid.getLotSize('${symbol}'))" class="btn-action btn-sell">SELL</button>
            </div>

            <div class="widget-body">
                <table class="mini-table option-table">
                    <thead>
                        <tr>
                            <th>STRIKE</th>
                            <th>TYPE</th>
                            <th>LTP</th>
                            <th>CHG%</th>
                            <th>ACTION</th>
                        </tr>
                    </thead>
                    <tbody id="tbody-${symbol}">
                        <!-- Options injected here -->
                    </tbody>
                </table>
            </div>
        `;

        this.widgets.set(symbol, widget);
        return widget;
    }

    loadSnapshot(data) {
        // Clear old list logic
        this.marketData = [];
        // Don't clear active widgets, we want them to persist across re-connects if possible.
        // But for fresh load, we might want to auto-populate.

        const isFreshLoad = this.marketData.length === 0 && this.widgets.size === 0;

        // 1. Identify Parents (All except options)
        const parents = Object.entries(data).filter(([s, _]) => !/\d/.test(s));

        parents.forEach(([symbol, d]) => {
            if (symbol === 'BANKNIFTY') {
                this.updateHeroCard(d);
            } else {
                // Add to market data for the sidebar
                this.marketData.push({ symbol, ...d });

                // Update widget if it exists
                if (this.widgets.has(symbol)) {
                    this.updatePrice(symbol, d);
                }
            }
        });

        this.renderMarketWatch();

        // Auto-populate on first load if empty
        if (isFreshLoad && this.marketData.length > 0) {
            // Try to restore saved widgets first
            const savedWidgets = this.loadOpenWidgets();
            if (savedWidgets && savedWidgets.length > 0) {
                // Restore previously open widgets
                savedWidgets.forEach(symbol => {
                    if (this.marketData.find(d => d.symbol === symbol)) {
                        this.openWidget(symbol);
                    }
                });
            } else {
                // No saved widgets, use default top 4 movers
                const movers = [...this.marketData].sort((a, b) => Math.abs(b.percent_change) - Math.abs(a.percent_change));
                movers.slice(0, 4).forEach(m => this.openWidget(m.symbol));
            }
        }

        // 2. Process Options (populate into existing widgets)
        Object.entries(data).forEach(([symbol, d]) => {
            if (/\d/.test(symbol)) this.updatePrice(symbol, d);
        });
    }

    updatePrice(symbol, data) {
        // Always update Hero Card for BANKNIFTY
        if (symbol === 'BANKNIFTY') {
            this.updateHeroCard(data);
        }

        // Update internal cache
        const idx = this.marketData.findIndex(x => x.symbol === symbol);
        if (idx >= 0) {
            this.marketData[idx] = { ...this.marketData[idx], ...data };
            // If we are watching this list, re-render occasionally? 
            // No, rendering full market watch on every tick is expensive. 
            // relying on interval or granular updates. 
            // For now, let's update DOM of the specific row if visible? 
            // Optimization: Only re-render list periodically (done in constructor)
        }

        // If it's a parent widget that IS OPEN
        if (this.widgets.has(symbol)) {
            const widget = this.widgets.get(symbol);
            if (widget) this.updateWidgetHeader(symbol, data);
        }

        // If it's an option (contains digits)
        else if (/\d/.test(symbol)) {
            // Check if parent widget exists
            const match = symbol.match(/^([A-Z]+)/);
            const parent = match ? match[1] : null;

            if (parent && this.widgets.has(parent)) {
                if (this.optionRows.has(symbol)) {
                    this.updateOptionRow(symbol, data);
                } else {
                    this.addOptionRow(parent, symbol, data);
                }
            }
        }
    }

    updateHeroCard(data) {
        if (!this.bankniftyPrice) return;
        this.bankniftyPrice.textContent = this.formatPrice(data.ltp);
        this.bankniftyChange.textContent = `${data.change.toFixed(2)} (${data.percent_change.toFixed(2)}%)`;
        this.bankniftyChange.className = 'index-change ' + this.getChangeClass(data.percent_change);
    }

    // ... (Keep existing helper methods like formatPrice, trade, init functions)

    initModeToggle() {
        const toggle = document.getElementById('mode-toggle');
        const statusLabel = document.getElementById('mode-status');

        if (toggle && statusLabel) {
            toggle.addEventListener('change', async (e) => {
                const isPaper = !e.target.checked;
                statusLabel.textContent = isPaper ? 'Paper' : 'Real';
                statusLabel.className = isPaper ? 'toggle-state-label off' : 'toggle-state-label on';

                await fetch(`/api/mode?paper_mode=${isPaper}`, { method: 'POST' });
            });
        }
    }

    async initAutoTradeToggle() {
        const toggle = document.getElementById('auto-trade-toggle');
        const statusLabel = document.getElementById('auto-trade-status');

        if (toggle && statusLabel) {
            // Load current state from backend
            try {
                const res = await fetch('/api/auto_trade');
                const data = await res.json();
                const isEnabled = data.auto_trading_enabled || false;

                // Sync UI with backend state
                toggle.checked = isEnabled;
                statusLabel.textContent = isEnabled ? 'ON' : 'OFF';
                statusLabel.className = isEnabled ? 'toggle-state-label on' : 'toggle-state-label off';
            } catch (e) {
                console.error('Failed to load auto-trade state:', e);
            }

            // Add change event listener
            toggle.addEventListener('change', async (e) => {
                const isOn = e.target.checked;
                statusLabel.textContent = isOn ? 'ON' : 'OFF';
                statusLabel.className = isOn ? 'toggle-state-label on' : 'toggle-state-label off';

                try {
                    await fetch(`/api/auto_trade?enabled=${isOn}`, { method: 'POST' });
                    console.log(`✅ Auto-trade ${isOn ? 'enabled' : 'disabled'}`);
                } catch (err) {
                    console.error('Failed to update auto-trade:', err);
                }
            });
        }
    }

    async initSimulationControls() {
        const toggle = document.getElementById('sim-mode-toggle');
        const speedRange = document.getElementById('sim-speed-range');
        const speedValue = document.getElementById('sim-speed-value');

        // 1. Sync Logic: Fetch current state from backend
        try {
            const res = await fetch('/api/market/status');
            const data = await res.json();

            if (data && typeof data.simulation_mode !== 'undefined') {
                const isSimMode = data.simulation_mode;
                const speed = data.simulation_speed || 1.0;

                // Sync UI elements to backend state
                if (toggle) toggle.checked = isSimMode;
                if (speedRange) speedRange.value = speed;
                if (speedValue) speedValue.textContent = `${speed}x`;

                console.log(`🎮 Simulator State Synced: Mode=${isSimMode}, Speed=${speed}x`);
            }
        } catch (e) {
            console.error('Failed to sync simulation controls:', e);
        }

        // 2. Event Listeners
        if (toggle) {
            toggle.addEventListener('change', async (e) => {
                await this.setSimulationConfig(e.target.checked, 1.0);
            });
        }

        if (speedRange) {
            // Update label immediately while dragging
            speedRange.addEventListener('input', (e) => {
                if (speedValue) speedValue.textContent = `${e.target.value}x`;
            });

            // Commit change on drag end
            speedRange.addEventListener('mouseup', async (e) => {
                const speed = parseFloat(e.target.value);
                // ALWAYS read the current state of the toggle
                const enabled = document.getElementById('sim-mode-toggle').checked;
                await this.setSimulationConfig(enabled, speed);
            });

            // Handle click/change for non-drag updates
            speedRange.addEventListener('change', async (e) => {
                const speed = parseFloat(e.target.value);
                const enabled = document.getElementById('sim-mode-toggle').checked;
                await this.setSimulationConfig(enabled, speed);
            });
        }
    }

    async setSimulationConfig(enabled, speed) {
        try {
            await fetch('/api/simulation/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled, speed })
            });
        } catch (e) { console.error(e); }
    }

    async initThresholdSlider() {
        const slider = document.getElementById('threshold-slider');
        const display = document.getElementById('threshold-value');

        if (!slider || !display) return;

        // Load current threshold from backend
        try {
            const res = await fetch('/api/strategy/threshold');
            const data = await res.json();
            if (data.threshold) {
                slider.value = data.threshold;
                display.textContent = data.threshold.toFixed(1);
            }
        } catch (e) {
            console.error('Failed to load threshold:', e);
        }

        // Update display on slider move
        slider.addEventListener('input', (e) => {
            display.textContent = parseFloat(e.target.value).toFixed(1);
        });

        // Debounced API call on slider change
        let timeout;
        slider.addEventListener('change', async (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(async () => {
                const threshold = parseFloat(e.target.value);
                try {
                    await fetch(`/api/strategy/threshold?threshold=${threshold}`, {
                        method: 'POST'
                    });
                    console.log(`✅ Threshold updated to ${threshold}`);
                } catch (err) {
                    console.error('Failed to update threshold:', err);
                }
            }, 300);
        });
    }


    async initTimeframeControl() {
        const select = document.getElementById('timeframe-select');
        const display = document.getElementById('tf-value');

        if (!select || !display) return;

        // Load current timeframe
        try {
            const res = await fetch('/api/strategy/timeframe');
            const data = await res.json();
            if (data.timeframe) {
                select.value = data.timeframe;
                display.textContent = data.timeframe + 'm';
            }
        } catch (e) {
            console.error('Failed to load timeframe:', e);
        }

        // Handle Change
        select.addEventListener('change', async (e) => {
            const minutes = parseInt(e.target.value);
            display.textContent = minutes + 'm';

            try {
                const res = await fetch(`/api/strategy/timeframe?minutes=${minutes}`, { method: 'POST' });
                const data = await res.json();

                if (data.status === 'success') {
                    console.log(`✅ Timeframe set to ${minutes}m`);
                } else {
                    alert('Error: ' + data.message);
                }
            } catch (err) {
                console.error('Failed to update timeframe:', err);
            }
        });
    }

    // Keep existing helpers
    formatPrice(p) { return (p || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
    getChangeClass(v) { return v > 0 ? 'text-green' : v < 0 ? 'text-red' : 'text-gray'; }

    async testTrade() {
        try {
            const res = await fetch('/api/test_trade', { method: 'POST' });
            const data = await res.json();

            if (data.status === 'success') {
                console.log('✅ Test trade created:', data.order);

                // Immediately refresh orders to show in Activity Log
                const ordersRes = await fetch('/api/orders');
                const ordersData = await ordersRes.json();
                if (ordersData.orders) {
                    this.renderOrders(ordersData.orders);
                }

                alert(`🧪 Test trade created!\n${data.order.side} ${data.order.symbol}\nPrice: ₹${data.order.price}\nCheck Activity Log →`);
            } else {
                console.error('Test trade failed:', data.message);
                alert(`❌ Test trade failed: ${data.message}`);
            }
        } catch (e) {
            console.error('Test trade error:', e);
            alert(`❌ Error: ${e.message}`);
        }
    }

    startOrderSync() {
        // Poll every 1s for immediate feedback
        setInterval(async () => {
            // 1. Fetch Orders
            try {
                const res = await fetch('/api/orders');
                const data = await res.json();
                if (data.orders) this.renderOrders(data.orders);
            } catch (e) { console.error('Order sync error:', e); }

            // 2. Fetch Positions
            try {
                const res = await fetch('/api/positions');
                const data = await res.json();
                if (data.positions) {
                    this.renderPositions(data.positions);
                    this.updateTotalPnl(data.total_pnl);
                }
            } catch (e) { console.error('Pos sync error:', e); }

        }, 1000);
    }

    renderPositions(positions) {
        if (!this.positionsTableBody) return;

        const entries = Object.entries(positions);
        if (entries.length === 0) {
            this.positionsTableBody.innerHTML = '<tr><td colspan="9" class="empty-table">No active positions</td></tr>';
            if (this.posCountBadge) this.posCountBadge.textContent = '0';
            return;
        }

        if (this.posCountBadge) this.posCountBadge.textContent = entries.length;

        this.positionsTableBody.innerHTML = entries.map(([key, p]) => {
            // key is "SYMBOL:PRODUCT"
            const symbol = p.symbol || key.split(':')[0];
            const netQty = p.net_qty;
            const avgPrice = p.avg_price;
            const ltp = p.ltp || avgPrice; // Fallback
            const realized = p.realized_pnl || 0;
            const unrealized = (ltp - avgPrice) * netQty;
            const totalPnl = realized + unrealized;
            const invest = Math.abs(avgPrice * netQty);
            const roi = invest > 0 ? (totalPnl / invest * 100) : 0;
            const side = netQty > 0 ? "LONG" : (netQty < 0 ? "SHORT" : "CLOSED");

            // value = ltp * qty
            const value = Math.abs(ltp * netQty);

            if (netQty === 0) return ''; // Skip closed positions in active table? Or show them? 
            // Usually active positions implies non-zero. Let's filter non-zero.

            return `
                <tr>
                    <td class="font-bold">${symbol}</td>
                    <td class="${side === 'LONG' ? 'text-green' : 'text-red'}">${side}</td>
                    <td>${netQty}</td>
                    <td>${avgPrice.toFixed(2)}</td>
                    <td>${ltp.toFixed(2)}</td>
                    <td>${(value / 1000).toFixed(1)}k</td>
                    <td class="${this.getChangeClass(roi)}">${roi.toFixed(1)}%</td>
                    <td class="${this.getChangeClass(totalPnl)} font-bold">${totalPnl.toFixed(0)}</td>
                    <td>
                        <button onclick="window.priceGrid.trade('${symbol}', '${netQty > 0 ? 'SELL' : 'BUY'}', ${Math.abs(netQty)})" class="btn-xs btn-sell">EXIT</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    updateTotalPnl(val) {
        const el = document.getElementById('total-pnl');
        if (el) {
            el.textContent = `₹${(val || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            el.className = `metric-value ${this.getChangeClass(val)}`;
        }
    }

    renderOrders(orders) {
        if (!this.ordersLog) return;
        if (orders.length === 0) {
            this.ordersLog.innerHTML = '<div class="empty-log">No recent activity</div>';
            return;
        }

        this.ordersLog.innerHTML = orders.map(o => `
            <div class="order-entry ${o.status === 'FILLED' ? 'complete' : o.status === 'REJECTED' ? 'rejected' : ''}">
                <div>
                   <span style="font-weight:600; color:#ddd">${o.symbol}</span>
                   <div style="font-size:10px; color:#666">${o.status}</div>
                </div>
                <div style="text-align:right">
                   <span class="${o.side === 'BUY' ? 'text-green' : 'text-red'} font-bold">${o.side}</span>
                   <div style="font-size:10px">${o.qty} @ ${o.price}</div>
                </div>
            </div>
        `).join('');
    }

    startStatsSync() {
        // Keep syncing stats but update UI carefully
        setInterval(async () => {
            // ... fetch stats logic
        }, 5000);
    }

    async loadConfig() { /* ... */ }

    async trade(symbol, side, qty) {
        if (!confirm(`Confirm ${side} ${qty} ${symbol}?`)) return;
        if (!window.automation_test && !confirm(`Confirm ${side} ${qty} ${symbol}?`)) return;

        const product_type = this.productTypeEl ? this.productTypeEl.value : 'I';

        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, side, qty, price: 0, product_type })
            });
            const res = await response.json();
            if (res.status === 'success') {
                alert(`Order Placed: ${res.order_id || res.id}`);
            } else {
                alert(`Error: ${res.message || 'Check terminal'}`);
            }
        } catch (e) {
            alert(`Network Error: ${e}`);
        }
    }

    async cancelOrder(orderId) {
        if (!confirm(`Cancel order ${orderId}?`)) return;
        try {
            const res = await fetch(`/api/order/cancel?order_id=${orderId}`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                alert('Order Cancellation Sent');
            } else {
                alert('Cancellation Failed: ' + (data.message || 'Check logs'));
            }
        } catch (e) { alert('Network Error: ' + e); }
    }

    updateHeroCard(data) {
        if (!this.bankniftyPrice || !this.bankniftyChange) return;

        const ltp = parseFloat(data.ltp || 0);
        const change = parseFloat(data.change || 0);
        const changePercent = parseFloat(data.percent_change || 0);

        this.bankniftyPrice.textContent = this.formatPrice(ltp);
        this.bankniftyChange.innerHTML = `
            <span class="change-value ${this.getChangeClass(change)}">${this.formatChange(change)}</span>
            <span class="change-percent ${this.getChangeClass(changePercent)}">(${Math.abs(changePercent).toFixed(2)}%)</span>
        `;

        // AI Signal Update
        const signalEl = document.getElementById('ai-signal');
        if (signalEl && data.ai_signal) {
            signalEl.textContent = `AI: ${data.ai_signal}`;
            signalEl.classList.remove('hidden', 'ai-signal-buy', 'ai-signal-sell');

            if (data.ai_signal.includes('BUY')) signalEl.classList.add('ai-signal-buy');
            else if (data.ai_signal.includes('SELL')) signalEl.classList.add('ai-signal-sell');
        }

        const now = new Date();
        if (this.lastUpdate) this.lastUpdate.textContent = now.toLocaleTimeString();
    }

    updateLatency(latency) {
        if (this.latencyElement) this.latencyElement.textContent = latency + ' ms';
    }

    updateWidgetHeader(symbol, data) {
        const widget = this.widgets.get(symbol);
        if (!widget) return;

        // Update Trend
        const trendEl = widget.querySelector('.header-trend');
        if (trendEl && data.trend) trendEl.textContent = data.trend;

        // Update Price
        const priceEl = widget.querySelector('.header-price');
        if (priceEl && data.ltp) priceEl.textContent = this.formatPrice(data.ltp);

        // Update Change
        const changeEl = widget.querySelector('.header-change');
        if (changeEl && data.percent_change !== undefined) {
            changeEl.textContent = `${data.percent_change.toFixed(2)}%`;
            changeEl.className = `header-change ${this.getChangeClass(data.percent_change)}`;
        }
    }

    addOptionRow(parent, symbol, data) {
        const tbody = document.getElementById(`tbody-${parent}`);
        if (!tbody || this.optionRows.has(symbol)) return;

        const row = document.createElement('tr');
        row.id = `opt-${symbol}`;
        row.innerHTML = this.getOptionRowHTML(symbol, data);

        tbody.appendChild(row);
        this.optionRows.set(symbol, row);
    }

    updateOptionRow(symbol, data) {
        const row = this.optionRows.get(symbol);
        if (!row) return;
        row.innerHTML = this.getOptionRowHTML(symbol, data);
    }

    getOptionRowHTML(symbol, data) {
        // Extract type (C/P) and strike from symbol like INDUSINDBK27JAN26C900
        const parsed = this.parseOptionSymbol(symbol);
        const type = parsed.type;  // CE or PE
        const strike = parsed.strike;
        const ltp = data.ltp || 0;
        const change = data.percent_change || 0;
        const typeClass = type === 'CE' ? 'opt-call' : 'opt-put';
        const changeSign = change >= 0 ? '+' : '';

        return `
            <td class="opt-strike-cell">
                <span class="opt-strike-value">${strike}</span>
            </td>
            <td class="opt-type-cell">
                <span class="opt-type-badge ${typeClass}">${type}</span>
            </td>
            <td class="opt-ltp">
                <span class="ltp-value">₹${this.formatPrice(ltp)}</span>
            </td>
            <td class="opt-change ${this.getChangeClass(change)}">
                ${changeSign}${change.toFixed(1)}%
            </td>
            <td class="actions-cell">
                 <button onclick="window.priceGrid.trade('${symbol}', 'BUY', window.priceGrid.getLotSize('${symbol}'))" class="btn-xs btn-buy">BUY</button>
                 <button onclick="window.priceGrid.trade('${symbol}', 'SELL', window.priceGrid.getLotSize('${symbol}'))" class="btn-xs btn-sell">SELL</button>
            </td>
        `;
    }

    parseOptionSymbol(symbol) {
        // Parse symbols like: INDUSINDBK27JAN26C900 or BANKNIFTY27JAN26P60000
        // Format: SYMBOL + EXPIRY + C/P + STRIKE
        const match = symbol.match(/([CP])(\d+)$/i);
        if (match) {
            const typeChar = match[1].toUpperCase();
            return {
                type: typeChar === 'C' ? 'CE' : 'PE',
                strike: match[2]
            };
        }
        // Fallback
        return { type: '??', strike: '---' };
    }

    extractStrike(symbol) {
        return this.parseOptionSymbol(symbol).strike;
    }

    getLotSize(symbol) {
        if (/\d/.test(symbol)) {
            const input = document.getElementById('opt-lots');
            const lots = input ? (parseInt(input.value) || 1) : 1;

            let mult = 1;
            if (symbol.includes('BANKNIFTY')) mult = 15;
            else if (symbol.includes('NIFTY')) mult = 50;

            return lots * mult;
        } else {
            const input = document.getElementById('stock-qty');
            return input ? (parseInt(input.value) || 1) : 1;
        }
    }

    startFpsCounter() {
        if (!this.fpsElement) return;
        setInterval(() => {
            const now = Date.now();
            const elapsed = (now - this.lastFpsUpdate) / 1000;
            this.fps = Math.round(this.updateCount / elapsed);

            this.fpsElement.textContent = this.fps + ' fps';

            // Reset counters
            this.updateCount = 0;
            this.lastFpsUpdate = now;
        }, 1000);
    }

    // Helper methods
    formatChange(change) {
        const sign = change >= 0 ? '+' : '';
        return `${sign}${change.toFixed(2)}`;
    }

    formatPercentChange(pct) {
        const sign = pct >= 0 ? '+' : '';
        return `${sign}${pct.toFixed(2)}%`;
    }

    handleOverscope(callback, ...args) {
        try {
            return callback(...args);
        } catch (e) {
            console.error('Overscope error:', e);
            return '';
        }
    }

    // Widget persistence
    saveOpenWidgets() {
        const openSymbols = Array.from(this.widgets.keys());
        try {
            localStorage.setItem('openWidgets', JSON.stringify(openSymbols));
        } catch (e) {
            console.error('Failed to save widgets:', e);
        }
    }

    loadOpenWidgets() {
        try {
            const saved = localStorage.getItem('openWidgets');
            return saved ? JSON.parse(saved) : null;
        } catch (e) {
            console.error('Failed to load widgets:', e);
            return null;
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 Page Loaded. Initializing PriceGrid...");

    // 1. Init PriceGrid (UI)
    window.priceGrid = new PriceGrid();
    const grid = window.priceGrid;

    // 2. Init WebSocket (Data Feed)
    if (typeof PriceWebSocket !== 'undefined') {
        // Use relative URL for WebSocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/prices`;

        const ws = new PriceWebSocket(wsUrl);

        ws.onConnected = () => {
            console.log("✅ WebSocket Connected!");
            const statusIndicator = document.getElementById('status-indicator');
            const statusText = document.getElementById('status-text');
            if (statusIndicator) {
                statusIndicator.classList.remove('disconnected');
                statusIndicator.classList.add('connected');
            }
            if (statusText) statusText.textContent = 'Connected';
        };

        ws.onDisconnected = () => {
            console.log("⚠️ WebSocket Disconnected!");
            const statusIndicator = document.getElementById('status-indicator');
            const statusText = document.getElementById('status-text');
            if (statusIndicator) {
                statusIndicator.classList.remove('connected');
                statusIndicator.classList.add('disconnected');
            }
            if (statusText) statusText.textContent = 'Disconnected';
        };

        ws.onSnapshot = (data) => {
            grid.loadSnapshot(data);
        };

        ws.onPriceUpdate = (symbol, data) => {
            grid.updatePrice(symbol, data);
            grid.updateCount++; // Increment FPS counter
        };

        ws.onLatencyUpdate = (latency) => {
            if (grid.updateLatency) grid.updateLatency(latency);
        };

        ws.connect();

        // Expose for debugging
        window.priceWS = ws;
    } else {
        console.error("❌ PriceWebSocket class not found! Check stylesheet inclusion.");
    }
});
