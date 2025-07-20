module.exports = {
  apps: [
    {
      name: "redis",
      script: "redis-server"
    },
    {
      name: "celery_worker",
      script: "./start_celery.sh"
    },
    {
      name: "uvicorn",
      script: "/data/data/com.termux/files/home/python/fastapi-whisper-server/venv/bin/uvicorn",
      args: "app:app --host 0.0.0.0 --port 8000",
      interpreter: "/data/data/com.termux/files/home/python/fastapi-whisper-server/venv/bin/python"
    },
  ]
};

