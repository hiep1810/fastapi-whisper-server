from celery import Celery
import subprocess
import os

from dotenv import load_dotenv

try:
    from dotenv import load_dotenv
except ImportError:
    raise ImportError("❌ python-dotenv is not installed. Install it with `pip install python-dotenv`.")
load_dotenv()

celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

WHISPER_CLI = os.environ.get("WHISPER_CLI")
MODEL = os.environ.get("MODEL")

if not WHISPER_CLI:
    raise ValueError("❌ WHISPER_CLI is not set! Please check your .env file.")

if not MODEL:
    raise ValueError("❌ MODEL is not set! Please check your .env file.")

@celery_app.task
def transcribe_task(input_path, output_path, language, format):
    cmd = [WHISPER_CLI, "-m", MODEL, "-f", input_path]
    if format == "srt":
        cmd.append("--output-srt")
    elif format == "txt":
        cmd.append("--output-txt")
    if language:
        cmd.extend(["--language", language])

    try:
        subprocess.run(cmd, check=True)
        return {"status": "completed", "result": output_path}
    except subprocess.CalledProcessError as e:
        return {"status": "failed", "error": str(e)}
