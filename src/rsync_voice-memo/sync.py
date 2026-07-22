"""Kopiowanie nagran .m4a z lokalnego katalogu Voice Memos na QNAP przez wspolny rsync_core.

Tylko nagrania (--include='*/' --include='*.m4a' --exclude='*'), nigdy --delete.
Brak SQLite, manifestu JSON, stagingu czy lokalnego folderu eksportu - kopia idzie
bezposrednio source -> destination.
"""

import subprocess
from pathlib import Path

from rsync_core.rsync_ops import build_rsync_progress_flags, run_rsync_with_live_output

VOICE_MEMO_FILTERS = ["--include=*/", "--include=*.m4a", "--exclude=*"]


def build_voice_memo_rsync_cmd(source: Path, destination: Path, dry_run: bool = False) -> list[str]:
    """Buduje komende rsync tylko dla nagran .m4a. Nigdy nie dodaje --delete."""
    archive_flags = "-avn" if dry_run else "-av"
    progress_flags = [] if dry_run else build_rsync_progress_flags()

    return [
        "rsync",
        archive_flags,
        *progress_flags,
        *VOICE_MEMO_FILTERS,
        str(source) + "/",
        str(destination) + "/",
    ]


def run_voice_memo_dry_run(source: Path, destination: Path) -> str:
    """Wykonuje dry-run i zwraca surowy output rsync (do wypisania uzytkownikowi przed kopiowaniem)."""
    cmd = build_voice_memo_rsync_cmd(source, destination, dry_run=True)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return result.stdout


def sync_voice_memos(source: Path, destination: Path) -> bool:
    """Kopiuje nagrania .m4a z source do destination przez wspolny rsync_core (bez --delete)."""
    destination.mkdir(parents=True, exist_ok=True)
    cmd = build_voice_memo_rsync_cmd(source, destination, dry_run=False)
    return run_rsync_with_live_output(cmd)
