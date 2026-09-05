# Opis: rsync_voice-memo_v5.txt

import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SRC_ROOT = REPO_ROOT / "src"

# "rsync_voice-memo" ma myslnik w nazwie (wymagana nazwa folderu), wiec nie da sie go
# zaimportowac jako pakietu z kreska w nazwie - dlatego wlasny katalog dodajemy do
# sys.path i importujemy sasiednie moduly po prostej nazwie.
sys.path.append(str(SRC_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from rsync_core.nas import ensure_nas
from rsync_core.preflight import verify_file_sync
from rsync_core.validation import ask_yes_no_default_no

from config import load_voice_memo_target
from diagnostics import build_diagnostics, list_selectable_recordings, print_diagnostics, print_source_not_found
from sync import copy_selected_files, run_dry_run_for_selected_files

# python_modules jest juz na sys.path (dodane jako efekt importu rsync_core.nas
# powyzej, patrz rsync_core/nas.py) - files_selection zyje tam, nie w tym repo.
from modules.files_selection.files_selection_v5 import display_files_with_numbers, parse_selection

INPUT_YAML_PATH = REPO_ROOT / "AA_Input" / "input_voice-memo.yaml"
SELECTION_COLLECTION_NAME = "voice-memos"

# Sytuacja jednorazowa (patrz rsync_voice-memo_v5.txt): stare wpisy w Voice Memos
# ciagle sie "odswiezaly", wiec caly katalog Recordings zostal recznie przeniesiony
# na Pulpit (backup), a Voice Memos wystartowalo od nowa z pusta baza. v5 wskazuje
# source RECZNIE na ten backup - zamiast automatycznego wykrywania jak w v1-v4
# (discovery.py). Zeby wrocic do standardowej (systemowej) lokalizacji Voice Memos,
# odkomentuj druga linie ponizej i zakomentuj pierwsza.
SOURCE_PATH = Path("/Users/pawelfluder/Desktop/VoiceMemos-backup-20260829-192923/Recordings")
# SOURCE_PATH = Path("~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings").expanduser()


def ask_selection(recordings: list[Path]) -> list[Path]:
    """Wypisuje numerowana liste nagran (najnowsze na gorze, (1) = najnowszy) i pyta
    o wybor: all / zakres / lista.

    `recordings` przychodzi chronologicznie rosnaco (list_selectable_recordings())
    - odwracamy tutaj, zeby najnowszy byl pierwszy w liscie przekazywanej do
    files_selection_v5, ktory numeruje w podanej kolejnosci bez wlasnej reorganizacji.
    """
    newest_first = list(reversed(recordings))
    collections = {SELECTION_COLLECTION_NAME: newest_first}
    display_files_with_numbers(collections, get_duration=None, format_duration=None, show_durations=False)

    raw = input(
        "\n➡️ Ktore nagrania skopiowac? (all / zakres np. 1-3 / lista np. 1,3,4,7) [domyslnie: all]: "
    ).strip()
    if not raw:
        raw = "all"

    selected = parse_selection(raw, collections)
    return selected.get(SELECTION_COLLECTION_NAME, [])


def default_destination_for_today(base_target: Path) -> Path:
    """<base_target>/<RR-MM-DD>_voice_memo, np. /Volumes/qnap/01_todo_a/26-07-22_voice_memo."""
    date_str = datetime.now().strftime("%y-%m-%d")
    return base_target / f"{date_str}_voice_memo"


def ask_destination(base_target: Path) -> Path:
    """Pyta o cel na QNAP tak samo jak rsync_files - Enter akceptuje domyslna wartosc."""
    default_target = default_destination_for_today(base_target)
    user_input = input(f"\n📁 Podaj sciezke docelowa (domyslnie: {default_target}): ").strip()
    return Path(user_input).expanduser() if user_input else default_target


def verify_selected_files_copied(destination: Path, selected_files: list[Path]) -> list[Path]:
    """Weryfikuje rozmiar kazdego skopiowanego pliku. Zwraca liste plikow, ktore sie NIE zgadzaja."""
    mismatched: list[Path] = []
    for file_path in selected_files:
        destination_file = destination / file_path.name
        if not verify_file_sync(file_path, destination_file):
            mismatched.append(file_path)
    return mismatched


def find_related_source_items(source: Path, recording: Path) -> list[Path]:
    """Zwraca WSZYSTKIE wpisy w source o tym samym rdzeniu nazwy (Path.stem) co `recording`.

    Voice Memos trzyma dla jednego nagrania kilka powiazanych wpisow pod tym samym
    znacznikiem czasu - np. dla "20250107 110307.m4a" rowniez folder
    "20250107 110307.composition" (fragmenty edycji) i plik
    "20250107 110307.waveform" (cache waveformu), potwierdzone live na realnym
    Macu. Path.stem obcina tylko OSTATNI suffix, wiec "X.composition".stem == "X"
    tak samo jak "X.m4a".stem == "X" - to wystarcza do dopasowania calego zestawu.
    """
    stem = recording.stem
    return sorted(p for p in source.iterdir() if p.stem == stem)


def collect_related_source_items(source: Path, selected_files: list[Path]) -> list[Path]:
    """Laczy find_related_source_items() dla wszystkich wybranych nagran, bez duplikatow."""
    related_items: list[Path] = []
    seen: set[Path] = set()
    for recording in selected_files:
        for item in find_related_source_items(source, recording):
            if item not in seen:
                seen.add(item)
                related_items.append(item)
    return related_items


def ask_delete_originals_double_confirm(related_items: list[Path]) -> bool:
    """Podwojne potwierdzenie usuniecia oryginalow (i wszystkiego powiazanego) - JEDNO
    pytanie dla calego zestawu na raz (nigdy per plik), plus drugie "na pewno?" -
    wywolywane TYLKO po zweryfikowanej kopii."""
    print("\n🗑️ Wszystkie wybrane nagrania poprawnie skopiowane na QNAP.", flush=True)
    print("   Do usuniecia (nagranie + powiazane pliki/foldery, np. .composition/.waveform):", flush=True)
    for path in related_items:
        print(f"   - {path}", flush=True)

    first = ask_yes_no_default_no(
        "   Czy usunac te oryginalne nagrania (i powiazane resztki) z Voice Memos na Macu? (t/n, domyslnie n): "
    )
    if not first:
        print("   ℹ️ Oryginaly pozostaly bez zmian", flush=True)
        return False

    second = ask_yes_no_default_no(
        "   Potwierdzenie 2/2: na pewno usunac oryginalne nagrania i powiazane resztki? (t/n, domyslnie n): "
    )
    if not second:
        print("   ℹ️ Anulowano na drugim potwierdzeniu", flush=True)
        return False

    return True


def delete_related_source_items(related_items: list[Path]) -> bool:
    """Usuwa WYLACZNIE podane wpisy (nagrania + powiazane resztki) - nigdy caly folder Recordings."""
    success = True
    for item in related_items:
        try:
            if item.is_dir():
                shutil.rmtree(item)
                print(f"  ✅ Usunieto folder: {item}", flush=True)
            else:
                item.unlink()
                print(f"  ✅ Usunieto: {item}", flush=True)
        except Exception as exc:
            print(f"  ❌ Blad usuwania {item}: {exc}", flush=True)
            success = False
    return success


def main() -> None:
    """Glowna funkcja skryptu."""
    print(f"🔍 Uzywam recznie wskazanego katalogu Voice Memos: {SOURCE_PATH}", flush=True)

    source = SOURCE_PATH
    if not source.is_dir():
        print_source_not_found([SOURCE_PATH])
        return

    diagnostics = build_diagnostics(source)
    print_diagnostics(diagnostics)

    if not diagnostics.recordings:
        print("⚠️ Katalog istnieje, ale nie zawiera plikow .m4a - nic do skopiowania.", flush=True)
        return

    recordings = list_selectable_recordings(source)
    if not recordings:
        print(
            "⚠️ Brak nagran na najwyzszym poziomie katalogu (tylko wewnetrzne fragmenty .composition) - nic do wyboru.",
            flush=True,
        )
        return

    print(f"\n🎙️ Nagran do wyboru: {len(recordings)}", flush=True)
    selected_files = ask_selection(recordings)

    if not selected_files:
        print("ℹ️ Nic nie wybrano - koncze.", flush=True)
        return

    base_target = load_voice_memo_target(INPUT_YAML_PATH)
    destination = ask_destination(base_target)

    print(f"\n📁 Source: {source}", flush=True)
    print(f"📁 Target (QNAP): {destination}", flush=True)
    print(f"🎙️ Wybranych nagran: {len(selected_files)}", flush=True)

    ensure_nas()

    print("\n🧪 Dry-run przed kopiowaniem:", flush=True)
    dry_run_output = run_dry_run_for_selected_files(source, destination, selected_files)
    print(dry_run_output.strip() or "  (brak zmian - target juz zawiera wszystkie wybrane nagrania)", flush=True)

    print("\n📦 Kopiowanie...", flush=True)
    if not copy_selected_files(source, destination, selected_files):
        print("⚠️ Kopiowanie wybranych nagran Voice Memos zakonczone z bledami (sprawdz logi powyzej)", flush=True)
        return

    print("✅ Kopiowanie wybranych nagran Voice Memos zakonczone pomyslnie!", flush=True)

    mismatched = verify_selected_files_copied(destination, selected_files)
    if mismatched:
        print(f"⚠️ Weryfikacja wykryla {len(mismatched)} niezgodnosc(i) - oryginaly NIE beda usuwane:", flush=True)
        for path in mismatched:
            print(f"   - {path}", flush=True)
        return

    related_items = collect_related_source_items(source, selected_files)
    if ask_delete_originals_double_confirm(related_items):
        if not delete_related_source_items(related_items):
            print("⚠️ Usuwanie oryginalow zakonczone z bledami (sprawdz logi powyzej)", flush=True)


if __name__ == "__main__":
    main()
