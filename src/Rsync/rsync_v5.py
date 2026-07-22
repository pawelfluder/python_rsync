"""
rsync_sync_v5.py - Synchronizacja plikow do QNAP przy uzyciu rsync (poprawione potwierdzenia)

Zmiany wzgledem v3:
- confirm_pair() pyta o potwierdzenie TYLKO gdy target istnieje i nie jest pusty
- Gdy target nie istnieje lub jest pusty - automatycznie kontynuuje (bezpieczne)
- Gdy target istnieje i ma dane - pyta o potwierdzenie (ochrona przed nadpisaniem)
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Konfiguracja sciezek repozytorium
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]

# Dodanie repozytorium do sciezki importow
sys.path.append(str(REPO_ROOT))

# Importy z modulow projektu
from modules.YamlParsing.files_collections_yaml_parsing_v1 import load_file_collections_from_yaml
from modules.RetryNetworkDrive.retry_network_drive_v2 import ensure_nas_available

# Stale
DEFAULT_QNAP_TARGET = Path(os.getenv("qnap_default_target", "/Volumes/qnap"))
INPUT_YAML_PATH = REPO_ROOT / "AA_Input" / "input.yaml"
COUNT_LIMIT = 1000
SAMPLE_LIMIT = 20
DELETE_PREVIEW_LIMIT = 50


def rsync_supports_info_flags() -> bool:
    """Sprawdza, czy rsync wspiera flagi --info=progress2 i --info=name0."""
    try:
        result = subprocess.run(["rsync", "--version"], check=False, capture_output=True, text=True)
        if result.returncode != 0:
            return False
        first_line = (result.stdout.splitlines() or [""])[0].lower()
        return "version 3." in first_line or "version 4." in first_line
    except Exception:
        return False


def build_rsync_progress_flags() -> list[str]:
    """Zwraca kompatybilne flagi postepu dla zainstalowanej wersji rsync."""
    if rsync_supports_info_flags():
        return ["--progress", "--info=progress2", "--info=name0"]
    return ["--progress"]


def ask_yes_no(prompt: str) -> bool:
    """Uniwersalne pytanie t/n."""
    while True:
        response = input(prompt).strip().lower()
        if response in ["t", "tak", "y", "yes"]:
            return True
        if response in ["n", "nie", "no"]:
            return False
        print("   Prosze wpisac 't' (tak) lub 'n' (nie)")


def ask_yes_no_default_no(prompt: str) -> bool:
    """Pytanie t/n, gdzie Enter oznacza NIE."""
    while True:
        response = input(prompt).strip().lower()
        if response == "":
            return False
        if response in ["t", "tak", "y", "yes"]:
            return True
        if response in ["n", "nie", "no"]:
            return False
        print("   Prosze wpisac 't' (tak) lub 'n' (nie)")


def is_suspicious_destructive_path(path: Path) -> bool:
    """Chroni przed potencjalnie niebezpiecznymi sciezkami."""
    resolved = path.resolve()
    if resolved == Path("/"):
        return True

    # Zbyt krotkie sciezki systemowe sa ryzykowne dla operacji destrukcyjnych.
    parts = [part for part in resolved.parts if part not in ["/"]]
    return len(parts) < 3


def validate_pair(source_path: Path, target_path: Path) -> tuple[bool, str]:
    """Waliduje pare source/target zanim ruszy synchronizacja."""
    if not str(source_path).strip():
        return False, "Pusta sciezka source"
    if not str(target_path).strip():
        return False, "Pusta sciezka target"

    source_resolved = source_path.resolve()
    target_resolved = target_path.resolve()

    if source_resolved == Path("/"):
        return False, "Source nie moze byc '/'"
    if target_resolved == Path("/"):
        return False, "Target nie moze byc '/'"

    if is_suspicious_destructive_path(source_resolved):
        return False, f"Podejrzanie krotka sciezka source: {source_resolved}"
    if is_suspicious_destructive_path(target_resolved):
        return False, f"Podejrzanie krotka sciezka target: {target_resolved}"

    if source_resolved == target_resolved:
        return False, "Source i target wskazuja ten sam katalog"

    if not source_resolved.exists():
        return False, f"Source nie istnieje: {source_resolved}"

    return True, ""


def confirm_pair(source_path: Path, target_path: Path) -> bool:
    """Pokazuje finalne sciezki i pyta o potwierdzenie TYLKO gdy target istnieje i ma dane.
    
    Feature: Smart Confirmation
    - Gdy target NIE istnieje: automatycznie kontynuuje (nowy folder - bezpieczne)
    - Gdy target istnieje ale jest pusty: automatycznie kontynuuje (pusty folder - bezpieczne)
    - Gdy target istnieje i ma dane: pyta o potwierdzenie (ochrona przed nadpisaniem)
    """
    target_resolved = target_path.resolve()
    
    # Sprawdz czy target istnieje i czy ma dane
    target_has_data = False
    if target_resolved.exists():
        try:
            # Sprawdz czy folder ma jakiekolwiek wpisy
            has_entries = next(target_resolved.iterdir(), None) is not None
            target_has_data = has_entries
        except (PermissionError, OSError):
            # Nie mozna odczytac - zakladamy ze ma dane dla bezpieczenstwa
            target_has_data = True
    
    print("\n🔐 Potwierdzenie pary synchronizacji:", flush=True)
    print(f"   Source: {source_path.resolve()}", flush=True)
    print(f"   Target: {target_path.resolve()}", flush=True)
    
    if not target_has_data:
        # Target nie istnieje lub jest pusty - automatycznie kontynuuje
        if target_has_data:
            print("   🟢 Target istnieje ale jest pusty - kontynuacja automatyczna", flush=True)
        else:
            print("   🟢 Target nie istnieje (nowy folder) - kontynuacja automatyczna", flush=True)
        return True
    
    # Target ma dane - pytamy o potwierdzenie
    print("   ⚠️ Target istnieje i zawiera dane!", flush=True)
    return ask_yes_no_default_no("   Kontynuowac te synchronizacje? (t/n, domyslnie n): ")


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


def run_rsync_with_live_output(cmd: list[str], retry: bool = True, retry_delay: int = 10) -> bool:
    """Uruchamia rsync i przekazuje output bezposrednio do terminala.
    
    Args:
        retry: Jeśli True, retry'uje w nieskonczonosc przy bledach polaczenia
        retry_delay: Czas oczekiwania miedzy probami (w sekundach)
    """
    attempt = 1
    while True:
        print(f"  ▶ {' '.join(cmd)} (prob {attempt})", flush=True)
        try:
            completed = subprocess.run(cmd, check=False, stdout=None, stderr=None)
            if completed.returncode == 0:
                print(f"  ✅ rsync zakonczyl pomyslnie", flush=True)
                return True
            
            # Kody bledow ktore wskazuja na problem z polaczeniem/siecia
            # i warto retry'owac:
            # 11 - error in file IO (pliki znikaja podczas transferu)
            # 12 - error in rsync protocol data stream (polaczenie przerwane)
            # 23 - partial transfer (niektore pliki nie zostaly przeniesione)
            # 24 - vanished source files (pliki zniknely podczas transferu)
            # 30 - timeout in data transfer
            retryable_codes = [11, 12, 23, 24, 30]
            
            if retry and completed.returncode in retryable_codes:
                print(f"  ⚠️ rsync zakonczyl sie kodem {completed.returncode} - prawdopodobnie problem z polaczeniem", flush=True)
                print(f"  🔄 Sprawdzam dostepnosc QNAP i probuje ponownie za {retry_delay}s...", flush=True)
                
                # Sprawdz czy NAS jest nadal dostepny
                target_path = Path("/Volumes/qnap")
                if not target_path.exists():
                    print(f"  ⚠️ QNAP niedostepny - probuje podlaczyc...", flush=True)
                    ensure_nas_available(target_path)
                else:
                    print(f"  ℹ️ QNAP dostepny, czekam {retry_delay}s i probuje ponownie...", flush=True)
                    time.sleep(retry_delay)
                
                attempt += 1
                continue
            
            # Inne kody bledow - nie retry'ujemy
            print(f"  ❌ rsync zakonczyl sie kodem: {completed.returncode}", flush=True)
            return False
            
        except Exception as exc:
            if retry:
                print(f"  ⚠️ Blad uruchamiania rsync: {exc}", flush=True)
                print(f"  🔄 Probujemy ponownie za {retry_delay}s...", flush=True)
                time.sleep(retry_delay)
                attempt += 1
                continue
            else:
                print(f"  ❌ Blad uruchamiania rsync: {exc}", flush=True)
                return False


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


def sync_file(source_file: Path, target_base: Path) -> bool:
    """Synchronizuje pojedynczy plik bez --delete."""
    destination_file = target_base / source_file.name

    valid, reason = validate_pair(source_file, destination_file)
    if not valid:
        print(f"❌ Walidacja nieudana: {reason}", flush=True)
        return False

    if not confirm_pair(source_file, destination_file):
        print("  ⏭️ Pomijam na zyczenie uzytkownika", flush=True)
        return False

    ensure_nas_available(target_base.parent)
    target_base.mkdir(parents=True, exist_ok=True)

    progress_flags = build_rsync_progress_flags()
    if len(progress_flags) == 1:
        print("  ℹ️ Wykryto starszy rsync - uzywam tylko --progress", flush=True)

    cmd = ["rsync", "-av", *progress_flags, str(source_file), str(destination_file)]
    if not run_rsync_with_live_output(cmd):
        return False

    return verify_file_sync(source_file, destination_file)


def sync_folder(source_folder: Path, target_base: Path) -> bool:
    """Synchronizuje folder bez --delete, a kasowanie dodatkow robi dopiero po dry-run."""
    destination_folder = target_base / source_folder.name

    valid, reason = validate_pair(source_folder, destination_folder)
    if not valid:
        print(f"❌ Walidacja nieudana: {reason}", flush=True)
        return False

    if not confirm_pair(source_folder, destination_folder):
        print("  ⏭️ Pomijam na zyczenie uzytkownika", flush=True)
        return False

    ensure_nas_available(target_base.parent)

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

    print("\n🧪 Dry-run delete po synchronizacji", flush=True)
    extras = detect_destination_only_entries(source_folder, destination_folder)
    if extras:
        print(f"  ⚠️ Dodatkowe wpisy tylko w target: {len(extras)}", flush=True)
        for item in extras[:DELETE_PREVIEW_LIMIT]:
            print(f"   - {item}", flush=True)
        if len(extras) > DELETE_PREVIEW_LIMIT:
            print(f"   ... i jeszcze {len(extras) - DELETE_PREVIEW_LIMIT} wiecej", flush=True)

        if ask_yes_no_default_no("  Czy usunac te dodatkowe wpisy z target? (t/n, domyslnie n): "):
            print("  🧹 Uruchamiam rsync z --delete po potwierdzeniu", flush=True)
            if not apply_delete_on_destination(source_folder, destination_folder):
                return False
        else:
            print("  ℹ️ Pozostawiono dodatkowe wpisy w target", flush=True)
    else:
        print("  ✅ Brak dodatkowych wpisow do usuniecia", flush=True)

    return True


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


def sync_collection(collection_name: str, paths: list[Path], target_base: Path) -> tuple[bool, list[Path]]:
    """Synchronizuje kolekcje i zwraca status + faktycznie przetworzone zrodla."""
    print(f"\n📂 Synchronizacja kolekcji: {collection_name}", flush=True)
    ensure_nas_available(target_base.parent)

    success = True
    synced_sources: list[Path] = []

    for source_path in paths:
        if source_path.is_file():
            item_ok = sync_file(source_path, target_base)
        elif source_path.is_dir():
            item_ok = sync_folder(source_path, target_base)
        else:
            print(f"⚠️ Nieznany typ lub brak wpisu: {source_path}", flush=True)
            item_ok = False

        if item_ok:
            synced_sources.append(source_path)
        else:
            success = False

    return success, synced_sources


def get_target_from_user() -> Path:
    """Pobiera sciezke docelowa od uzytkownika."""
    user_input = input(f"\n📁 Podaj sciezke docelowa na QNAP (domyslnie: {DEFAULT_QNAP_TARGET}): ").strip()
    if not user_input:
        return DEFAULT_QNAP_TARGET
    return Path(user_input).expanduser()


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

    target_base = get_target_from_user()
    if not str(target_base).strip() or target_base.resolve() == Path("/"):
        print("❌ Niepoprawny target bazowy", flush=True)
        return

    print(f"\n🔍 Sprawdzanie dostepnosci QNAP: {target_base.parent}", flush=True)
    ensure_nas_available(target_base.parent)
    target_base.mkdir(parents=True, exist_ok=True)

    print(f"\n🚀 Rozpoczynanie synchronizacji do: {target_base}", flush=True)

    overall_success = True
    all_synced_sources: list[Path] = []

    for collection_name, source_paths in collections.items():
        collection_ok, synced_sources = sync_collection(collection_name, source_paths, target_base)
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