"""
Bulk Dispatcher — Sends all candidate folders to the Celery queue.

Usage:
    python bulk_dispatch.py                             (uses default paths)
    python bulk_dispatch.py --input input/candidates    (custom input path)

Each candidate folder is dispatched as an independent Celery task.
Workers process them in parallel. Output goes to the local output/ folder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

app = typer.Typer(help="Dispatch bulk candidate processing to Celery workers.")


@app.command()
def dispatch(
    input_dir: Path = typer.Option(
        Path("input/candidates"),
        "--input", "-i",
        help="Path to folder containing candidate subdirectories",
        exists=True,
        resolve_path=True,
    ),
    output_dir: Path = typer.Option(
        Path("output"),
        "--output", "-o",
        help="Base output directory",
        resolve_path=True,
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to config.json (auto-discovered if not set)",
    ),
) -> None:
    """Discover candidate folders and dispatch each one to a Celery worker."""
    from tasks import process_candidate_task

    # Auto-discover config
    if config_path is None:
        auto_config = input_dir.parent / "config.json"
        if auto_config.exists():
            config_path = auto_config

    # Discover candidate subdirectories
    candidates = sorted(
        [d for d in input_dir.iterdir() if d.is_dir()],
        key=lambda p: p.name,
    )

    if not candidates:
        typer.echo("[ERROR] No candidate folders found in: " + str(input_dir))
        raise typer.Exit(code=1)

    typer.echo(f"\n{'='*60}")
    typer.echo(f"  BULK DISPATCH — {len(candidates)} candidates")
    typer.echo(f"  Input:  {input_dir}")
    typer.echo(f"  Output: {output_dir}")
    typer.echo(f"{'='*60}\n")

    # Dispatch each candidate to the Celery queue
    task_ids = []
    for candidate_dir in candidates:
        candidate_name = candidate_dir.name
        candidate_output = output_dir / candidate_name

        task = process_candidate_task.delay(
            candidate_name=candidate_name,
            input_dir=str(candidate_dir),
            output_dir=str(candidate_output),
            config_path=str(config_path) if config_path else None,
        )
        task_ids.append((candidate_name, task.id))
        typer.echo(f"  ✓ Dispatched: {candidate_name} → Task ID: {task.id[:8]}...")

    typer.echo(f"\n[INFO] {len(task_ids)} tasks dispatched to Celery workers.")
    typer.echo("[INFO] Workers will process them in parallel.")
    typer.echo("[INFO] Watch worker logs with: docker compose logs -f worker")


if __name__ == "__main__":
    app()
