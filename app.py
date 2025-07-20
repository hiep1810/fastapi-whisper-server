from dotenv import load_dotenv
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Query, Header, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from celery import chain
from celery.result import AsyncResult
from celery_worker import transcribe_task, create_video_task
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




@app.post("/transcribe", dependencies=[Depends(verify_api_key)])
async def transcribe_audio(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    language: str = Form(default=""),
    format: str = Form(default="srt"),
    model: str = Form(default=os.environ.get("MODEL", "base"))
):
    # Save upload
    uid = str(uuid.uuid4())

    filename = os.path.splitext(file.filename)[0]
    input_path = os.path.join(UPLOAD_DIR, f"{uid}_{filename}")

    output_ext = ".srt" if format == "srt" else ".txt"
    output_path = f"{input_path}{output_ext}"

    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    task = transcribe_task.delay(input_path, output_path, language, format, model)

    metadata = {
        "task_id": task.id,
        "file_id": uid,
        "source": "upload",
        "filename": file.filename,
        "input_path": input_path,
        "output_path": output_path,
        "language": language or "auto",
        "type": "transcription"
    }
    save_metadata(metadata)

    return {"task_id": task.id}


@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id)
    if not task_result.ready():
        return {"status": "pending"}

    if not task_result.successful():
        return {"status": "failed", "error": str(task_result.result)}

    result = task_result.result
    file_type = "unknown"

    # Determine file type from result
    if isinstance(result, dict):
        path = result.get("output_path") or result.get("result")
        if path and isinstance(path, str):
            ext = os.path.splitext(path)[1].lower()
            if ext in [".srt", ".txt", ".vtt"]:
                file_type = "text"
            elif ext in [".mp4", ".mov", ".avi", ".mkv"]:
                file_type = "video"
            elif ext in [".mp3", ".wav", ".ogg", ".flac"]:
                file_type = "audio"

    return {"status": "completed", "result": result, "file_type": file_type}


@app.post("/create_transcript_video", dependencies=[Depends(verify_api_key)])
async def create_transcript_video(
    file: UploadFile = File(...),
    language: str = Form(default="")
):
    # Save upload
    uid = str(uuid.uuid4())
    filename = os.path.splitext(file.filename)[0]
    input_path = os.path.join(UPLOAD_DIR, f"{uid}_{filename}")
    
    output_path = f"{input_path}.srt"

    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Create a chain of tasks
    task_chain = chain(
        transcribe_task.s(input_path, output_path, language, "srt"),
        create_video_task.s()
    )
    result = task_chain.apply_async()

    # Save metadata for the chained task
    metadata = {
        "task_id": result.id,
        "file_id": uid,
        "source": "upload",
        "filename": file.filename,
        "input_path": input_path,
        "language": language or "auto",
        "type": "transcript_video_chain"
    }
    save_metadata(metadata)

    return {"task_id": result.id}


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
    format: str = Query(default="srt"),
    model: str = Query(default=os.environ.get("MODEL", "base"))
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

    model_path = f"/app/models/{model}"
    cmd = [WHISPER_CLI, "-m", model_path, "-f", input_path]
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
