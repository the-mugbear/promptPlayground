# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables to prevent caching issues and ensure output is shown
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if needed (e.g., build tools for some Python packages)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Install pip requirements
# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Make port 8000 available to the world outside this container (Gunicorn default)
EXPOSE 8000

# Define environment variables needed by Flask/Celery
# These will often be overridden by docker-compose/podman-compose
ENV FLASK_APP=fuzzy_prompts:create_app
ENV FLASK_RUN_HOST=0.0.0.0
# Add other runtime ENV VARS if needed, e.g., CELERY_BROKER_URL, DB_URL if not using compose env files

# Command to run the application using Gunicorn (for the web server)
# This will be overridden for the celery worker in the compose file
# Use a reasonable number of workers (e.g., 2*CPU + 1)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "fuzzy_prompts:create_app()"]