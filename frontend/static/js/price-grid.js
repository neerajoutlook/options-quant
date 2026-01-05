/**
 * Ultra-fast Price Grid Rendering
 * Optimized for HFT with minimal DOM manipulation
 */

class PriceGrid {
    constructor() {
        this.gridContainer = document.getElementById('widget-grid');
        this.widgets = new Map(); // symbol -> widget element (for underlying)
        this.optionRows = new Map(); // optionSymbol -> row element
        this.lastPrices = new Map(); // symbol -> last price (for flash detection)

        // Performance tracking
        this.updateCount = 0;
        this.lastFpsUpdate = Date.now();
        this.fps = 0;

        // Bank Nifty main elements
        this.bankniftyPrice = document.getElementById('banknifty-price');
        this.bankniftyChange = document.getElementById('banknifty-change');
        this.lastUpdate = document.getElementById('last-update');

        // Metrics elements
        this.fpsElement = document.getElementById('fps');
        this.latencyElement = document.getElementById('latency');
        this.symbolCountElement = document.getElementById('symbol-count');

        // Positions and Orders
        this.positions = {};
        this.totalPnlElement = document.getElementById('total-pnl');
        this.ordersLog = document.getElementById('orders-log');
        this.positionsTableBody = document.getElementById('positions-table-body');
        this.orderCountBadge = document.getElementById('order-count');

        // Column Lists
        this.bearsList = document.getElementById('bears-list');
        this.bullsList = document.getElementById('bulls-list');

        this.startPositionSync();
        this.startOrderSync();
        this.startStatsSync();

        // Config
        this.lotSizes = { 'BANKNIFTY': 15, 'NIFTY': 50 }; // Defaults
        this.loadConfig();

        // Trading Mode
        this.paperMode = true;
        this.autoTradeEnabled = false;
        this.modeToggle = document.getElementById('mode-toggle');
        this.modeStatus = document.getElementById('mode-status');
        this.autoTradeToggle = document.getElementById('auto-trade-toggle');
        this.autoTradeStatus = document.getElementById('auto-trade-status');
        this.aiSignalBadge = document.getElementById('ai-signal');
        this.globalModeBadge = document.getElementById('global-mode-badge');
        this.productTypeEl = document.getElementById('product-type');

        this.initModeToggle();
        this.initAutoTradeToggle();
        this.initSimulationControls();

        // History Controls
        this.historyDateInput = document.getElementById('history-date');
        this.btnClearHistory = document.getElementById('btn-clear-history');

        // Start Sorting interval
        setInterval(() => this.sortColumns(), 3000);

        if (this.historyDateInput) {
            this.historyDateInput.value = new Date().toISOString().split('T')[0];
            this.initHistoryControls();
        }

        // Start FPS counter
        this.startFpsCounter();
    }

    async initModeToggle() {
        if (!this.modeToggle) return;

        // Fetch initial mode
        try {
            const res = await fetch('/api/mode');
            const data = await res.json();
            this.setPaperMode(data.paper_trading_mode);
        } catch (e) { console.error('Mode Fetch Error', e); }

        // Handle toggle change
        // Handle toggle change
        this.modeToggle.addEventListener('change', async () => {
            const isChecked = this.modeToggle.checked;
            const newPaperMode = !isChecked; // Checked = REAL (paper=false), Unchecked = PAPER (paper=true)

            // Safety confirmation for Real mode
            if (isChecked && !confirm("⚠️ SWITCH TO REAL TRADING?\n\nThis will place REAL orders at Shoonya.")) {
                this.modeToggle.checked = false; // Revert to Paper
                return;
            }

            try {
                const res = await fetch(`/api/mode?paper_mode=${newPaperMode}`, { method: 'POST' });
                const data = await res.json();
                this.setPaperMode(data.paper_trading_mode);
            } catch (e) {
                console.error('Mode Update Error', e);
                alert('Failed to update trading mode');
            }
        });
    }

    setPaperMode(isPaper) {
        this.paperMode = isPaper;
        if (this.modeToggle) this.modeToggle.checked = !isPaper; // Checked = REAL
        if (this.modeStatus) {
            this.modeStatus.textContent = isPaper ? 'Paper' : 'REAL';
            this.modeStatus.className = 'mode-status ' + (isPaper ? 'paper' : 'real');
        }
        if (this.globalModeBadge) {
            this.globalModeBadge.textContent = isPaper ? 'PAPER' : 'REAL';
            this.globalModeBadge.className = 'mode-badge ' + (isPaper ? 'paper' : 'real');
        }
    }

