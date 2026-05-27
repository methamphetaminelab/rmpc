import json
import sys
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import fetch_lyrics as fl

def test_setup_logging_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "test.log"
        # monkey-patch LOG_FILE
        orig_log_file = fl.LOG_FILE
        fl.LOG_FILE = log_path
        try:
            logger = fl.setup_logging()
            logger.info("test message")
            assert log_path.exists()
            content = log_path.read_text()
            assert "test message" in content
        finally:
            fl.LOG_FILE = orig_log_file

def test_resolve_lrc_path():
    with tempfile.TemporaryDirectory() as tmp:
        music_dir = Path(tmp) / "Music"
        music_dir.mkdir()
        orig_music_dir = fl.MUSIC_DIR
        fl.MUSIC_DIR = music_dir
        try:
            path = fl.resolve_lrc_path("Artist/Album/song.flac")
            expected = music_dir / "Lyrics" / "Artist" / "Album" / "song.lrc"
            assert path == expected
        finally:
            fl.MUSIC_DIR = orig_music_dir

def test_resolve_lrc_path_rejects_absolute():
    with pytest.raises(ValueError, match="relative path"):
        fl.resolve_lrc_path("/etc/passwd")

def test_resolve_lrc_path_rejects_traversal():
    with pytest.raises(ValueError, match="Path traversal"):
        fl.resolve_lrc_path("../../../etc/passwd")

def test_resolve_lrc_path_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        fl.resolve_lrc_path("")

def test_fetch_lyrics_success():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "syncedLyrics": "[00:12.34]Line 1\n[00:15.67]Line 2"
    }).encode()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = fl.fetch_lyrics_from_lrclib("Artist", "Title", "Album", 245.5)
        assert result == "[00:12.34]Line 1\n[00:15.67]Line 2"

def test_fetch_lyrics_not_found():
    error = urllib.error.HTTPError(
        "https://lrclib.net/api/get", 404, "Not Found", {}, None
    )
    with patch("urllib.request.urlopen", side_effect=error):
        result = fl.fetch_lyrics_from_lrclib("Artist", "Title", None, None)
        assert result is None

def test_fetch_lyrics_retry_then_success():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "syncedLyrics": "[00:00.00]Works"
    }).encode()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    side_effects = [urllib.error.URLError("timeout"), mock_response]
    with patch("urllib.request.urlopen", side_effect=side_effects), \
         patch("fetch_lyrics.time.sleep"):
        result = fl.fetch_lyrics_from_lrclib("A", "B", None, None)
        assert result == "[00:00.00]Works"

def test_fetch_lyrics_exhausted_retries():
    side_effects = [
        urllib.error.URLError("timeout 1"),
        urllib.error.URLError("timeout 2"),
        urllib.error.URLError("timeout 3"),
    ]
    with patch("urllib.request.urlopen", side_effect=side_effects), \
         patch("fetch_lyrics.time.sleep"):
        with pytest.raises(urllib.error.URLError, match="timeout 3"):
            fl.fetch_lyrics_from_lrclib("A", "B", None, None)
