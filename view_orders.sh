#!/bin/bash
# Order Log Viewer - Shows today's trading activity

echo "=== ORDER LOG VIEWER ==="
echo "Date: $(date '+%Y-%m-%d')"
echo ""

if [ ! -f "logs/orders.log" ]; then
    echo "No orders log found. Bot hasn't generated any signals yet."
    exit 0
fi

echo "--- SIGNALS GENERATED ---"
grep "SIGNAL |" logs/orders.log | tail -20

echo ""
echo "--- ORDERS ATTEMPTED ---"
grep "ORDER_ATTEMPT |" logs/orders.log | tail -20

echo ""
echo "--- ORDER RESULTS ---"
grep "ORDER_RESULT |" logs/orders.log | tail -20

echo ""
echo "--- ORDER UPDATES ---"
grep "ORDER_UPDATE |" logs/orders.log | tail -20

echo ""
echo "=== SUMMARY ==="
echo "Total Signals: $(grep -c "SIGNAL |" logs/orders.log || echo 0)"
echo "Total Order Attempts: $(grep -c "ORDER_ATTEMPT |" logs/orders.log || echo 0)"
echo "Successful Orders: $(grep -c "PLACED" logs/orders.log || echo 0)"
echo "Failed Orders: $(grep -c "FAILED\|EXCEPTION" logs/orders.log || echo 0)"
echo "Rejected Orders: $(grep -c "REJECTED" logs/orders.log || echo 0)"
