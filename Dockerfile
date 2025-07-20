# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . .

# Copy whisper-cli and models
COPY whisper.cpp/build/bin/whisper-cli /usr/local/bin/whisper-cli
COPY whisper.cpp/models /app/models

# Make whisper-cli executable
RUN chmod +x /usr/local/bin/whisper-cli

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variables
ENV WHISPER_CLI="/path/to/your/whisper-cli"
ENV MODEL="base"
ENV UPLOAD_DIR="/app/uploads"
ENV METADATA_FILE="/app/metadata.json"
ENV API_KEY="your-secret-api-key"
ENV MAX_AGE_SECONDS=86400

# The command to run is specified in the docker-compose.yml file
