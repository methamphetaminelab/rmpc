#!/usr/bin/env python3
"""Auto-fetch .lrc lyrics for rmpc via LRCLIB API."""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
MUSIC_DIR = Path("/home/user/Music")
LRC_SUBDIR = "Lyrics"
LOG_FILE = Path.home() / ".local/share/rmpc/fetch_lyrics.log"
MAX_RETRIES = 3
TIMEOUT_SECONDS = 10

LRCLIB_API = "https://lrclib.net/api/get"

# ── Logging ─────────────────────────────────────────────────────────
def setup_logging() -> logging.Logger:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_FILE)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger = logging.getLogger("fetch_lyrics")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger


# ── Main ────────────────────────────────────────────────────────────
def main() -> int:
    logger = setup_logging()
    logger.info("fetch_lyrics invoked")
    # TODO: implement
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
