import os
import sys
import tempfile
from pathlib import Path

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

import pytest

def test_resolve_lrc_path_rejects_absolute():
    with pytest.raises(ValueError, match="relative path"):
        fl.resolve_lrc_path("/etc/passwd")

def test_resolve_lrc_path_rejects_traversal():
    with pytest.raises(ValueError, match="Path traversal"):
        fl.resolve_lrc_path("../../../etc/passwd")

def test_resolve_lrc_path_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        fl.resolve_lrc_path("")
