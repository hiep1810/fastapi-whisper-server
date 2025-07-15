from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
import subprocess
import os
import json
import uuid
import time

load_dotenv()  # <-- Load environment variables from .env file

app = FastAPI()

# Path to your whisper-cli binary
WHISPER_CLI = os.environ.get("WHISPER_CLI")
MODEL = os.environ.get("MODEL")
UPLOAD_DIR= os.environ.get("UPLOAD_DIR")
METADATA_FILE = os.environ.get("METADATA_FILE")

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---- UTILS ----
def save_metadata(data):
    if not os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "w") as f:
            json.dump([], f)

    with open(METADATA_FILE, "r") as f:
        meta = json.load(f)

    meta.append(data)

    with open(METADATA_FILE, "w") as f:
        json.dump(meta, f, indent=2)


@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form(default=""),
    format: str = Form(default="srt")  # srt or txt
):
    # Save upload
    uid = str(uuid.uuid4())
    input_path = f"{UPLOAD_DIR}/{uid}_{file.filename}"
    output_ext = ".srt" if format == "srt" else ".txt"
    output_path = f"{input_path}{output_ext}"

    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Build Whisper command
    cmd = [
        WHISPER_CLI,
        "-m", MODEL,
        "-f", input_path
    ]

    if format == "srt":
        cmd.append("--output-srt")
    elif format == "txt":
        cmd.append("--output-txt")

    if language:
        cmd.extend(["--language", language])

    # Run Whisper
    t0 = time.time()
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    processing_time = round(time.time() - t0, 2)

    # Save simple metadata
    metadata = {
        "file_id": uid,
        "filename": file.filename,
        "output": output_path,
        "language": language or "auto",
        "processing_time": processing_time
    }
    save_metadata(metadata)

    return FileResponse(output_path, media_type="text/plain", filename=f"transcript{output_ext}")
