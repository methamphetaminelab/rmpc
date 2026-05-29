#!/usr/bin/env python3
"""Fetch lyrics and notify rmpc via remote commands."""
import os
import subprocess
import sys

# Path to the original fetch_lyrics script
FETCH_SCRIPT = os.path.expanduser("~/.config/rmpc/scripts/fetch_lyrics.py")


def _rmpc_remote(*args):
    """Run rmpc remote with optional --pid from environment."""
    pid = os.environ.get("PID")
    cmd = ["rmpc", "remote"]
    if pid:
        cmd.extend(["--pid", pid])
    cmd.extend(args)
    subprocess.run(cmd, check=False)


def main():
    artist = os.environ.get("ARTIST", "Unknown Artist")
    title = os.environ.get("TITLE", "Unknown Title")

    # Run the original fetch_lyrics script
    result = subprocess.run(
        [sys.executable, FETCH_SCRIPT], capture_output=True, text=True
    )

    if result.returncode != 0:
        _rmpc_remote(
            "status",
            "--level",
            "error",
            f"Lyrics fetch failed: {artist} - {title}",
        )
        return result.returncode

    lrc_path = result.stdout.strip()
    if lrc_path:
        # Notify rmpc to index the new lyrics file
        _rmpc_remote("indexlrc", "--path", lrc_path)
        # Show a message in rmpc's status bar
        _rmpc_remote("status", f"Lyrics downloaded: {artist} - {title}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
