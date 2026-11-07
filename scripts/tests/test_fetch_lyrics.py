import json
import os
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

def test_fetch_lyrics_fallback_search():
    """Test fallback to search API when direct get returns 404."""
    def side_effect(req, **kwargs):
        url = req.get_full_url()
        if "/api/get?" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        elif "/api/search?" in url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps([
                {
                    "trackName": "Glubina",
                    "syncedLyrics": "[00:10.91] Оу\n[00:12.86] На-на..."
                }
            ]).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp
        else:
            raise RuntimeError(f"Unexpected URL: {url}")

    with patch("urllib.request.urlopen", side_effect=side_effect):
        result = fl.fetch_lyrics_from_lrclib("Depo Boulevard", "Glubina", None, None)
        assert result == "[00:10.91] Оу\n[00:12.86] На-на..."

def test_fetch_lyrics_fallback_search_no_match():
    """Test fallback search returns None when no matching track found."""
    def side_effect(req, **kwargs):
        url = req.get_full_url()
        if "/api/get?" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        elif "/api/search?" in url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps([
                {
                    "trackName": "Different Track",
                    "syncedLyrics": "[00:00.00]Lyrics"
                }
            ]).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp
        else:
            raise RuntimeError(f"Unexpected URL: {url}")

    with patch("urllib.request.urlopen", side_effect=side_effect):
        result = fl.fetch_lyrics_from_lrclib("Depo Boulevard", "Glubina", None, None)
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

def test_main_skips_when_file_exists():
    with tempfile.TemporaryDirectory() as tmp:
        music_dir = Path(tmp) / "Music"
        music_dir.mkdir()
        lrc_dir = music_dir / "Lyrics" / "Artist" / "Album"
        lrc_dir.mkdir(parents=True)
        lrc_file = lrc_dir / "song.lrc"
        lrc_file.write_text("[00:00.00]Existing")

        orig_music_dir = fl.MUSIC_DIR
        orig_log_file = fl.LOG_FILE
        log_path = Path(tmp) / "test.log"
        fl.LOG_FILE = log_path
        fl.MUSIC_DIR = music_dir
        try:
            os.environ["CURRENT_SONG"] = "Artist/Album/song.flac"
            os.environ["ARTIST"] = "Artist"
            os.environ["TITLE"] = "Title"
            os.environ["ALBUM"] = "Album"
            os.environ["DURATION"] = "245.5"
            assert fl.main() == 0
            # File should remain unchanged
            assert lrc_file.read_text() == "[00:00.00]Existing"
        finally:
            fl.MUSIC_DIR = orig_music_dir
            fl.LOG_FILE = orig_log_file
            for k in ("CURRENT_SONG", "ARTIST", "TITLE", "ALBUM", "DURATION"):
                os.environ.pop(k, None)

def test_main_fetches_and_saves():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "syncedLyrics": "[00:12.34]Line 1\n[00:15.67]Line 2"
    }).encode()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with tempfile.TemporaryDirectory() as tmp:
        music_dir = Path(tmp) / "Music"
        music_dir.mkdir()
        orig_music_dir = fl.MUSIC_DIR
        orig_log_file = fl.LOG_FILE
        log_path = Path(tmp) / "test.log"
        fl.LOG_FILE = log_path
        fl.MUSIC_DIR = music_dir
        try:
            os.environ["CURRENT_SONG"] = "Artist/Album/song.flac"
            os.environ["ARTIST"] = "Artist"
            os.environ["TITLE"] = "Title"
            os.environ["ALBUM"] = "Album"
            os.environ["DURATION"] = "245.5"

            with patch("urllib.request.urlopen", return_value=mock_response):
                assert fl.main() == 0

            lrc_file = music_dir / "Lyrics" / "Artist" / "Album" / "song.lrc"
            assert lrc_file.exists()
            assert "[00:12.34]Line 1" in lrc_file.read_text()
        finally:
            fl.MUSIC_DIR = orig_music_dir
            fl.LOG_FILE = orig_log_file
            for k in ("CURRENT_SONG", "ARTIST", "TITLE", "ALBUM", "DURATION"):
                os.environ.pop(k, None)

def test_main_missing_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        orig_log_file = fl.LOG_FILE
        log_path = Path(tmp) / "test.log"
        fl.LOG_FILE = log_path
        try:
            os.environ.pop("CURRENT_SONG", None)
            os.environ.pop("ARTIST", None)
            os.environ.pop("TITLE", None)
            assert fl.main() == 0
        finally:
            fl.LOG_FILE = orig_log_file


def test_normalize_whitespace():
    assert fl._normalize("No Flag  (Prod. by Dante)") == "No Flag (Prod. by Dante)"
    assert fl._normalize("  Boulevard   Depo  ") == "Boulevard Depo"
    assert fl._normalize("already clean") == "already clean"


