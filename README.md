# FastAPI Whisper Server

This project provides a simple FastAPI server to transcribe audio files using [Whisper.cpp](https://github.com/ggerganov/whisper.cpp).

## Features

- Upload audio files for transcription.
- Specify the output format (`srt` or `txt`).
- Specify the language for transcription.
- Saves metadata about each transcription request.

## Project Phases

| Phase | Features | Goal |
| :--- | :--- | :--- |
| ✅ MVP | Upload + basic SRT output | Working core |
| 🚀 Phase 1 | Multi-format + auto language + metadata | Production-ready core |
| ⚡ Phase 2 | Auth + remote URL + cleanup | Safe & scalable |
| ✨ Phase 3 | Dashboard | Polished product |
| 🚀 Phase 4 | Transcription Queue | Handle multiple requests |
| 💡 Future | Diarization | Speaker-separated transcripts |

## Prerequisites

- Python 3.7+
- A compiled version of `whisper.cpp`. The main executable should be accessible.

## Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/hiep1810/fastapi-whisper-server.git
    cd fastapi-whisper-server
    ```

2.  **Install Python dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up `whisper.cpp`:**

    Follow the instructions on the [whisper.cpp](https://github.com/ggerganov/whisper.cpp) repository to build the project. You will also need to download a model.

4.  **Configure environment variables:**

    Create a `.env` file in the root of the project and add the following variables:

    ```
    WHISPER_CLI="path/to/your/whisper.cpp/main"
    MODEL="path/to/your/whisper.cpp/models/ggml-base.en.bin"
    UPLOAD_DIR="uploads"
    METADATA_FILE="metadata.json"
    ```

    - `WHISPER_CLI`: The path to the compiled `main` executable from `whisper.cpp`.
    - `MODEL`: The path to the Whisper model you want to use.
    - `UPLOAD_DIR`: The directory where uploaded files will be stored.
    - `METADATA_FILE`: The file where transcription metadata will be saved.

## Usage

**IMPORTANT**: Before starting the application, make sure you have Redis installed and running.

1.  **Start Redis:**

    ```bash
    redis-server
    ```

2.  **Start the Celery worker:**

    ```bash
    celery -A celery_worker.celery_app worker --loglevel=info
    ```

3.  **Start the server:**

    ```bash
    python -m uvicorn app:app --host 0.0.0.0 --port 8000
    ```

4.  **Send a transcription request:**

    You can use a tool like `curl` to send a `POST` request to the `/transcribe` endpoint:

    ```bash
    curl -X POST -F "file=@/path/to/your/audio.wav" -F "language=en" -F "format=srt" http://localhost:8000/transcribe -o transcript.srt
    ```

    -   `file`: The audio file to transcribe.
    -   `language` (optional): The language of the audio. If not provided, Whisper will try to auto-detect the language.
    -   `format` (optional): The desired output format. Can be `srt` (default) or `txt`.

The server will return a task ID. You can use the dashboard to check the status of the transcription.

## API Endpoints

### `POST /transcribe`

Submits an audio file for transcription.

**Form Data:**

-   `file` (required): The audio file to be uploaded.
-   `language` (optional): The language code (e.g., `en`, `es`, `fr`).
-   `format` (optional): The output format (`srt` or `txt`). Defaults to `srt`.

**Responses:**

-   `200 OK`: Returns a task ID.

### `GET /transcribe/{task_id}`

Checks the status of a transcription task.

**Responses:**

-   `200 OK`: Returns the status of the task. If the task is completed, it also returns the path to the transcription file.
