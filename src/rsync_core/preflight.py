"""Preflight celu przed synchronizacja i weryfikacja po synchronizacji."""

import os
import subprocess
from pathlib import Path

COUNT_LIMIT = 1000
SAMPLE_LIMIT = 20


def count_files_limited(path: Path, limit: int = COUNT_LIMIT) -> tuple[int, bool]:
    """Liczy pliki rekurencyjnie do limitu, bez pelnego skanowania ogromnych drzew."""
    count = 0
    for _, _, files in os.walk(path):
        count += len(files)
        if count >= limit:
            return limit, True
    return count, False


def sample_target_entries(path: Path, limit: int = SAMPLE_LIMIT) -> list[str]:
    """Zwraca probe wpisow z targetu, bez pelnego skanu."""
    sample: list[str] = []
    try:
        for entry in sorted(path.iterdir(), key=lambda p: p.name)[:limit]:
            suffix = "/" if entry.is_dir() else ""
            sample.append(f"{entry.name}{suffix}")
    except Exception:
        return []
    return sample


def print_target_size_classification(target: Path, newly_created: bool = False) -> None:
    """Wypisuje szybka klasyfikacje wielkosci targetu."""
    if newly_created:
        print("0 files: target folder was newly created", flush=True)
        return

    count, reached_limit = count_files_limited(target, limit=COUNT_LIMIT)
    if count == 0:
        print("0 files: target folder was empty", flush=True)
    elif reached_limit:
        print("1000+ files: target folder may be very hard to check for additional files to delete", flush=True)
    else:
        print(f"{count} files: target folder contains existing data", flush=True)


def preflight_target_folder(target_folder: Path) -> bool:
    """Szybki preflight celu przed synchronizacja."""
    if not target_folder.exists():
        target_folder.mkdir(parents=True, exist_ok=True)
        print_target_size_classification(target_folder, newly_created=True)
        return True

    print_target_size_classification(target_folder, newly_created=False)

    # Sprawdzanie pustosci bez pelnego skanowania
    try:
        is_empty = next(target_folder.iterdir(), None) is None
    except Exception as exc:
        print(f"❌ Nie mozna odczytac target folder: {exc}", flush=True)
        return False

    if is_empty:
        return True

    print("⚠️ Target folder is not empty.", flush=True)
    sample = sample_target_entries(target_folder, limit=SAMPLE_LIMIT)
    if sample:
        print(f"   Sample entries (first {len(sample)}):", flush=True)
        for item in sample:
            print(f"   - {item}", flush=True)

    while True:
        decision = input("   Co robimy? [1=Continue as resume, 2=Cancel] (domyslnie 2): ").strip()
        if decision == "1":
            return True
        if decision in ["", "2"]:
            return False
        print("   Wpisz 1 lub 2")


def verify_file_sync(source_file: Path, destination_file: Path) -> bool:
    """Weryfikuje przeslany plik przez porownanie rozmiarow."""
    if not destination_file.exists() or not destination_file.is_file():
        print(f"  ❌ Brak pliku docelowego: {destination_file}", flush=True)
        return False

    if source_file.stat().st_size != destination_file.stat().st_size:
        print(f"  ❌ Rozmiar pliku rozny: {source_file.name}", flush=True)
        return False

    return True


def verify_folder_sync_size_only(source_folder: Path, destination_folder: Path) -> bool:
    """Szybka weryfikacja po synchronizacji: tylko brakujace pliki i rozmiary."""
    cmd = [
        "rsync",
        "-rni",
        "--size-only",
        "--no-perms",
        "--no-owner",
        "--no-group",
        "--omit-dir-times",
        str(source_folder) + "/",
        str(destination_folder) + "/",
    ]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception as exc:
        print(f"  ❌ Blad weryfikacji: {exc}", flush=True)
        return False

    if result.returncode != 0:
        print(f"  ❌ Weryfikacja zwrocila kod: {result.returncode}", flush=True)
        if result.stderr:
            print(f"  stderr: {result.stderr.strip()}", flush=True)
        return False

    pending = result.stdout.strip()
    if pending:
        print("  ❌ Weryfikacja nie przeszla - roznice (brakujace pliki lub inny rozmiar):", flush=True)
        print(pending, flush=True)
        return False

    print("  ✅ Weryfikacja rozmiarow OK", flush=True)
    return True
