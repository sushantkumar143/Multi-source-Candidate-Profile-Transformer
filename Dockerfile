# ============================================================
# Multi-source Candidate Profile Transformer — Docker Image
# ============================================================
# Uses a multi-stage build for smaller image size.
# Stage 1: Install dependencies
# Stage 2: Copy application code
# ============================================================

FROM python:3.10-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required by pdfplumber (poppler) and others
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (for Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Create output and input directories
RUN mkdir -p /app/input /app/output

# Default command: run the FastAPI web server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
