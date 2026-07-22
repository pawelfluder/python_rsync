"""
rsync_files/main.py - Synchronizacja plikow do QNAP przy uzyciu rsync (pytanie o kazda sciezke osobno).

Nastepca src/Rsync/rsync_v6.py po wydzieleniu wspolnej logiki do rsync_core - zachowuje
dokladnie to samo zachowanie: AA_Input/input.yaml, kolekcje YAML, pytanie o cel dla
kazdego source, domyslny cel /Volumes/qnap/01_todo_a, obecne potwierdzenia i opcjonalne
usuwanie zrodel.
"""

import shutil
import sys
from pathlib import Path

# Konfiguracja sciezek repozytorium
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SRC_ROOT = REPO_ROOT / "src"

# Dodanie repozytorium (dla modules/YamlParsing) i src/ (dla rsync_core) do sciezki importow.
sys.path.append(str(REPO_ROOT))
sys.path.append(str(SRC_ROOT))

from modules.YamlParsing.files_collections_yaml_parsing_v1 import load_file_collections_from_yaml

from rsync_core.extras import review_and_delete_extra_entries
from rsync_core.nas import ensure_nas
from rsync_core.preflight import preflight_target_folder, verify_file_sync, verify_folder_sync_size_only
from rsync_core.rsync_ops import build_rsync_progress_flags, run_rsync_with_live_output
from rsync_core.validation import ask_yes_no_default_no, confirm_pair, validate_pair

# Stale
DEFAULT_QNAP_TARGET = Path("/Volumes/qnap/01_todo_a")
INPUT_YAML_PATH = REPO_ROOT / "AA_Input" / "input.yaml"


def sync_file(source_file: Path, destination_file: Path) -> bool:
    """Synchronizuje pojedynczy plik bez --delete."""
    valid, reason = validate_pair(source_file, destination_file)
    if not valid:
        print(f"❌ Walidacja nieudana: {reason}", flush=True)
        return False

    if not confirm_pair(source_file, destination_file):
        print("  ⏭️ Pomijam na zyczenie uzytkownika", flush=True)
        return False

    ensure_nas()
    destination_file.parent.mkdir(parents=True, exist_ok=True)

    progress_flags = build_rsync_progress_flags()
    if len(progress_flags) == 1:
        print("  ℹ️ Wykryto starszy rsync - uzywam tylko --progress", flush=True)

    cmd = ["rsync", "-av", *progress_flags, str(source_file), str(destination_file)]
    if not run_rsync_with_live_output(cmd):
        return False

    return verify_file_sync(source_file, destination_file)


def sync_folder(source_folder: Path, destination_folder: Path) -> bool:
    """Synchronizuje folder bez --delete, a kasowanie dodatkow robi dopiero po dry-run."""
    valid, reason = validate_pair(source_folder, destination_folder)
    if not valid:
        print(f"❌ Walidacja nieudana: {reason}", flush=True)
        return False

    if not confirm_pair(source_folder, destination_folder):
        print("  ⏭️ Pomijam na zyczenie uzytkownika", flush=True)
        return False

    ensure_nas()

    print("\n🔎 Preflight target folder", flush=True)
    if not preflight_target_folder(destination_folder):
        print("  ❌ Anulowano po preflight", flush=True)
        return False

    progress_flags = build_rsync_progress_flags()
    if len(progress_flags) == 1:
        print("  ℹ️ Wykryto starszy rsync - uzywam tylko --progress", flush=True)

    print("  📦 Start normalnej synchronizacji (bez --delete)", flush=True)
    cmd_sync = [
        "rsync",
        "-av",
        *progress_flags,
        str(source_folder) + "/",
        str(destination_folder) + "/",
    ]
    if not run_rsync_with_live_output(cmd_sync):
        return False

    if not verify_folder_sync_size_only(source_folder, destination_folder):
        return False

    return review_and_delete_extra_entries(source_folder, destination_folder)


def delete_source_paths(source_paths: list[Path]) -> bool:
    """Usuwa zrodla po dwoch potwierdzeniach uzytkownika."""
    success = True
    for path in source_paths:
        try:
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  ✅ Usunieto folder: {path}", flush=True)
            elif path.is_file():
                path.unlink()
                print(f"  ✅ Usunieto plik: {path}", flush=True)
            else:
                print(f"  ⚠️ Sciezka juz nie istnieje: {path}", flush=True)
        except Exception as exc:
            print(f"  ❌ Blad usuwania {path}: {exc}", flush=True)
            success = False
    return success


