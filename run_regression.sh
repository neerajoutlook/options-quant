#!/bin/bash
# Regression Test Runner

echo "🚀 Starting Regression Test Suite..."

# Ensure PYTHONPATH includes project root
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run Pytest on the regression directory
# -v: Verbose
# -s: Show stdout (logs)
pytest tests/regression/test_trade_flow.py -v -s

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Regression Tests PASSED"
else
    echo "❌ Regression Tests FAILED"
fi

exit $EXIT_CODE
