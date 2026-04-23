#!/bin/bash
# LinkConnect Worker - Auto-restart on crash
# Run this once: bash start_worker.sh
# It will keep running in the background and auto-restart if it crashes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/linkconnect_worker.log"

echo "Starting LinkConnect worker (auto-restart enabled)..."
echo "Logs: $LOG_FILE"
echo "To stop: pkill -f 'worker.py'"

cd "$SCRIPT_DIR"

while true; do
    echo "[$(date)] Starting worker..." >> "$LOG_FILE"
    PYTHONUNBUFFERED=1 python3 -u worker.py >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
    echo "[$(date)] Worker exited with code $EXIT_CODE. Restarting in 10 seconds..." >> "$LOG_FILE"
    sleep 10
done
