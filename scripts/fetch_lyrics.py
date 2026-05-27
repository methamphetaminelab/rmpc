#!/usr/bin/env python3
"""Auto-fetch .lrc lyrics for rmpc via LRCLIB API."""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
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
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger


def resolve_lrc_path(current_song: str) -> Path:
    """Map a relative song path to its .lrc path under Music/Lyrics."""
    if not current_song.strip():
        raise ValueError("current_song must not be empty")
    relative = Path(current_song)
    if relative.is_absolute():
        raise ValueError("current_song must be a relative path")
    if ".." in relative.parts:
        raise ValueError("Path traversal not allowed")
    return MUSIC_DIR / LRC_SUBDIR / relative.with_suffix(".lrc")


def fetch_lyrics_from_lrclib(
    artist: str, title: str, album: str | None, duration: float | None
) -> str | None:
    """Query LRCLIB for synced lyrics. Returns None if not found or on error."""
    params = {
        "artist_name": artist,
        "track_name": title,
    }
    if album:
        params["album_name"] = album
    if duration is not None:
        params["duration"] = duration

    query = urllib.parse.urlencode(params)
    url = f"{LRCLIB_API}?{query}"

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rmpc-auto-lyrics/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode())
                return data.get("syncedLyrics") or None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last_error = e
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e

        if attempt < MAX_RETRIES:
            wait = 2 ** (attempt - 1)
            time.sleep(wait)

    raise last_error if last_error else RuntimeError("Unknown error fetching lyrics")


# ── Main ────────────────────────────────────────────────────────────
def main() -> int:
    logger = setup_logging()
    logger.info("fetch_lyrics invoked")
    # TODO: implement
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
