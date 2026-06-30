"""
Configuration loader.

Loads and validates the runtime config.json file.
If no config is found, returns a default configuration
that outputs all canonical fields.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from schemas.config_schema import RuntimeConfig

logger = logging.getLogger(__name__)


def load_config(config_path: Path | None) -> RuntimeConfig:
    """Load runtime configuration from a JSON file.

    If the file doesn't exist or is invalid, returns the default config
    (all fields, confidence included, on_missing="null").

    Args:
        config_path: Path to config.json, or None for default.

    Returns:
        Validated RuntimeConfig instance.
    """
    if config_path is None or not config_path.exists():
        logger.info("No config file found — using default configuration (all fields)")
        return RuntimeConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw: dict[str, Any] = json.load(f)

        config = RuntimeConfig(**raw)
        logger.info("Loaded runtime config from %s", config_path.name)

        if config.fields:
            logger.info(
                "Config specifies %d projected fields", len(config.fields)
            )
        else:
            logger.info("Config has no field projections — all canonical fields will be output")

        return config

    except json.JSONDecodeError as e:
        logger.warning("Config file is not valid JSON: %s — using default config", e)
        return RuntimeConfig()

    except ValidationError as e:
        logger.warning("Config file has validation errors: %s — using default config", e)
        return RuntimeConfig()

    except Exception as e:
        logger.warning("Unexpected error loading config: %s — using default config", e)
        return RuntimeConfig()