    async initAutoTradeToggle() {
        if (!this.autoTradeToggle) return;

        // Fetch initial state
        try {
            const res = await fetch('/api/auto_trade');
            const data = await res.json();
            this.setAutoTrade(data.auto_trading_enabled);
        } catch (e) { console.error('Failed to fetch auto-trade status', e); }

        this.autoTradeToggle.addEventListener('change', async (e) => {
            const enabled = e.target.checked;
            try {
                const res = await fetch(`/api/auto_trade?enabled=${enabled}`, { method: 'POST' });
                const data = await res.json();
                this.setAutoTrade(data.auto_trading_enabled);
            } catch (err) {
                console.error('Failed to set auto-trade', err);
                e.target.checked = !enabled; // Revert
            }
        });
    }

    setAutoTrade(enabled) {
        this.autoTradeEnabled = enabled;
        if (this.autoTradeToggle) this.autoTradeToggle.checked = enabled;
        if (this.autoTradeStatus) {
            this.autoTradeStatus.textContent = enabled ? 'ON' : 'OFF';
            this.autoTradeStatus.className = 'mode-status ' + (enabled ? 'enabled' : 'disabled');
        }
    }

    initSimulationControls() {
        this.simToggle = document.getElementById('sim-mode-toggle');
        this.simSpeedControls = document.getElementById('sim-speed-controls');
        this.simSpeedRadios = document.getElementsByName('sim-speed');

        if (!this.simToggle) return;

        // Toggle Event
        this.simToggle.addEventListener('change', async (e) => {
            const enabled = e.target.checked;
            const speed = this.getSimSpeed();
            await this.setSimulationConfig(enabled, speed);
        });

        // Speed Radio Events
        if (this.simSpeedRadios) {
            this.simSpeedRadios.forEach(radio => {
                radio.addEventListener('change', async (e) => {
                    const enabled = this.simToggle.checked;
                    // Only update if simulator is ON (or maybe allowed even if off? Logic says yes)
                    const speed = parseFloat(e.target.value);
                    await this.setSimulationConfig(enabled, speed);
                });
            });
        }
    }

    getSimSpeed() {
        let speed = 1.0;
        if (this.simSpeedRadios) {
            this.simSpeedRadios.forEach(r => {
                if (r.checked) speed = parseFloat(r.value);
            });
        }
        return speed;
    }

