#!/usr/bin/env python3
"""Auto-fetch .lrc lyrics for rmpc via LRCLIB API."""
from __future__ import annotations

import fcntl
import json
import logging
import os
import re
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


def _acquire_fetch_lock(lrc_path: Path) -> int | None:
    """Acquire an exclusive, non-blocking file lock for the given lrc path.

    Returns the file descriptor on success, or None if another process holds the lock.
    """
    lock_path = lrc_path.with_suffix(lrc_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except (BlockingIOError, OSError):
        os.close(fd)
        return None


def _release_fetch_lock(fd: int, lrc_path: Path) -> None:
    """Release the lock and clean up the lock file."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except OSError:
        pass
    lock_path = lrc_path.with_suffix(lrc_path.suffix + ".lock")
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass


def _normalize(s: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", s.strip())


def _parse_duration(raw: str) -> float | None:
    """Parse duration: float seconds or MM:SS / HH:MM:SS."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        pass
    parts = raw.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 2:  # MM:SS
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:  # HH:MM:SS
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def _swap_artist_name(artist: str) -> str | None:
    """If artist looks like 'First Last', try 'Last First'."""
    parts = artist.split()
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    return None


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
            artist_lower = artist.lower()
            title_lower = title.lower()
            best_match = None
            best_score = 0
            for track in data:
                track_artist = track.get("artistName", "").lower()
                track_title = track.get("trackName", "").lower()

                # Exact title match → immediate win
                if track_title == title_lower:
                    return track.get("syncedLyrics") or None

                # Fuzzy title match (one contains the other)
                title_score = 0
                if title_lower in track_title or track_title in title_lower:
                    title_score = 1

                # Artist similarity
                artist_score = 0
                if artist_lower == track_artist:
                    artist_score = 2
                elif artist_lower in track_artist or track_artist in artist_lower:
                    artist_score = 1
                elif _swap_artist_name(artist_lower) == track_artist:
                    artist_score = 2
                elif _swap_artist_name(artist_lower) in track_artist:
                    artist_score = 1

                score = title_score + artist_score
                if score > best_score:
                    best_score = score
                    best_match = track

            if best_match and best_score >= 2:
                return best_match.get("syncedLyrics") or None
    except Exception:
        pass
    return None


def fetch_lyrics_from_lrclib(
    artist: str, title: str, album: str | None, duration: float | None
) -> str | None:
    """Query LRCLIB for synced lyrics. Returns None if not found or on error."""
    artist = _normalize(artist)
    title = _normalize(title)
    if album:
        album = _normalize(album)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _try_fetch_lrclib(artist, title, album, duration)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Try swapped artist name (e.g. "Depo Boulevard" → "Boulevard Depo")
                swapped = _swap_artist_name(artist)
                if swapped:
                    try:
                        return _try_fetch_lrclib(swapped, title, album, duration)
                    except urllib.error.HTTPError as e2:
                        if e2.code != 404:
                            last_error = e2
                    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e2:
                        last_error = e2
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

    duration = _parse_duration(duration_raw) if duration_raw else None
    if duration_raw and duration is None:
        logger.warning("Invalid DURATION: %s", duration_raw)

    try:
        lrc_path = resolve_lrc_path(current_song)
    except ValueError as e:
        logger.error("Invalid current song path: %s", e)
        return 1
    if lrc_path.exists():
        logger.info("Lyrics already exist at %s, skipping", lrc_path)
        return 0

    lock_fd = _acquire_fetch_lock(lrc_path)
    if lock_fd is None:
        logger.info("Another process is fetching lyrics for %s, skipping", lrc_path)
        return 0

    try:
        # Double-check inside the lock in case another process just finished
        if lrc_path.exists():
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
            # Print path so callers can notify rmpc about the new file
            print(lrc_path)
            return 0
        except OSError as e:
            logger.error("Failed to write lyrics to %s: %s", lrc_path, e)
            return 1
    finally:
        _release_fetch_lock(lock_fd, lrc_path)


if __name__ == "__main__":
    raise SystemExit(main())
