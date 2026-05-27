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
