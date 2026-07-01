import io
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pipeline import Pipeline

app = FastAPI(
    title="Candidate Intelligence Pipeline API",
    description="Multi-source Candidate Profile Transformer",
    version="2.0.0",
)

class StringLogger:
    """A context manager to temporarily redirect logging to a string buffer."""
    def __init__(self, level=logging.INFO):
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setLevel(level)
        formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.handler.setFormatter(formatter)
        self.logger = logging.getLogger() # root logger

    def __enter__(self):
        self.logger.addHandler(self.handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.removeHandler(self.handler)
        self.handler.close()

    def get_logs(self):
        return self.stream.getvalue()


@app.post("/process")
async def process_candidate(
    resume: Optional[UploadFile] = File(None, description="Resume PDF file"),
    csv: Optional[UploadFile] = File(None, description="Candidate CSV file"),
    linkedin: Optional[UploadFile] = File(None, description="LinkedIn TXT file"),
    recruiter_notes: Optional[UploadFile] = File(None, description="Recruiter Notes TXT file"),
    links: Optional[UploadFile] = File(None, description="Links JSON file (e.g., github_url)"),
    config: Optional[UploadFile] = File(None, description="Config JSON file"),
):
    """
    Process candidate data from various uploaded sources and return the canonical profile.
    """
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        input_dir = temp_dir / "input"
        output_dir = temp_dir / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        config_path = None

        # Save uploaded files to the temp input directory
        files = {
            "resume.pdf": resume,
            "candidate.csv": csv,
            "linkedin.txt": linkedin,
            "recruiter_notes.txt": recruiter_notes,
            "links.json": links,
        }

        for filename, upload_file in files.items():
            if upload_file:
                file_path = input_dir / filename
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(upload_file.file, f)

        if config:
            config_path = temp_dir / "config.json"
            with open(config_path, "wb") as f:
                shutil.copyfileobj(config.file, f)

        # Capture step-by-step logs and run the pipeline
        with StringLogger() as log_capture:
            try:
                pipeline = Pipeline(
                    input_dir=input_dir,
                    output_dir=output_dir,
                    config_path=config_path,
                )
                
                # The pipeline run will process the files and generate the output
                result = pipeline.run()
                
            except Exception as e:
                logs = log_capture.get_logs()
                return JSONResponse(status_code=500, content={"error": str(e), "logs": logs})

        # Read the generated candidate and audit report
        candidate_file = output_dir / "candidate.json"
        audit_file = output_dir / "audit_report.json"

        candidate_data = {}
        audit_data = {}

        if candidate_file.exists():
            with open(candidate_file, "r", encoding="utf-8") as f:
                candidate_data = json.load(f)
                
        if audit_file.exists():
            with open(audit_file, "r", encoding="utf-8") as f:
                audit_data = json.load(f)

        logs = log_capture.get_logs()
        
        # Split logs into an array of lines for better JSON readability
        log_lines = [line for line in logs.split("\n") if line.strip()]

        return {
            "candidate": candidate_data,
            "audit_report": audit_data,
            "logs": log_lines,
        }


# ── Bulk Processing (Celery) ─────────────────────────────────

class BulkRequest(BaseModel):
    """Request body for bulk processing."""
    input_dir: str = "input/candidates"
    output_dir: str = "output"
    config_path: Optional[str] = None


@app.post("/process/bulk")
async def process_bulk(request: BulkRequest):
    """
    Dispatch all candidate folders to Celery workers for parallel processing.
    Returns task IDs for tracking.
    """
    try:
        from tasks import process_candidate_task
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"error": "Celery/Redis not available. Start workers first.", "detail": str(e)},
        )

    input_path = Path(request.input_dir)
    if not input_path.exists():
        return JSONResponse(status_code=404, content={"error": f"Input directory not found: {request.input_dir}"})

    candidates = sorted([d for d in input_path.iterdir() if d.is_dir()], key=lambda p: p.name)
    if not candidates:
        return JSONResponse(status_code=404, content={"error": "No candidate folders found"})

    # Auto-discover config
    config = request.config_path
    if config is None:
        auto_config = input_path.parent / "config.json"
        if auto_config.exists():
            config = str(auto_config)

    # Dispatch tasks to Celery workers
    dispatched = []
    for candidate_dir in candidates:
        candidate_name = candidate_dir.name
        candidate_output = Path(request.output_dir) / candidate_name

        task = process_candidate_task.delay(
            candidate_name=candidate_name,
            input_dir=str(candidate_dir),
            output_dir=str(candidate_output),
            config_path=config,
        )
        dispatched.append({"candidate": candidate_name, "task_id": task.id})

    return {
        "status": "dispatched",
        "total_candidates": len(dispatched),
        "tasks": dispatched,
        "message": f"{len(dispatched)} candidates sent to Celery workers for parallel processing.",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/Kubernetes."""
    redis_status = "unknown"
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=1)
        r.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "unavailable (in-memory fallback active)"

    return {
        "status": "healthy",
        "version": "2.0.0",
        "redis": redis_status,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
