/**
 * WebSocket Client for Real-time Price Streaming
 * Ultra-low latency connection with auto-reconnect
 */

class PriceWebSocket {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // Start with 1 second
        this.pingInterval = null;
        this.lastPingTime = 0;

        // Callbacks
        this.onSnapshot = null;
        this.onPriceUpdate = null;
        this.onConnected = null;
        this.onDisconnected = null;
        this.onLatencyUpdate = null;
    }

    connect() {
        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;

                if (this.onConnected) {
                    this.onConnected();
                }

                // Start ping-pong for latency measurement
                this.startPing();
            };

            this.ws.onmessage = (event) => {
                this.handleMessage(event.data);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket closed');
                this.isConnected = false;
                this.stopPing();

                if (this.onDisconnected) {
                    this.onDisconnected();
                }

                // Auto-reconnect with exponential backoff
                this.reconnect();
            };

        } catch (error) {
            console.error('Failed to connect:', error);
            this.reconnect();
        }
    }

    handleMessage(data) {
        try {
            // Handle pong for latency
            if (data === 'pong') {
                const latency = Date.now() - this.lastPingTime;
                if (this.onLatencyUpdate) {
                    this.onLatencyUpdate(latency);
                }
                return;
            }

            const message = JSON.parse(data);

            switch (message.type) {
                case 'snapshot':
                    // Initial data load
                    if (this.onSnapshot) {
                        this.onSnapshot(message.data);
                    }
                    break;

                case 'price_update':
                    // Real-time price update
                    if (this.onPriceUpdate) {
                        this.onPriceUpdate(message.symbol, message.data);
                    }
                    break;

                case 'ping':
                    // Server keepalive
                    this.send('pong');
                    break;
            }

        } catch (error) {
            console.error('Error handling message:', error);
        }
    }

    send(data) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(typeof data === 'string' ? data : JSON.stringify(data));
        }
    }

    startPing() {
        this.pingInterval = setInterval(() => {
            if (this.isConnected) {
                this.lastPingTime = Date.now();
                this.send('ping');
            }
        }, 5000); // Ping every 5 seconds
    }

    stopPing() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    reconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1);

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    disconnect() {
        this.stopPing();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Global WebSocket instance
window.priceWS = null;
