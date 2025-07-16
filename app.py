from dotenv import load_dotenv
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Query, Header, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from celery.result import AsyncResult
from celery_worker import transcribe_task
import subprocess
import os
import json
import uuid
import time
import glob
import requests

load_dotenv()  # <-- Load environment variables from .env file

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

# Path to your whisper-cli binary
WHISPER_CLI = os.environ.get("WHISPER_CLI")
MODEL = os.environ.get("MODEL")
UPLOAD_DIR= os.environ.get("UPLOAD_DIR")
METADATA_FILE = os.environ.get("METADATA_FILE")
API_KEY = os.environ.get("API_KEY")
MAX_AGE_SECONDS = int(os.environ.get("MAX_AGE_SECONDS", 86400))

os.makedirs(UPLOAD_DIR, exist_ok=True)

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def save_metadata(data):
    if not os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "w") as f:
            json.dump([], f)

    with open(METADATA_FILE, "r") as f:
        meta = json.load(f)

    meta.append(data)

    with open(METADATA_FILE, "w") as f:
        json.dump(meta, f, indent=2)


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


@app.post("/transcribe", dependencies=[Depends(verify_api_key)])
async def transcribe_audio(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    language: str = Form(default=""),
    format: str = Form(default="srt"),
    make_video: bool = Form(default=False)
):
    # Save upload
    uid = str(uuid.uuid4())

    input_path = os.path.join(UPLOAD_DIR, f"{uid}_{file.filename}")

    output_ext = ".srt" if format == "srt" else ".txt"
    output_path = f"{input_path}{output_ext}"

    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    task = transcribe_task.delay(input_path, output_path, language, format)

    metadata = {
        "task_id": task.id,
        "file_id": uid,
        "source": "upload",
        "filename": file.filename,
        "output": output_path,
        "language": language or "auto",
    }
    save_metadata(metadata)

    return {"task_id": task.id}


@app.get("/transcribe/{task_id}")
async def get_transcription_status(task_id: str):
    task_result = AsyncResult(task_id)
    if task_result.ready():
        if task_result.successful():
            return {"status": "completed", "result": task_result.result}
        else:
            return {"status": "failed", "error": str(task_result.result)}
    else:
        return {"status": "pending"}


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/transcriptions")
async def get_transcriptions():
    if not os.path.exists(METADATA_FILE):
        return []
    with open(METADATA_FILE) as f:
        return json.load(f)


@app.get("/uploads/{file_path:path}")
async def get_transcription_file(file_path: str):
    return FileResponse(f"uploads/{file_path}")


def cleanup_old_files():
    now = time.time()
    for f in glob.glob(f"{UPLOAD_DIR}/*"):
        if os.stat(f).st_mtime < now - MAX_AGE_SECONDS:
            os.remove(f)


@app.post("/transcribe_url", dependencies=[Depends(verify_api_key)])
async def transcribe_from_url(
    url: str = Query(..., description="Audio file URL"),
    background_tasks: BackgroundTasks = None,
    language: str = Query(default=""),
    format: str = Query(default="srt")
):
    uid = str(uuid.uuid4())
    input_path = f"{UPLOAD_DIR}/{uid}_remote_audio"
    output_ext = ".srt" if format == "srt" else ".txt"
    output_path = f"{input_path}{output_ext}"

    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to download file")

    with open(input_path, "wb") as f:
        for chunk in r.iter_content(1024):
            f.write(chunk)

    cmd = [WHISPER_CLI, "-m", MODEL, "-f", input_path]
    if format == "srt":
        cmd.append("--output-srt")
    elif format == "txt":
        cmd.append("--output-txt")
    if language:
        cmd.extend(["--language", language])

    t0 = time.time()
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    processing_time = round(time.time() - t0, 2)

    metadata = {
        "file_id": uid,
        "source": url,
        "output": output_path,
        "language": language or "auto",
        "processing_time": processing_time
    }
    save_metadata(metadata)

    background_tasks.add_task(cleanup_old_files)

    return FileResponse(output_path, media_type="text/plain", filename=f"transcript{output_ext}")
