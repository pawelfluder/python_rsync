"""
rsync_sync_v1.py - Synchronizacja plików do QNAP przy użyciu rsync

Skrypt wczytuje konfigurację z AA_Input/input.yaml zgodnie z zasadami
z files_collections_yaml_parsing_v1.py i synchronizuje pliki do folderu
na QNAP (domyślnie /Volumes/qnap/01_todo_a).

Wykorzystuje retry_network_drive_v2.py do obsługi przerw w połączeniu.
"""

import os
import subprocess
import sys
import shutil
from pathlib import Path

# Konfiguracja ścieżek repozytorium
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]  # Jeden poziom w górę: src/Rsync -> repo_root

# Dodanie repozytorium do ścieżki importów
sys.path.append(str(REPO_ROOT))

# Importy z modułów projektu
from modules.YamlParsing.files_collections_yaml_parsing_v1 import load_file_collections_from_yaml
from modules.RetryNetworkDrive.retry_network_drive_v2 import ensure_nas_available

# Stałe
DEFAULT_QNAP_TARGET = Path(os.getenv("qnap_default_target", "/Volumes/qnap"))
INPUT_YAML_PATH = REPO_ROOT / "AA_Input" / "input.yaml"
QMAP_PATH = Path("/Volumes/qnap")


def run_rsync_with_live_output(cmd: list[str]) -> bool:
    """Uruchamia rsync i przekazuje jego output bezpośrednio do terminala."""
    print(f"  ▶ {' '.join(cmd)}")
    try:
        completed = subprocess.run(cmd, check=False)
        if completed.returncode != 0:
            print(f"  ❌ rsync zakończył się kodem: {completed.returncode}")
            return False
        return True
    except Exception as e:
        print(f"  ❌ Błąd uruchamiania rsync: {e}")
        return False


def ask_yes_no(prompt: str) -> bool:
    """Uniwersalne pytanie t/n do użytkownika."""
    while True:
        response = input(prompt).strip().lower()
        if response in ["t", "tak", "y", "yes"]:
            return True
        if response in ["n", "nie", "no"]:
            return False
        print("   Proszę wpisać 't' (tak) lub 'n' (nie)")


def detect_destination_only_entries(source_folder: Path, destination_folder: Path) -> list[str]:
    """Wykrywa elementy istniejące tylko w folderze docelowym."""
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
    except Exception as e:
        print(f"  ⚠️ Nie udało się wykryć plików tylko po stronie docelowej: {e}")
        return []

    if result.returncode != 0:
        print(f"  ⚠️ Diff przed synchronizacją zwrócił kod {result.returncode}, pomijam wykrywanie nadmiarowych plików")
        if result.stderr:
            print(f"  stderr: {result.stderr.strip()}")
        return []

    extras = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("*deleting "):
            extras.append(stripped.replace("*deleting ", "", 1))

    return extras


def verify_file_sync(source_file: Path, destination_file: Path) -> bool:
    """Weryfikuje, że plik został poprawnie przesłany."""
    if not destination_file.exists() or not destination_file.is_file():
        print(f"  ❌ Brak pliku docelowego: {destination_file}")
        return False

    src_size = source_file.stat().st_size
    dst_size = destination_file.stat().st_size
    if src_size != dst_size:
        print(f"  ❌ Rozmiar pliku różni się (src={src_size}, dst={dst_size}): {source_file.name}")
        return False

    return True


def verify_folder_sync(source_folder: Path, destination_folder: Path) -> bool:
    """Weryfikuje folder przez rsync dry-run, porównując zawartość plików."""
    cmd = [
        "rsync",
        "-rcni",
        "--no-perms",
        "--no-owner",
        "--no-group",
        "--omit-dir-times",
        str(source_folder) + "/",
        str(destination_folder) + "/",
    ]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ❌ Nie udało się zweryfikować folderu {source_folder.name}: kod {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr.strip()}")
            return False

        pending_changes = result.stdout.strip()
        if pending_changes:
            print("  ❌ Weryfikacja nie przeszła - pozostały różnice w zawartości:")
            print(result.stdout.strip())
            return False

        return True
    except Exception as e:
        print(f"  ❌ Błąd weryfikacji folderu {source_folder.name}: {e}")
        return False


def sync_file(file_path: Path, target_folder: Path) -> bool:
    """
    Synchronizuje pojedynczy plik do folderu docelowego.
    """
    if not file_path.exists():
        print(f"⚠️ Plik nie istnieje: {file_path}")
        return False
    
    ensure_nas_available(target_folder.parent)
    target_folder.mkdir(parents=True, exist_ok=True)
    
    dest_path = target_folder / file_path.name
    
    cmd = [
        "rsync",
        "-av",
        "--progress",
        str(file_path),
        str(dest_path)
    ]
    
    if not run_rsync_with_live_output(cmd):
        return False

    if not verify_file_sync(file_path, dest_path):
        return False

    print(f"  ✅ {file_path.name} -> {dest_path}")
    return True


