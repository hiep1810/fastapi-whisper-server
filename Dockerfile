# ✅ Use an official Python runtime as base image
FROM python:3.12-slim

# ✅ Install system build tools & runtime dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# ✅ Set working directory
WORKDIR /app

# ✅ Copy Python requirements first (leverages Docker cache)
COPY requirements.txt .

# ✅ Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Copy the rest of your FastAPI app (includes whisper.cpp)
COPY . .

# ✅ Set working directory
# This is where whisper.cpp will be built
WORKDIR /app/whisper.cpp

# ✅ Build & install whisper.cpp with CMake
RUN cmake -B build && cmake --build build -j --config Release

# ✅ If your `make install` installs libwhisper.so to /usr/local/lib,
# this helps the linker find it
ENV LD_LIBRARY_PATH=/usr/local/lib

# ✅ Return to app working directory
WORKDIR /app

# ✅ Expose FastAPI port
EXPOSE 8000

# ✅ Create uploads folder at runtime if not already
RUN mkdir -p /app/uploads

# ✅ Default CMD is handled by docker-compose.yml
