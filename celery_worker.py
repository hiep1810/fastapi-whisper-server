from celery import Celery
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery("tasks")

celery_app.conf.update(
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND_URL", "redis://localhost:6379/0"),
)

WHISPER_CLI = os.environ.get("WHISPER_CLI")
MODEL = os.environ.get("MODEL")

if not WHISPER_CLI:
    raise ValueError("❌ WHISPER_CLI is not set! Please check your .env file.")

if not MODEL:
    raise ValueError("❌ MODEL is not set! Please check your .env file.")

@celery_app.task(bind=True)
def transcribe_task(self, input_path, output_path, language, format, model=None):
    # Output path is determined inside the task
    output_path = f"{os.path.splitext(input_path)[0]}.{format}"

    # Use the provided model, or fall back to the environment variable
    model_name = model or os.environ.get("MODEL", "base")
    model_path = f"/app/models/{model_name}"

    cmd = [WHISPER_CLI, "-m", model_path, "-f", input_path]
    if format == "srt":
        cmd.append("--output-srt")
    elif format == "txt":
        cmd.append("--output-txt")
    if language:
        cmd.extend(["--language", language])

    try:
        subprocess.run(cmd, check=True)
        # Return paths for the next task in the chain
        return {"input_path": input_path, "output_path": output_path}
    except subprocess.CalledProcessError as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise e


def make_subtitled_video(audio_path, srt_path, output_path):
    # Make sure paths are absolute and FFmpeg-safe
    audio_path = os.path.abspath(audio_path)
    srt_path = os.path.abspath(srt_path)
    output_path = os.path.abspath(output_path)

    # 1. Get audio duration
    result = subprocess.run(
        ["ffprobe", "-i", audio_path, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    duration = float(result.stdout.strip())

    # FFmpeg on Windows requires special path escaping for the subtitles filter
    if os.name == 'nt':
        # Replace backslashes with forward slashes and escape colons
        srt_path_escaped = srt_path.replace('\\', '/').replace(':', '\\:')
        subtitles_filter = f"subtitles='{srt_path_escaped}'"
    else:
        subtitles_filter = f"subtitles={srt_path}"


    # 2. FFmpeg command
    cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", f"color=size=1280x720:duration={duration}:rate=25:color=black",
        "-i", audio_path,
        "-vf", subtitles_filter,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]

    subprocess.run(cmd, check=True)


@celery_app.task(bind=True)
def create_video_task(self, paths):
    # The 'paths' argument is the return value of the previous task in the chain
    audio_path = paths['input_path']  # Use 'input_path' from transcribe_task
    srt_path = paths['output_path']   # Use 'output_path' from transcribe_task
    video_path = f"{os.path.splitext(audio_path)[0]}_subtitled.mp4"

    try:
        make_subtitled_video(audio_path, srt_path, video_path)
        # The final result of the chain is this dictionary
        return {"status": "completed", "output_path": video_path}
    except Exception as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise e