def test_parse_duration():
    assert fl._parse_duration("245.5") == 245.5
    assert fl._parse_duration("2:21") == 141.0
    assert fl._parse_duration("1:02:30") == 3750.0
    assert fl._parse_duration("") is None
    assert fl._parse_duration("invalid") is None


def test_swap_artist_name():
    assert fl._swap_artist_name("Depo Boulevard") == "Boulevard Depo"
    assert fl._swap_artist_name("Boulevard Depo") == "Depo Boulevard"
    assert fl._swap_artist_name("Three Word Name") is None
    assert fl._swap_artist_name("Single") is None


def test_fetch_lyrics_swapped_artist_fallback():
    """Test fallback with swapped artist name when direct get returns 404."""
    def side_effect(req, **kwargs):
        url = req.get_full_url()
        if "artist_name=Depo+Boulevard" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        elif "artist_name=Boulevard+Depo" in url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "syncedLyrics": "[00:00.00]Swapped"
            }).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp
        else:
            raise RuntimeError(f"Unexpected URL: {url}")

    with patch("urllib.request.urlopen", side_effect=side_effect):
        result = fl.fetch_lyrics_from_lrclib("Depo Boulevard", "No Flag", None, None)
        assert result == "[00:00.00]Swapped"


def test_fetch_lyrics_fuzzy_search_match():
    """Test fuzzy title matching in search fallback."""
    def side_effect(req, **kwargs):
        url = req.get_full_url()
        if "/api/get?" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        elif "/api/search?" in url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps([
                {
                    "trackName": "No Flag (Prod. by Dante)",
                    "artistName": "Boulevard Depo",
                    "syncedLyrics": "[00:00.00]Fuzzy"
                }
            ]).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp
        else:
            raise RuntimeError(f"Unexpected URL: {url}")

    with patch("urllib.request.urlopen", side_effect=side_effect):
        # Title has double space — should fuzzy-match after normalization
        result = fl.fetch_lyrics_from_lrclib("Depo Boulevard", "No Flag  (Prod. by Dante)", None, None)
        assert result == "[00:00.00]Fuzzy"


def test_main_parses_mmss_duration():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "syncedLyrics": "[00:12.34]Line 1\n[00:15.67]Line 2"
    }).encode()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with tempfile.TemporaryDirectory() as tmp:
        music_dir = Path(tmp) / "Music"
        music_dir.mkdir()
        orig_music_dir = fl.MUSIC_DIR
        orig_log_file = fl.LOG_FILE
        log_path = Path(tmp) / "test.log"
        fl.LOG_FILE = log_path
        fl.MUSIC_DIR = music_dir
        try:
            os.environ["CURRENT_SONG"] = "Artist/Album/song.flac"
            os.environ["ARTIST"] = "Artist"
            os.environ["TITLE"] = "Title"
            os.environ["ALBUM"] = "Album"
            os.environ["DURATION"] = "2:21"  # MM:SS format

            with patch("urllib.request.urlopen", return_value=mock_response):
                assert fl.main() == 0

            lrc_file = music_dir / "Lyrics" / "Artist" / "Album" / "song.lrc"
            assert lrc_file.exists()
        finally:
            fl.MUSIC_DIR = orig_music_dir
            fl.LOG_FILE = orig_log_file
            for k in ("CURRENT_SONG", "ARTIST", "TITLE", "ALBUM", "DURATION"):
                os.environ.pop(k, None)

def test_resolve_lrc_path_stream_uri_has_no_colons():
    # Mopidy отдаёт адреса вида youtube:video:ID; ':' запрещён на NTFS
    path = fl.resolve_lrc_path("youtube:video:yIDJrW43fKE")
    assert path == fl.MUSIC_DIR / "Lyrics" / "youtube" / "video" / "yIDJrW43fKE.lrc"

def test_with_tags_adds_metadata_for_rmpc_index():
    # rmpc находит текст по [ar:]/[ti:]/[al:] внутри файла, не по имени
    text = fl.with_tags("[00:01.00]x", "rizza", "limbo", "greater than one")
    assert text.splitlines()[:3] == ["[ar:rizza]", "[al:limbo]", "[ti:greater than one]"]
    assert text.endswith("[00:01.00]x")

def test_with_tags_keeps_existing_tags():
    assert fl.with_tags("[ti:t]\n[00:01.00]x", "a", None, "t") == "[ti:t]\n[00:01.00]x"

def test_resolve_lrc_path_online_url():
    # mpd-online: треки в очереди MPD — ссылки на локальный резолвер
    path = fl.resolve_lrc_path("http://127.0.0.1:6611/dz/349125841")
    assert path == fl.MUSIC_DIR / "Lyrics" / "online" / "dz" / "349125841.lrc"
