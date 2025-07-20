#!/data/data/com.termux/files/usr/bin/bash

# Activate your venv
source /data/data/com.termux/files/home/python/fastapi-whisper-server/venv/bin/activate

# Run uvicorn (adjust the module)
exec uvicorn app:app --host 0.0.0.0 --port 8000 --reload

