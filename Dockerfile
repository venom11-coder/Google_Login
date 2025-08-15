# Use official Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install system dependencies and Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    apt-get purge -y --auto-remove build-essential

# Copy app code
COPY . .

# Expose the port
EXPOSE 8080

# Start Gunicorn with Uvicorn worker
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "google_auth:app", "--bind", "0.0.0.0:8080"]
