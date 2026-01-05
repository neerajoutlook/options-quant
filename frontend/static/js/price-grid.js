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
        this.startPositionSync();

        // Config
        this.lotSizes = { 'BANKNIFTY': 15, 'NIFTY': 50 }; // Defaults
        this.loadConfig();

        // Start FPS counter
        this.startFpsCounter();
    }

    startPositionSync() {
        this.panicBtn = document.getElementById('btn-panic');

        setInterval(async () => {
            try {
                const response = await fetch('/api/positions');
                const data = await response.json();
                if (data.positions) {
                    this.positions = data.positions;
                    this.updateTotalPnl(data.total_pnl);

                    // Toggle Panic Button
                    const hasPositions = Object.keys(this.positions).length > 0;
                    if (this.panicBtn) {
                        this.panicBtn.disabled = !hasPositions;
                        this.panicBtn.style.opacity = hasPositions ? '1' : '0.5';
                        this.panicBtn.style.cursor = hasPositions ? 'pointer' : 'not-allowed';
                    }
                }
            } catch (e) { console.error('Pos Sync Error', e); }
        }, 1000); // 1 sec sync
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


    async panicExit() {
        if (!confirm("🔥 ARE YOU SURE? THIS WILL CLOSE ALL POSITIONS!")) return;
        try {
            await fetch('/api/panic', { method: 'POST' });
            alert('Panic Exit Triggered!');
        } catch (e) { alert('Panic Exit Failed: ' + e); }
    }

    async trade(symbol, side, qty) {
        if (!confirm(`Confirm ${side} ${qty} ${symbol}?`)) return;

        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, side, qty, price: 0 })
            });
            const res = await response.json();
            if (res.status === 'success') {
                alert(`Order Placed: ${res.order_id}`);
            } else {
                alert(`Error: ${res.message}`);
            }
        } catch (e) {
            alert(`Network Error: ${e}`);
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
        this.gridContainer.innerHTML = '';
        this.widgets.clear();
        this.optionRows.clear();

        // 1. Identify Parents (Underlying)
        const parents = Object.keys(data).filter(s => !/\d/.test(s) && !s.includes('CE') && !s.includes('PE'));

        // Sort parents alphabetically
        parents.sort().forEach(symbol => {
            this.createWidget(symbol, data[symbol]);
        });

        // 2. Process all symbols to populate widgets or tables
        Object.entries(data).forEach(([symbol, priceData]) => {
            if (this.widgets.has(symbol)) {
                this.updateWidgetHeader(symbol, priceData);
                if (symbol === 'BANKNIFTY') this.updateHeroCard(priceData);
            } else {
                // It's an option, find parent
                const match = symbol.match(/^([A-Z]+)/);
                const parent = match ? match[1] : symbol;

                // Special handling if parent widget exists
                if (this.widgets.has(parent)) {
                    this.addOptionRow(parent, symbol, priceData);
                }
            }
        });
        this.updateSymbolCount();
    }

    updatePrice(symbol, data) {
        // If it's a parent widget
        if (this.widgets.has(symbol)) {
            this.updateWidgetHeader(symbol, data);
            if (symbol === 'BANKNIFTY') this.updateHeroCard(data);
        }
        // If it's an option row
        else if (this.optionRows.has(symbol)) {
            this.updateOptionRow(symbol, data);
        }
    }

    createWidget(symbol, data) {
        const widget = document.createElement('div');
        widget.className = 'stock-widget';
        widget.dataset.symbol = symbol;

        widget.innerHTML = `
            <div class="widget-header">
                <div class="header-left">
                    <div class="header-symbol">${symbol}</div>
                    <div class="header-price">--</div>
                    <div class="header-change">--</div>
                    <div class="header-trend" style="font-size: 0.8rem; margin-left: 10px;">--</div>
                </div>
                <div class="actions-cell">
                    <button onclick="window.priceGrid.trade('${symbol}', 'BUY', window.priceGrid.getLotSize('${symbol}'))" class="btn-trade btn-buy" title="Buy">B</button>
                    <button onclick="window.priceGrid.trade('${symbol}', 'SELL', window.priceGrid.getLotSize('${symbol}'))" class="btn-trade btn-sell" title="Sell">S</button>
                    <button onclick="window.priceGrid.trade('${symbol}', 'EXIT', 0)" class="btn-trade btn-exit" title="Close Position">X</button>
                </div>
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

        this.gridContainer.appendChild(widget);
        this.widgets.set(symbol, widget);
    }

    updateWidgetHeader(symbol, data) {
        const widget = this.widgets.get(symbol);
        const ltpEl = widget.querySelector('.header-price');
        const changeEl = widget.querySelector('.header-change');

        const ltp = parseFloat(data.ltp || 0);
        const change = parseFloat(data.change || 0);
        let changePercent = 0;
        if (data.change !== 0) {
            const prev = ltp - change;
            if (Math.abs(prev) > 0.01) changePercent = (change / prev) * 100;
        }

        ltpEl.textContent = this.formatPrice(ltp);
        changeEl.textContent = `${this.formatChange(change)} (${Math.abs(changePercent).toFixed(2)}%)`;
        changeEl.className = 'header-change ' + this.getChangeClass(change);

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
            <td class="opt-ltp">--</td>
            <td class="opt-pct">--</td>
            <td class="opt-vol">--</td>
            <td class="opt-pnl font-mono">--</td>
            <td class="text-right actions-cell flex gap-2 justify-end" style="padding: 4px;">
                <button onclick="window.priceGrid.trade('${symbol}', 'BUY', window.priceGrid.getLotSize('${symbol}'))" class="btn-trade btn-buy" style="width:24px;height:24px;font-size:0.8rem">B</button>
                <button onclick="window.priceGrid.trade('${symbol}', 'SELL', window.priceGrid.getLotSize('${symbol}'))" class="btn-trade btn-sell" style="width:24px;height:24px;font-size:0.8rem">S</button>
                <button onclick="window.priceGrid.trade('${symbol}', 'EXIT', 0)" class="btn-trade btn-exit" style="width:24px;height:24px;font-size:0.8rem">X</button>
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
        let changePercent = 0;
        if (data.change !== 0) {
            const prev = ltp - change;
            if (Math.abs(prev) > 0.01) changePercent = (change / prev) * 100;
        }

        // Update cells directly
        row.querySelector('.opt-ltp').textContent = this.formatPrice(ltp);

        const pctEl = row.querySelector('.opt-pct');
        pctEl.textContent = `${changePercent.toFixed(1)}%`;
        pctEl.className = 'opt-pct ' + this.getChangeClass(changePercent);

        row.querySelector('.opt-vol').textContent = this.formatVolume(data.volume);

        // P&L
        const pos = this.positions[symbol] || {};
        const pnl = pos.unrealized_pnl || 0;
        const pnlEl = row.querySelector('.opt-pnl');
        pnlEl.textContent = pos.net_qty ? Math.round(pnl) : '-';
        pnlEl.className = 'opt-pnl font-mono ' + (pnl >= 0 ? 'text-green-400' : 'text-red-400');
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
        if (!confirm(`Confirm ${side} ${qty} ${symbol}?`)) return;

        try {
            const response = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, side, qty, price: 0 })
            });
            const res = await response.json();
            if (res.status === 'success') {
                alert(`Order Placed: ${res.order_id}`);
            } else {
                alert(`Error: ${res.message} (Is Algo Running?)`);
            }
        } catch (e) {
            alert(`Network Error: ${e}`);
        }
    }

    updateHeroCard(data) {
        if (!this.bankniftyPrice || !this.bankniftyChange) return;

        const ltp = parseFloat(data.ltp || 0);
        const change = parseFloat(data.change || 0);
        let changePercent = 0;
        if (data.change !== 0) {
            const prev = ltp - change;
            if (Math.abs(prev) > 0.01) changePercent = (change / prev) * 100;
        }

        this.bankniftyPrice.textContent = this.formatPrice(ltp);
        this.bankniftyChange.innerHTML = `
            <span class="change-value ${this.getChangeClass(change)}">${this.formatChange(change)}</span>
            <span class="change-percent ${this.getChangeClass(changePercent)}">(${Math.abs(changePercent).toFixed(2)}%)</span>
        `;

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
