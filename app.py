"""
Candidate Intelligence Pipeline — CLI Entry Point.

Usage:
    python app.py --input input/
    python app.py --input input/ --config input/config.json --output output/

This file contains ZERO business logic — it only:
1. Parses CLI arguments
2. Sets up logging
3. Delegates to the Pipeline orchestrator
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from pipeline import Pipeline
from utils.logger import setup_logging

app = typer.Typer(
    name="candidate-pipeline",
    help="Candidate Intelligence Pipeline — Multi-source Candidate Profile Transformer",
    add_completion=False,
)


@app.command()
def run(
    input_dir: Path = typer.Option(
        ...,
        "--input",
        "-i",
        help="Path to the input directory containing source files",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.json for output projection (auto-discovered in input dir if not specified)",
        exists=False,
        resolve_path=True,
    ),
    output_dir: Path = typer.Option(
        Path("output"),
        "--output",
        "-o",
        help="Path to the output directory",
        resolve_path=True,
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="Log level: DEBUG, INFO, WARNING, ERROR",
    ),
    log_file: Path | None = typer.Option(
        None,
        "--log-file",
        help="Optional file to write logs to",
        resolve_path=True,
    ),
) -> None:
    """Run the candidate intelligence pipeline.

    Automatically discovers candidate.csv, resume.pdf, github_profile.json,
    linkedin.txt, recruiter_notes.txt, and config.json in the input directory.
    """
    # Setup logging
    setup_logging(level=log_level, log_file=log_file)

    # Auto-discover config if not explicitly provided
    if config is None:
        auto_config = input_dir / "config.json"
        if not auto_config.exists() and input_dir.parent:
            auto_config = input_dir.parent / "config.json"
            
        if auto_config.exists():
            config = auto_config

    # Detect batch mode
    subdirs = [d for d in input_dir.iterdir() if d.is_dir()]
    
    if subdirs:
        typer.echo(f"\n[INFO] Found {len(subdirs)} candidate folders. Running batch mode...")
        success_count = 0
        for subdir in subdirs:
            candidate_output = output_dir / subdir.name
            typer.echo(f"Processing candidate: {subdir.name}")
            
            pipeline = Pipeline(
                input_dir=subdir,
                output_dir=candidate_output,
                config_path=config,
            )
            try:
                result = pipeline.run()
                if result:
                    success_count += 1
            except Exception as e:
                typer.echo(f"[ERROR] Failed processing {subdir.name}: {e}", err=True)
                
        typer.echo(f"\n[INFO] Batch complete. Successfully processed {success_count}/{len(subdirs)} candidates.")
    else:
        # Single candidate mode
        pipeline = Pipeline(
            input_dir=input_dir,
            output_dir=output_dir,
            config_path=config,
        )

        try:
            result = pipeline.run()
            if result:
                typer.echo(f"\nPipeline complete. Output written to {output_dir}/")
                typer.echo(f"   * candidate.json")
                typer.echo(f"   * audit_report.json")
            else:
                typer.echo("\n[WARNING] Pipeline completed with no output -- check logs for details")
                raise typer.Exit(code=1)
        except Exception as e:
            typer.echo(f"\n[ERROR] Pipeline failed: {e}", err=True)
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
