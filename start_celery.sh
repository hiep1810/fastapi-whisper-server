#!/data/data/com.termux/files/usr/bin/bash

# Activate your venv
source /data/data/com.termux/files/home/python/fastapi-whisper-server/venv/bin/activate

# Wait for Redis
while ! bash -c "</dev/tcp/127.0.0.1/6379" 2>/dev/null; do
  echo "Waiting for Redis..."
  sleep 1
done

echo "Redis is up! Starting Celery..."
exec celery -A celery_worker.celery_app worker --loglevel=info

