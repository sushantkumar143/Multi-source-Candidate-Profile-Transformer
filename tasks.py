"""
Celery Task Definitions — Async Pipeline Processing.

Defines background tasks that Celery workers pull from the Redis queue.
Each task processes a single candidate folder through the full pipeline.

Usage:
    # Start the worker:
    celery -A tasks worker --loglevel=info --concurrency=4

    # Dispatch tasks from Python:
    from tasks import process_candidate_task
    process_candidate_task.delay("sushant_kumar", "input/candidates/sushant_kumar", "output/sushant_kumar")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from celery import Celery

logger = logging.getLogger(__name__)

# ── Celery Configuration ─────────────────────────────────────
# Uses Redis as both broker (task queue) and backend (result store).
# Falls back to local filesystem if Redis is unavailable.
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "candidate_tasks",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

# Celery settings for reliability
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,                # Re-queue task if worker crashes mid-processing
    worker_prefetch_multiplier=1,       # Don't hoard tasks; take one at a time
    result_expires=3600,                # Results expire after 1 hour
)


@celery_app.task(bind=True, name="process_candidate", max_retries=2)
def process_candidate_task(self, candidate_name: str, input_dir: str, output_dir: str, config_path: str | None = None):
    """Process a single candidate folder through the full pipeline.

    Args:
        candidate_name: Human-readable name for logging.
        input_dir: Absolute or relative path to the candidate's input folder.
        output_dir: Absolute or relative path to write outputs.
        config_path: Optional path to config.json.

    Returns:
        dict with processing status, confidence, and output path.
    """
    from pipeline import Pipeline

    logger.info("Worker picked up task: %s", candidate_name)

    try:
        pipeline = Pipeline(
            input_dir=Path(input_dir),
            output_dir=Path(output_dir),
            config_path=Path(config_path) if config_path else None,
        )
        result = pipeline.run()

        if result:
            overall_confidence = result.get("overall_confidence", 0.0)
            logger.info(
                "Completed: %s (confidence=%.3f)",
                candidate_name,
                overall_confidence,
            )
            return {
                "status": "success",
                "candidate": candidate_name,
                "confidence": overall_confidence,
                "output_dir": str(output_dir),
            }
        else:
            logger.warning("Pipeline returned empty result for %s", candidate_name)
            return {
                "status": "empty",
                "candidate": candidate_name,
                "output_dir": str(output_dir),
            }

    except Exception as exc:
        logger.error("Failed processing %s: %s", candidate_name, exc)
        # Retry up to max_retries times with exponential backoff
        raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))