    async setSimulationConfig(enabled, speed) {
        try {
            await fetch('/api/simulation/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled, speed })
            });
            // Controls visibility update handled by updateStats which runs every 5s, 
            // but for responsiveness we can update UI immediately too
            this.updateSimUI(enabled, speed);
        } catch (e) {
            console.error('Sim Config Error', e);
            alert('Failed to update Simulation settings');
            // Revert UI if needed?
        }
    }

    updateSimUI(enabled, speed) {
        if (this.simToggle) this.simToggle.checked = enabled;
        if (this.simSpeedControls) {
            // Show speed controls only if enabled
            this.simSpeedControls.classList.toggle('hidden', !enabled);
        }
        if (this.simSpeedRadios) {
            this.simSpeedRadios.forEach(r => {
                if (Math.abs(parseFloat(r.value) - speed) < 0.1) r.checked = true;
            });
        }
    }

    startStatsSync() {
        this.updateStats(); // Initial fetch
        setInterval(() => this.updateStats(), 5000);
    }

    async updateStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();

            // Strategy Badges
            const badgeHedged = document.getElementById('badge-hedged');
            const badgeStraddle = document.getElementById('badge-straddle');
            if (badgeHedged) badgeHedged.classList.toggle('hidden', !data.hedged_mode);
            if (badgeStraddle) badgeStraddle.classList.toggle('hidden', !data.straddle_mode);

            const badgeSim = document.getElementById('badge-simulator');
            if (badgeSim) badgeSim.classList.toggle('hidden', !data.simulation_mode);

            // Sync Simulator UI Controls
            this.updateSimUI(data.simulation_mode, data.simulation_speed);

            // Daily Stop Metric
            const dailyStopEl = document.getElementById('daily-stop');
            if (dailyStopEl) dailyStopEl.textContent = `₹${data.daily_loss_limit}`;

            // Sync Auto Trade status (Backend might disable it via Hard Stop)
            if (this.autoTradeEnabled !== data.auto_trade_enabled) {
                this.setAutoTrade(data.auto_trade_enabled);
            }
        } catch (e) { console.warn('Stats Sync Error', e); }
    }

    initHistoryControls() {
        if (this.historyDateInput) {
            this.historyDateInput.addEventListener('change', () => {
                this.fetchOrders(this.historyDateInput.value);
            });
        }
        if (this.btnClearHistory) {
            this.btnClearHistory.addEventListener('click', () => {
                this.clearHistory(this.historyDateInput.value);
            });
        }
    }

    async fetchOrders(date) {
        try {
            const res = await fetch(`/api/orders?date=${date}`);
            const data = await res.json();
            if (data.orders) {
                this.renderOrders(data.orders);
            }
        } catch (e) { console.error('Failed to fetch historical orders', e); }
    }

    async clearHistory(date) {
        if (!confirm(`Clear all history for ${date}? This cannot be undone.`)) return;
        try {
            const res = await fetch(`/api/orders/clear?date=${date}`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                alert(data.message);
                this.fetchOrders(date); // Refresh UI
            } else {
                alert('Clear failed: ' + data.message);
            }
        } catch (e) { alert('Clear failed: ' + e); }
    }

    startPositionSync() {
        this.panicBtn = document.getElementById('btn-panic');

        setInterval(async () => {
            try {
                const response = await fetch('/api/positions');
                const data = await response.json();
                if (data.positions) {
                    this.positions = data.positions;
                    this.updateTotalPnl(data.total_pnl || 0);
                    this.renderPositions(data.positions);

                    // Toggle Panic Button
                    const hasPositions = Object.values(this.positions).some(p => p.net_qty !== 0);
                    if (this.panicBtn) {
                        this.panicBtn.disabled = !hasPositions;
                        this.panicBtn.style.opacity = hasPositions ? '1' : '0.5';
                        this.panicBtn.style.cursor = hasPositions ? 'pointer' : 'not-allowed';
                    }
                }
            } catch (e) { console.error('Pos Sync Error', e); }
        }, 1000); // 1 sec sync
    }

    renderPositions(positions) {
        if (!this.positionsTableBody) return;

        const keys = Object.keys(positions);
        const filteredKeys = keys.filter(k => positions[k].net_qty !== 0);

        if (filteredKeys.length === 0) {
            this.positionsTableBody.innerHTML = '<tr><td colspan="7" class="empty-table">No active trades</td></tr>';
            return;
        }

        this.positionsTableBody.innerHTML = filteredKeys.map(key => {
            const pos = positions[key];
            const [symbol, product] = key.split(':');
            const side = pos.net_qty > 0 ? 'BUY' : 'SELL';
            const sideClass = pos.net_qty > 0 ? 'side-buy' : 'side-sell';
            const pnlClass = pos.unrealized_pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
            const ltp = pos.ltp || pos.avg_price;

            return `
                <tr>
                    <td>${pos.entry_time || '<span style="opacity:0.3">Live</span>'}</td>
                    <td><strong>${symbol}</strong></td>
                    <td><span class="side-badge ${sideClass}">${side}</span></td>
                    <td>${Math.abs(pos.net_qty)}</td>
                    <td>${this.formatPrice(pos.avg_price)}</td>
                    <td>${this.formatPrice(ltp)}</td>
                    <td class="${pnlClass}">${pos.unrealized_pnl >= 0 ? '+' : ''}${Math.round(pos.unrealized_pnl)}</td>
                </tr>
            `;
        }).join('');
    }

    startOrderSync() {
        setInterval(async () => {
            // Only sync if viewing today's date
            const today = new Date().toISOString().split('T')[0];
            const viewingToday = !this.historyDateInput || this.historyDateInput.value === today;
            if (!viewingToday) return;

            try {
                const res = await fetch('/api/orders');
                const data = await res.json();
                if (data.orders) {
                    this.renderOrders(data.orders);
                }
            } catch (e) { console.error('Order Sync Error', e); }
        }, 1500); // 1.5 sec sync
    }

    renderOrders(orders) {
        if (!this.ordersLog) return;

        if (orders.length === 0) {
            this.ordersLog.innerHTML = '<div class="empty-log">No recent orders</div>';
            return;
        }

        if (this.orderCountBadge) this.orderCountBadge.textContent = orders.length;

        // Simple render (only if changed? for now just recreate as order count is low)
        this.ordersLog.innerHTML = orders.map(order => {
            const isCancellable = ['PLACED', 'PENDING', 'GTT_PLACED'].includes(order.status);
            return `
                <div class="order-item ${order.side?.toLowerCase() || ''}">
                    <div>
                        <span class="order-symbol">${order.symbol}</span>
                        <span class="order-status text-xs">${order.status}</span>
                        ${isCancellable ? `<button onclick="window.priceGrid.cancelOrder('${order.id}')" class="order-cancel-btn">Cancel</button>` : ''}
                    </div>
                    <div class="order-details">
                        <span>${order.side || 'UPD'} ${order.qty || '-'} @ ${this.formatPrice(order.price || 0)}</span>
                        <span class="text-xs text-gray-500">${new Date(order.timestamp).toLocaleTimeString()}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    updateTotalPnl(amount) {
        if (!this.totalPnlElement) return;
        this.totalPnlElement.textContent = `₹${amount.toFixed(2)}`;
        this.totalPnlElement.className = 'metric-value ' + (amount >= 0 ? 'pnl-green' : 'pnl-red');
    }

    async loadConfig() {
        try {
            const res = await fetch('/api/config');
            const config = await res.json();
            if (config.lot_sizes) {
                this.lotSizes = config.lot_sizes;
            }
            console.log('Loaded Config:', this.lotSizes);
        } catch (e) {
            console.error('Config Load Error:', e);
        }
    }



    updateCell(cell, content, className = null) {
        if (cell.textContent !== content) {
            cell.textContent = content;
        }
        if (className) {
            cell.className = className;
        }
    }

    formatPrice(price) {
        return price.toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    formatChange(change) {
        return (change >= 0 ? '+' : '') + change.toFixed(2);
    }

    formatPercent(percent) {
        return (percent >= 0 ? '+' : '') + percent.toFixed(2) + '%';
    }

    formatVolume(volume) {
        if (volume >= 1000000) {
            return (volume / 1000000).toFixed(1) + 'M';
        } else if (volume >= 1000) {
            return (volume / 1000).toFixed(1) + 'K';
        }
        return volume.toString();
    }

    getChangeClass(value) {
        if (value > 0) return 'positive';
        if (value < 0) return 'negative';
        return 'neutral';
    }

    loadSnapshot(data) {
        if (this.bearsList) this.bearsList.innerHTML = '';
        if (this.bullsList) this.bullsList.innerHTML = '';
        this.widgets.clear();
        this.optionRows.clear();

        // 1. Identify Parents (Underlying)
        const parents = Object.keys(data).filter(s => !/\d/.test(s) && !s.includes('CE') && !s.includes('PE'));

        // Process all symbols
        Object.entries(data).forEach(([symbol, priceData]) => {
            if (parents.includes(symbol)) {
                if (!this.widgets.has(symbol)) {
                    this.createWidget(symbol, priceData);
                }
                this.updatePrice(symbol, priceData);
            } else {
                // It's an option, find parent
                const match = symbol.match(/^([A-Z]+)/);
                const parent = match ? match[1] : symbol;

                if (this.widgets.has(parent)) {
                    this.addOptionRow(parent, symbol, priceData);
                }
            }
        });
        this.updateSymbolCount();
    }

    updatePrice(symbol, data) {
        // Always update Hero Card for BANKNIFTY
        if (symbol === 'BANKNIFTY') {
            this.updateHeroCard(data);
        }

        // If it's a parent widget
        if (this.widgets.has(symbol)) {
            const widget = this.widgets.get(symbol);
            this.updateWidgetHeader(symbol, data);

            // Dynamic column movement
            const pct = data.percent_change || 0;
            const targetColumn = data.percent_change >= 0 ? this.bullsList : this.bearsList;
            if (widget.parentElement !== targetColumn && targetColumn) {
                targetColumn.appendChild(widget);
            }
            widget.dataset.pct = pct; // For sorting
        }
        // If it's an existing option row
        else if (this.optionRows.has(symbol)) {
            this.updateOptionRow(symbol, data);
        }
        // If it's a NEW option (not in rows yet)
        else if (/\d/.test(symbol) || symbol.includes('CE') || symbol.includes('PE')) {
            // Try to find parent
            const match = symbol.match(/^([A-Z]+)/);
            const parent = match ? match[1] : null;

            if (parent && this.widgets.has(parent)) {
                // Initial creation handling
                this.addOptionRow(parent, symbol, data);
            }
        }
    }

    sortColumns() {
        [this.bullsList, this.bearsList].forEach(list => {
            if (!list) return;
            const items = Array.from(list.children);
            if (items.length < 2) return;

            items.sort((a, b) => {
                const valA = parseFloat(a.dataset.pct || 0);
                const valB = parseFloat(b.dataset.pct || 0);
                // For bulls, descending. For bears, ascending (most bearish first)
                if (list === this.bullsList) return valB - valA;
                return valA - valB;
            });

            // Only append if order changed to save DOM cycles
            items.forEach((item, index) => {
                if (list.children[index] !== item) {
                    list.appendChild(item);
                }
            });
        });
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
                <div class="header-price-row">
                    <span class="header-price">--</span>
                    <span class="header-change">--</span>
                </div>
            </div>
            
            <div class="widget-actions">
                <button onclick="window.priceGrid.trade('${symbol}', 'BUY', window.priceGrid.getLotSize('${symbol}'))" class="btn-action btn-buy">BUY</button>
                <button onclick="window.priceGrid.trade('${symbol}', 'SELL', window.priceGrid.getLotSize('${symbol}'))" class="btn-action btn-sell">SELL</button>
                <button onclick="window.priceGrid.trade('${symbol}', 'EXIT', 0)" class="btn-action btn-exit">EXIT</button>
            </div>

            <div class="widget-body">
                <table class="mini-table">
                    <thead>
                        <tr>
                            <th>Option</th>
                            <th>LTP</th>
                            <th>% Chg</th>
                            <th>Vol</th>
                            <th>P&L</th>
                            <th>Act</th>
                        </tr>
                    </thead>
                    <tbody id="tbody-${symbol}"></tbody>
                </table>
            </div>
        `;

        this.widgets.set(symbol, widget);
        return widget;
    }

    updateWidgetHeader(symbol, data) {
        const widget = this.widgets.get(symbol);
        const ltpEl = widget.querySelector('.header-price');
        const changeEl = widget.querySelector('.header-change');

        const ltp = parseFloat(data.ltp || 0);
        const change = parseFloat(data.change || 0);
        const changePercent = parseFloat(data.percent_change || 0);

        ltpEl.textContent = this.formatPrice(ltp);
        changeEl.textContent = `${this.formatChange(change)} (${Math.abs(changePercent).toFixed(2)}%)`;
        changeEl.className = 'header-change ' + this.getChangeClass(changePercent);

        // Update Trend/Macro
        const trendEl = widget.querySelector('.header-trend');
        const macro = data.macro || {};
        const trendText = data.trend || '-';
        const macroText = macro.trend ? macro.trend[0] : '-';

        trendEl.innerHTML = `
            <span class="${trendText === 'BULLISH' ? 'text-green-400' : trendText === 'BEARISH' ? 'text-red-400' : 'text-gray-500'}">${trendText}</span> 
            <span class="text-xs text-gray-600">|</span> 
            <span class="${macro.trend === 'BULLISH' ? 'text-green-400' : macro.trend === 'BEARISH' ? 'text-red-400' : 'text-gray-500'}">${macroText}</span>
        `;
    }

    addOptionRow(parent, symbol, data) {
        const tbody = document.getElementById(`tbody-${parent}`);
        if (!tbody) return;

        const row = document.createElement('tr');
        row.id = `row-${symbol}`;

        // Shorten option name for display (e.g. HDFCBANK27JAN26C1000 -> 27JAN 1000 CE)
        // Adjust regex based on expected naming
        let displayName = symbol.replace(parent, '');

        row.innerHTML = `
            <td>${displayName}</td>
            <td class="opt-ltp text-right">--</td>
            <td class="opt-pct text-right">--</td>
            <td class="opt-vol text-right">--</td>
            <td class="opt-pnl text-right">--</td>
            <td class="opt-actions">
                <button onclick="window.priceGrid.trade('${symbol}', 'BUY', window.priceGrid.getLotSize('${symbol}'))" class="btn-trade btn-buy">B</button>
                <button onclick="window.priceGrid.trade('${symbol}', 'SELL', window.priceGrid.getLotSize('${symbol}'))" class="btn-trade btn-sell">S</button>
                <button onclick="window.priceGrid.trade('${symbol}', 'EXIT', 0)" class="btn-trade btn-exit">X</button>
            </td>
        `;

        tbody.appendChild(row);
        this.optionRows.set(symbol, row);
        this.updateOptionRow(symbol, data);
    }

    updateOptionRow(symbol, data) {
        const row = this.optionRows.get(symbol);
        const ltp = parseFloat(data.ltp || 0);
        const change = parseFloat(data.change || 0);
        const changePercent = parseFloat(data.percent_change || 0);

        // Update cells directly
        row.querySelector('.opt-ltp').textContent = this.formatPrice(ltp);

        const pctEl = row.querySelector('.opt-pct');
        pctEl.textContent = `${changePercent.toFixed(1)}%`;
        pctEl.className = 'opt-pct ' + this.getChangeClass(changePercent);

        row.querySelector('.opt-vol').textContent = this.formatVolume(data.volume);

        // P&L (Sum across all product types for this symbol)
        let totalPnl = 0;
        let hasNetQty = false;

        Object.keys(this.positions).forEach(key => {
            if (key.startsWith(symbol + ':') || key === symbol) {
                const pos = this.positions[key];
                totalPnl += (pos.unrealized_pnl || 0);
                if (pos.net_qty) hasNetQty = true;
            }
        });

        const pnlEl = row.querySelector('.opt-pnl');
        pnlEl.textContent = hasNetQty ? Math.round(totalPnl) : '-';
        pnlEl.className = 'opt-pnl font-mono ' + (totalPnl >= 0 ? 'text-green-400' : 'text-red-400');
    }

    updateSymbolCount() {
        this.symbolCountElement.textContent = this.widgets.size + this.optionRows.size;
    }

    getLotSize(symbol) {
        // Determine if Option or Stock
        const isOption = /\d/.test(symbol) || symbol.includes('CE') || symbol.includes('PE');
        let multiplier = 1;

        if (isOption) {
            const input = document.getElementById('qty-option');
            if (input) multiplier = parseInt(input.value) || 1;

            // Base logic: BANKNIFTY -> 15, NIFTY -> 50
            let base = 1;
            if (symbol.includes('BANKNIFTY')) base = this.lotSizes['BANKNIFTY'] || 15;
            else if (symbol.includes('NIFTY')) base = this.lotSizes['NIFTY'] || 50;
            else base = 1; // Default for stock options if not in config

            return base * multiplier;
        } else {
            // Stock Logic
            const input = document.getElementById('qty-stock');
            if (input) multiplier = parseInt(input.value) || 1;
            return 1 * multiplier;
        }
    }

    async panicExit() {
        if (!confirm("🔥 ARE YOU SURE? THIS WILL CLOSE ALL POSITIONS!")) return;
        try {
            await fetch('/api/panic', { method: 'POST' });
            alert('Panic Exit Triggered!');
        } catch (e) { alert('Panic Exit Failed: ' + e); }
    }

    async trade(symbol, side, qty) {
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
        this.latencyElement.textContent = latency + ' ms';
    }

    startFpsCounter() {
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
}

// Initialize on page load
// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 Page Loaded. Initializing PriceGrid...");
    try {
        const grid = new PriceGrid();
        window.priceGrid = grid; // Global access

        // Status indicators
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');

        // Check WebSocket Class
        if (typeof PriceWebSocket === 'undefined') {
            console.error("❌ PriceWebSocket Class is NOT defined. Check websocket.js loading.");
            if (statusText) statusText.textContent = "Script Error: websocket.js";
            if (statusIndicator) statusIndicator.classList.add('disconnected');
            return;
        }

        // Connect to WebSocket
        const wsUrl = `ws://${window.location.host}/ws/prices`;
        console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);

        const ws = new PriceWebSocket(wsUrl);
        window.priceWS = ws; // Global access

        ws.onConnected = () => {
            console.log("✅ WebSocket Connected!");
            if (statusIndicator) {
                statusIndicator.classList.remove('disconnected');
                statusIndicator.classList.add('connected');
            }
            if (statusText) statusText.textContent = 'Connected';
        };

        ws.onDisconnected = () => {
            console.log("⚠️ WebSocket Disconnected!");
            if (statusIndicator) {
                statusIndicator.classList.remove('connected');
                statusIndicator.classList.add('disconnected');
            }
            if (statusText) statusText.textContent = 'Disconnected';
        };

        ws.onSnapshot = (data) => {
            console.log('📦 Snapshot:', Object.keys(data).length, 'symbols');
            grid.loadSnapshot(data);
        };

        ws.onPriceUpdate = (symbol, data) => {
            grid.updatePrice(symbol, data);
        };

        ws.onLatencyUpdate = (latency) => {
            grid.updateLatency(latency);
        };

        ws.connect();

    } catch (e) {
        console.error("❌ Critical Initialization Error:", e);
        alert("Dashboard Error: " + e.message);
    }
});