def ask_delete_sources_double_confirm(source_paths: list[Path]) -> bool:
    """Podwojne potwierdzenie kasowania zrodel na samym koncu."""
    print("\n🗑️ Koncowa decyzja o usunieciu zrodel", flush=True)
    for path in source_paths:
        print(f"   - {path}", flush=True)

    first = ask_yes_no_default_no("   Czy usunac zrodla? (t/n, domyslnie n): ")
    if not first:
        print("   ℹ️ Zrodla pozostaly bez zmian", flush=True)
        return False

    second = ask_yes_no_default_no("   Potwierdzenie 2/2: na pewno usunac zrodla? (t/n, domyslnie n): ")
    if not second:
        print("   ℹ️ Anulowano na drugim potwierdzeniu", flush=True)
        return False

    return True


def sync_collection(collection_name: str, pairs: list[tuple[Path, Path]]) -> tuple[bool, list[Path]]:
    """Synchronizuje kolekcje (pary source -> destination) i zwraca status + faktycznie przetworzone zrodla."""
    print(f"\n📂 Synchronizacja kolekcji: {collection_name}", flush=True)

    success = True
    synced_sources: list[Path] = []

    for source_path, destination_path in pairs:
        if source_path.is_file():
            item_ok = sync_file(source_path, destination_path)
        elif source_path.is_dir():
            item_ok = sync_folder(source_path, destination_path)
        else:
            print(f"⚠️ Nieznany typ lub brak wpisu: {source_path}", flush=True)
            item_ok = False

        if item_ok:
            synced_sources.append(source_path)
        else:
            success = False

    return success, synced_sources


def get_target_paths_from_user(collections: dict[str, list[Path]]) -> dict[str, list[tuple[Path, Path]]]:
    """Dla kazdej sciezki source pyta o docelowa sciezke (domyslnie: DEFAULT_QNAP_TARGET/nazwa)."""
    resolved: dict[str, list[tuple[Path, Path]]] = {}
    for collection_name, source_paths in collections.items():
        pairs: list[tuple[Path, Path]] = []
        for source_path in source_paths:
            default_target = DEFAULT_QNAP_TARGET / source_path.name
            user_input = input(f"\n📁 {source_path}\n   -> Podaj sciezke docelowa (domyslnie: {default_target}): ").strip()
            target_path = Path(user_input).expanduser() if user_input else default_target
            pairs.append((source_path, target_path))
        resolved[collection_name] = pairs
    return resolved


def main() -> None:
    """Glowna funkcja skryptu."""
    print("🔍 Wczytywanie konfiguracji synchronizacji...", flush=True)

    if not INPUT_YAML_PATH.exists():
        print(f"❌ Plik konfiguracji nie istnieje: {INPUT_YAML_PATH}", flush=True)
        return

    try:
        collections = load_file_collections_from_yaml(str(INPUT_YAML_PATH))
    except Exception as exc:
        print(f"❌ Blad wczytywania YAML: {exc}", flush=True)
        return

    if not collections:
        print("⚠️ Brak kolekcji do synchronizacji w pliku YAML", flush=True)
        return

    resolved_collections = get_target_paths_from_user(collections)

    print(f"\n🔍 Sprawdzanie dostepnosci QNAP: {DEFAULT_QNAP_TARGET.parent}", flush=True)
    ensure_nas(DEFAULT_QNAP_TARGET.parent)

    overall_success = True
    all_synced_sources: list[Path] = []

    for collection_name, pairs in resolved_collections.items():
        collection_ok, synced_sources = sync_collection(collection_name, pairs)
        all_synced_sources.extend(synced_sources)
        if not collection_ok:
            overall_success = False

    # Zawsze pytamy na koncu o usuniecie zrodel, ale usuwanie tylko po podwojnym potwierdzeniu.
    if all_synced_sources and ask_delete_sources_double_confirm(all_synced_sources):
        if not delete_source_paths(all_synced_sources):
            overall_success = False

    print("\n" + "=" * 50, flush=True)
    if overall_success:
        print("✅ Synchronizacja zakonczona pomyslnie!", flush=True)
    else:
        print("⚠️ Synchronizacja zakonczona z bledami (sprawdz logi powyzej)", flush=True)
    print("=" * 50, flush=True)


if __name__ == "__main__":
    main()
