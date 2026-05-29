#!/usr/bin/env python3
"""Auto-fetch .lrc lyrics for rmpc via LRCLIB API."""
from __future__ import annotations

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
    for h in logger.handlers:
        h.close()
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


def _try_fetch_lrclib(
    artist: str, title: str, album: str | None, duration: float | None
) -> str | None:
    """Direct LRCLIB API query."""
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

    req = urllib.request.Request(url, headers={"User-Agent": "rmpc-auto-lyrics/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode())
        return data.get("syncedLyrics") or None


def _search_lrclib(artist: str, title: str) -> str | None:
    """Fallback search via LRCLIB search API."""
    query = urllib.parse.quote(f"{artist} {title}")
    url = f"https://lrclib.net/api/search?q={query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rmpc-auto-lyrics/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode())
            title_lower = title.lower()
            for track in data:
                if track.get("trackName", "").lower() == title_lower:
                    return track.get("syncedLyrics") or None
    except Exception:
        pass
    return None


def fetch_lyrics_from_lrclib(
    artist: str, title: str, album: str | None, duration: float | None
) -> str | None:
    """Query LRCLIB for synced lyrics. Returns None if not found or on error."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _try_fetch_lrclib(artist, title, album, duration)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return _search_lrclib(artist, title)
            last_error = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = e

        if attempt < MAX_RETRIES:
            wait = 2 ** (attempt - 1)
            time.sleep(wait)

    raise last_error if last_error else RuntimeError("Unknown error fetching lyrics")


# ── Main ────────────────────────────────────────────────────────────
def main() -> int:
    logger = setup_logging()
    logger.info("fetch_lyrics invoked")

    current_song = os.environ.get("CURRENT_SONG", "").strip()
    artist = os.environ.get("ARTIST", "").strip()
    title = os.environ.get("TITLE", "").strip()
    album = os.environ.get("ALBUM", "").strip() or None
    duration_raw = os.environ.get("DURATION", "").strip()

    if not current_song or not artist or not title:
        logger.info("Missing metadata, skipping")
        return 0

    duration = None
    if duration_raw:
        try:
            duration = float(duration_raw)
        except ValueError:
            logger.warning("Invalid DURATION: %s", duration_raw)

    try:
        lrc_path = resolve_lrc_path(current_song)
    except ValueError as e:
        logger.error("Invalid current song path: %s", e)
        return 1
    if lrc_path.exists():
        logger.info("Lyrics already exist at %s, skipping", lrc_path)
        return 0

    logger.info("Fetching lyrics for %s - %s", artist, title)
    try:
        synced_lyrics = fetch_lyrics_from_lrclib(artist, title, album, duration)
    except Exception:
        logger.exception("Failed to fetch lyrics for %s - %s", artist, title)
        return 1

    if synced_lyrics is None:
        logger.info("Lyrics not found on LRCLIB")
        return 0

    try:
        lrc_path.parent.mkdir(parents=True, exist_ok=True)
        lrc_path.write_text(synced_lyrics, encoding="utf-8")
        logger.info("Saved lyrics to %s", lrc_path)
        return 0
    except OSError as e:
        logger.error("Failed to write lyrics to %s: %s", lrc_path, e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
