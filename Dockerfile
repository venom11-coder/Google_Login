FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install system deps + Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy app code
COPY . .

EXPOSE 8080

# Start Gunicorn with Uvicorn worker
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "google_auth:app", "--bind", "0.0.0.0:8080"]
