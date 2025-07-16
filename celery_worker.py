from celery import Celery
import subprocess
import os

celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

WHISPER_CLI = os.environ.get("WHISPER_CLI")
MODEL = os.environ.get("MODEL")

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