def sync_folder(folder_path: Path, target_folder: Path) -> bool:
    """
    Synchronizuje cały folder do folderu docelowego.
    """
    if not folder_path.is_dir():
        print(f"⚠️ Folder nie istnieje: {folder_path}")
        return False
    
    ensure_nas_available(target_folder.parent)
    target_folder.mkdir(parents=True, exist_ok=True)
    
    dest_path = target_folder / folder_path.name

    delete_in_destination = False
    extras = detect_destination_only_entries(folder_path, dest_path)
    if extras:
        print("  ⚠️ W docelowym folderze są pliki/foldery nieobecne w źródle:")
        for extra in extras:
            print(f"    - {extra}")
        delete_in_destination = ask_yes_no("  Czy usunąć je podczas synchronizacji? (t/n): ")
    
    cmd = [
        "rsync",
        "-av",
        "--progress",
        str(folder_path) + "/",
        str(dest_path) + "/"
    ]
    if delete_in_destination:
        cmd.insert(3, "--delete")
    
    if not run_rsync_with_live_output(cmd):
        return False

    if not verify_folder_sync(folder_path, dest_path):
        return False

    print(f"  ✅ {folder_path.name}/ -> {dest_path}/")
    return True


def sync_collection(collection_name: str, files: list[Path], target_base: Path) -> bool:
    """
    Synchronizuje kolekcję plików.
    """
    print(f"\n📂 Synchronizacja kolekcji: {collection_name}")
    
    ensure_nas_available(target_base.parent)
    
    folders = []
    single_files = []
    
    for file_path in files:
        if file_path.is_dir():
            folders.append(file_path)
        elif file_path.is_file():
            single_files.append(file_path)
        else:
            print(f"⚠️ Nieznany typ: {file_path}")
    
    if not files:
        print(f"  ⚠️ Kolekcja '{collection_name}' jest pusta - nic do synchronizacji")
        return False

    success = True
    
    for file_path in single_files:
        if not sync_file(file_path, target_base):
            success = False
    
    for folder_path in folders:
        if not sync_folder(folder_path, target_base):
            success = False
    
    return success


def get_target_from_user() -> Path:
    """
    Pobiera ścieżkę docelową od użytkownika.
    """
    user_input = input(f"\n📁 Podaj ścieżkę docelową na QNAP (domyślnie: {DEFAULT_QNAP_TARGET}): ").strip()
    
    if not user_input:
        return DEFAULT_QNAP_TARGET
    
    return Path(user_input)


def ask_delete_source(collection_name: str, source_paths: list[Path]) -> bool:
    """
    Pyta użytkownika czy usunąć źródłowe pliki/foldery po synchronizacji.
    """
    print(f"\n🗑️  Kolekcja '{collection_name}' została zsynchronizowana.")
    print("   Źródłowe ścieżki:")
    for path in source_paths:
        print(f"     - {path}")
    
    return ask_yes_no("\n   Czy usunąć źródłowe pliki/foldery? (t/n): ")


def delete_source_paths(source_paths: list[Path]) -> bool:
    """
    Usuwa źródłowe pliki/foldery.
    """
    success = True
    for path in source_paths:
        try:
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  ✅ Usunięto folder: {path}")
            elif path.is_file():
                path.unlink()
                print(f"  ✅ Usunięto plik: {path}")
            else:
                print(f"  ⚠️  Ścieżka nie istnieje: {path}")
        except Exception as e:
            print(f"  ❌ Błąd podczas usuwania {path}: {e}")
            success = False
    
    return success


def main():
    """Główna funkcja skryptu."""
    print("🔍 Wczytywanie konfiguracji synchronizacji...")
    
    if not INPUT_YAML_PATH.exists():
        print(f"❌ Plik konfiguracji nie istnieje: {INPUT_YAML_PATH}")
        print("   Utwórz plik AA_Input/input.yaml zgodnie z zasadami z files_collections_yaml_parsing_v1.py")
        return
    
    try:
        collections = load_file_collections_from_yaml(str(INPUT_YAML_PATH))
    except Exception as e:
        print(f"❌ Błąd wczytywania YAML: {e}")
        return
    
    if not collections:
        print("⚠️ Brak kolekcji do synchronizacji w pliku YAML")
        return
    
    target_path = get_target_from_user()
    
    print(f"\n🔍 Sprawdzanie dostępności QNAP: {target_path.parent}")
    ensure_nas_available(target_path.parent)
    
    if not target_path.exists():
        print(f"⚠️ Folder docelowy nie istnieje: {target_path}")
        print("   Tworzenie folderu...")
        try:
            target_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Utworzono folder: {target_path}")
        except Exception as e:
            print(f"❌ Nie udało się utworzyć folderu: {e}")
            return
    
    print(f"\n🚀 Rozpoczynanie synchronizacji do: {target_path}")
    
    overall_success = True
    for collection_name, files in collections.items():
        collection_success = sync_collection(collection_name, files, target_path)
        if not collection_success:
            overall_success = False
        else:
            if files and ask_delete_source(collection_name, files):
                if not delete_source_paths(files):
                    print(f"  ⚠️  Nie wszystkie pliki/foldery zostały usunięte")
    
    print("\n" + "="*50)
    if overall_success:
        print("✅ Synchronizacja zakończona pomyślnie!")
    else:
        print("⚠️  Synchronizacja zakończona z błędami (sprawdź logi powyżej)")
    print("="*50)


if __name__ == "__main__":
    main()