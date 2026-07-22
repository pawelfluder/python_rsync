"""Kopiowanie nagran .m4a z lokalnego katalogu Voice Memos na QNAP przez wspolny rsync_core.

Tylko nagrania (--include='*/' --include='*.m4a' --exclude='*'), nigdy --delete.
Brak SQLite, manifestu JSON, stagingu czy lokalnego folderu eksportu - kopia idzie
bezposrednio source -> destination.
"""

import subprocess
import tempfile
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


def _write_files_from_list(selected_files: list[Path]) -> Path:
    """Zapisuje nazwy wybranych plikow (wzgledem source, po jednej w linii) do pliku tymczasowego dla --files-from."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    try:
        for file_path in selected_files:
            tmp.write(f"{file_path.name}\n")
    finally:
        tmp.close()
    return Path(tmp.name)


def build_selected_files_rsync_cmd(source: Path, destination: Path, files_from: Path, dry_run: bool = False) -> list[str]:
    """Buduje komende rsync kopiujaca TYLKO pliki z listy `files_from` (--files-from). Nigdy --delete."""
    archive_flags = "-avn" if dry_run else "-av"
    progress_flags = [] if dry_run else build_rsync_progress_flags()

    return [
        "rsync",
        archive_flags,
        *progress_flags,
        f"--files-from={files_from}",
        str(source) + "/",
        str(destination) + "/",
    ]


def run_dry_run_for_selected_files(source: Path, destination: Path, selected_files: list[Path]) -> str:
    """Dry-run tylko dla numerowanej selekcji uzytkownika (nie dla calego source), bez --delete."""
    files_from = _write_files_from_list(selected_files)
    try:
        cmd = build_selected_files_rsync_cmd(source, destination, files_from, dry_run=True)
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        return result.stdout
    finally:
        files_from.unlink(missing_ok=True)


def copy_selected_files(source: Path, destination: Path, selected_files: list[Path]) -> bool:
    """Kopiuje TYLKO numerowana selekcje uzytkownika przez wspolny rsync_core. Nigdy --delete."""
    destination.mkdir(parents=True, exist_ok=True)
    files_from = _write_files_from_list(selected_files)
    try:
        cmd = build_selected_files_rsync_cmd(source, destination, files_from, dry_run=False)
        return run_rsync_with_live_output(cmd)
    finally:
        files_from.unlink(missing_ok=True)
