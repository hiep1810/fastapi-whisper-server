from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
import subprocess
import os
import shutil
from uuid import uuid4

app = FastAPI()

# Path to your whisper-cli binary
WHISPER_CLI = "/data/data/com.termux/files/home/python/fastapi-whisper-server/whisper.cpp/build/bin/whisper-cli"

# Path to your model
MODEL = "/data/data/com.termux/files/home/python/fastapi-whisper-server/whisper.cpp/models/ggml-medium.bin"

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form(default="en")
):
    # Save upload
    audio_id = str(uuid4())
    input_path = f"{UPLOAD_DIR}/{audio_id}_{file.filename}"
    output_srt = f"{input_path}.srt"

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Run whisper-cli
    cmd = [
        WHISPER_CLI,
        "-m", MODEL,
        "-f", input_path,
        "--output-srt",
        "--language", language
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    # Send back the SRT file
    return FileResponse(output_srt, media_type="text/plain", filename="output.srt")

