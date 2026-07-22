# Opis: rsync_voice-memo_v2.txt

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
from rsync_core.validation import ask_yes_no_default_no

from config import load_voice_memo_target
from diagnostics import build_diagnostics, list_selectable_recordings, print_diagnostics, print_source_not_found
from discovery import CANDIDATE_SOURCE_PATHS, find_voice_memos_source
from sync import copy_selected_files, run_dry_run_for_selected_files

# python_modules jest juz na sys.path (dodane jako efekt importu rsync_core.nas
# powyzej, patrz rsync_core/nas.py) - files_selection zyje tam, nie w tym repo.
from modules.files_selection.files_selection_v4 import display_files_with_numbers, parse_selection

INPUT_YAML_PATH = REPO_ROOT / "AA_Input" / "input_voice-memo.yaml"
SELECTION_COLLECTION_NAME = "voice-memos"


def ask_selection(recordings: list[Path]) -> list[Path]:
    """Wypisuje numerowana liste nagran (najnowsze na gorze) i pyta o wybor: all / zakres / lista."""
    collections = {SELECTION_COLLECTION_NAME: recordings}
    display_files_with_numbers(collections, get_duration=None, format_duration=None, show_durations=False)

    raw = input(
        "\n➡️ Ktore nagrania skopiowac? (all / zakres np. 1-3 / lista np. 1,3,4,7) [domyslnie: all]: "
    ).strip()
    if not raw:
        raw = "all"

    selected = parse_selection(raw, collections)
    return selected.get(SELECTION_COLLECTION_NAME, [])


def default_destination_for_today(base_target: Path) -> Path:
    """<base_target>/<RR-MM-DD>_voice_memo, np. /Volumes/qnap/.../voice-memos/26-07-22_voice_memo."""
    date_str = datetime.now().strftime("%y-%m-%d")
    return base_target / f"{date_str}_voice_memo"


def ask_destination(base_target: Path) -> Path:
    """Pyta o cel na QNAP tak samo jak rsync_files - Enter akceptuje domyslna wartosc."""
    default_target = default_destination_for_today(base_target)
    user_input = input(f"\n📁 Podaj sciezke docelowa (domyslnie: {default_target}): ").strip()
    return Path(user_input).expanduser() if user_input else default_target


def main() -> None:
    """Glowna funkcja skryptu."""
    print("🔍 Szukam lokalnego katalogu Voice Memos (zsynchronizowanego przez iCloud)...", flush=True)

    source = find_voice_memos_source()
    if source is None:
        print_source_not_found(CANDIDATE_SOURCE_PATHS)
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

    if not ask_yes_no_default_no("\n➡️ Skopiowac wybrane nagrania na QNAP? (t/n, domyslnie n): "):
        print("ℹ️ Pomijam kopiowanie na zyczenie uzytkownika", flush=True)
        return

    if copy_selected_files(source, destination, selected_files):
        print("✅ Kopiowanie wybranych nagran Voice Memos zakonczone pomyslnie!", flush=True)
    else:
        print("⚠️ Kopiowanie wybranych nagran Voice Memos zakonczone z bledami (sprawdz logi powyzej)", flush=True)


if __name__ == "__main__":
    main()
