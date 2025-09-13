#!/bin/bash
set -e

# Ensure /app exists
mkdir -p /app

# Clone or update repo
if [ -z "$(ls -A /app)" ]; then
    echo "[INFO] /app is empty, cloning repo..."
    git clone "${REPO}" /app
else
    echo "[INFO] /app already has files, pulling latest changes..."
    cd /app
    git pull || echo "[WARN] git pull failed"
fi

# Set cron schedule
CRON_SCHEDULE="${CRON:-0 2 * * *}"

# Run immediately if requested
if [ "$RUN_NOW" = "true" ]; then
    echo "[INFO] RUN_NOW flag detected. Running UTSK.py immediately..."
    cd /app
    DOCKER=true python3 /app/UTSK.py 2>&1 | tee -a /var/log/cron.log
fi

# Setup cron job
echo "$CRON_SCHEDULE root cd /app && DOCKER=true python3 /app/UTSK.py >> /var/log/cron.log 2>&1" > /etc/cron.d/utsk-cron
chmod 0644 /etc/cron.d/utsk-cron
crontab /etc/cron.d/utsk-cron

# Ensure log exists
touch /var/log/cron.log

# Start cron in foreground
echo "[INFO] Starting cron with schedule: $CRON_SCHEDULE"
crond -f -l 2