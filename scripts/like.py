#!/usr/bin/env python3
"""Лайк как в Spotify: треки ↔ плейлист MPD «Liked» (новые сверху).

Вызывается из rmpc (ExternalCommand, клавиша L). Что лайкать:
- фокус в очереди/поиске/плейлисте — выделенный трек или отмеченные пробелом (SELECTED_SONGS);
- иначе — играющий трек (CURRENT_SONG).
Если все выбранные уже лайкнуты — лайк снимается, иначе ставится тем, у кого его нет.
Работает и для локальных, и для онлайн-треков mpd-online (в плейлисте хранится ссылка).
"""
import os
import subprocess
import sys

from mpd import CommandError, MPDClient

PLAYLIST = "Liked"
MAX_AT_ONCE = 25  # альбом пройдёт, вся выдача поиска — нет


def status(text: str, level: str = "info") -> None:
    cmd = ["rmpc", "remote"]
    if os.environ.get("PID"):
        cmd += ["--pid", os.environ["PID"]]
    subprocess.run(cmd + ["status", "--level", level, text], check=False)


def targets(env) -> list[str]:
    selected = [f for f in env.get("SELECTED_SONGS", "").split("\n") if f]
    return selected or ([env["CURRENT_SONG"]] if env.get("CURRENT_SONG") else [])


def apply(client, files: list[str]) -> bool:
    """True — лайки поставлены, False — сняты."""
    try:
        liked = client.listplaylist(PLAYLIST)
    except CommandError:  # плейлиста ещё нет
        liked = []
    if all(f in liked for f in files):
        for pos in sorted((i for i, f in enumerate(liked) if f in files), reverse=True):
            client.playlistdelete(PLAYLIST, pos)
        return False
    for f in reversed([f for f in files if f not in liked]):
        client.playlistadd(PLAYLIST, f, 0)
    return True


def name(client: MPDClient, file: str) -> str:
    found = client.playlistfind("file", file) or (client.find("file", file) if "://" not in file else [])
    if found and found[0].get("title"):
        return f"{found[0].get('artist', '?')} - {found[0]['title']}"
    return "1 track"


def main() -> int:
    files = targets(os.environ)
    if not files:
        status("Nothing selected or playing", "warn")
        return 0
    if len(files) > MAX_AT_ONCE:  # фокус на полях поиска: rmpc передаёт всю выдачу
        status(f"{len(files)} tracks at once — select a track in the results (or mark with Space)", "warn")
        return 0
    client = MPDClient()
    client.connect("127.0.0.1", int(os.environ.get("MPD_PORT", 6600)))
    what = name(client, files[0]) if len(files) == 1 else f"{len(files)} tracks"
    status(f"♥ Liked: {what}" if apply(client, files) else f"Removed from Liked: {what}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
