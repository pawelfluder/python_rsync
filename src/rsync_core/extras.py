"""Obsluga dodatkowych plikow: wykrywanie i kasowanie wpisow istniejacych tylko w destination."""

import subprocess
from pathlib import Path

from rsync_core.rsync_ops import run_rsync_with_live_output
from rsync_core.validation import ask_yes_no_default_no

DELETE_PREVIEW_LIMIT = 50


def detect_destination_only_entries(source_folder: Path, destination_folder: Path) -> list[str]:
    """Wykrywa wpisy istniejące tylko po stronie docelowej (dry-run z --delete)."""
    if not destination_folder.exists():
        return []

    cmd = [
        "rsync",
        "-rni",
        "--delete",
        str(source_folder) + "/",
        str(destination_folder) + "/",
    ]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception as exc:
        print(f"  ⚠️ Nie udalo sie wykonac dry-run delete: {exc}", flush=True)
        return []

    if result.returncode != 0:
        print(f"  ⚠️ Dry-run delete zwrocil kod {result.returncode}", flush=True)
        if result.stderr:
            print(f"  stderr: {result.stderr.strip()}", flush=True)
        return []

    extras: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("*deleting "):
            extras.append(stripped.replace("*deleting ", "", 1))
    return extras


def apply_delete_on_destination(source_folder: Path, destination_folder: Path) -> bool:
    """Kasuje wpisy dodatkowe po stronie docelowej przez rsync --delete po potwierdzeniu."""
    cmd = [
        "rsync",
        "-av",
        "--delete",
        str(source_folder) + "/",
        str(destination_folder) + "/",
    ]
    return run_rsync_with_live_output(cmd)


def review_and_delete_extra_entries(
    source_folder: Path, destination_folder: Path, preview_limit: int = DELETE_PREVIEW_LIMIT
) -> bool:
    """Wykrywa i (po potwierdzeniu) kasuje wpisy istniejace tylko w destination.

    Zwraca False tylko wtedy, gdy uzytkownik zgodzil sie na usuniecie a samo
    usuwanie (apply_delete_on_destination) sie nie powiodlo.
    """
    print("\n🧪 Dry-run delete po synchronizacji", flush=True)
    extras = detect_destination_only_entries(source_folder, destination_folder)
    if not extras:
        print("  ✅ Brak dodatkowych wpisow do usuniecia", flush=True)
        return True

    print(f"  ⚠️ Dodatkowe wpisy tylko w target: {len(extras)}", flush=True)
    for item in extras[:preview_limit]:
        print(f"   - {item}", flush=True)
    if len(extras) > preview_limit:
        print(f"   ... i jeszcze {len(extras) - preview_limit} wiecej", flush=True)

    if ask_yes_no_default_no("  Czy usunac te dodatkowe wpisy z target? (t/n, domyslnie n): "):
        print("  🧹 Uruchamiam rsync z --delete po potwierdzeniu", flush=True)
        if not apply_delete_on_destination(source_folder, destination_folder):
            return False
    else:
        print("  ℹ️ Pozostawiono dodatkowe wpisy w target", flush=True)

    return True
