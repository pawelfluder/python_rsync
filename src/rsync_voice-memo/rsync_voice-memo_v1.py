# Opis: rsync_voice-memo_v1.txt

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SRC_ROOT = REPO_ROOT / "src"

# "rsync_voice-memo" ma myslnik w nazwie (wymagana nazwa folderu), wiec nie da sie go
# zaimportowac jako pakietu z kreska w nazwie ("import rsync_voice-memo" to blad
# skladni) - dlatego wlasny katalog dodajemy do sys.path i importujemy sasiednie
# moduly po prostej nazwie (discovery, diagnostics, config, sync).
sys.path.append(str(SRC_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from rsync_core.nas import ensure_nas
from rsync_core.validation import ask_yes_no_default_no

from config import load_voice_memo_target
from diagnostics import build_diagnostics, print_diagnostics, print_source_not_found
from discovery import CANDIDATE_SOURCE_PATHS, find_voice_memos_source
from sync import run_voice_memo_dry_run, sync_voice_memos

INPUT_YAML_PATH = REPO_ROOT / "AA_Input" / "input_voice-memo.yaml"


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

    destination = load_voice_memo_target(INPUT_YAML_PATH)

    print(f"\n📁 Source: {source}", flush=True)
    print(f"📁 Target (QNAP): {destination}", flush=True)
    print(f"🎙️ Nagran do skopiowania: {len(diagnostics.recordings)}", flush=True)

    ensure_nas()

    print("\n🧪 Dry-run przed kopiowaniem:", flush=True)
    dry_run_output = run_voice_memo_dry_run(source, destination)
    print(dry_run_output.strip() or "  (brak zmian - target juz zawiera wszystkie nagrania)", flush=True)

    if not ask_yes_no_default_no("\n➡️ Skopiowac nagrania na QNAP? (t/n, domyslnie n): "):
        print("ℹ️ Pomijam kopiowanie na zyczenie uzytkownika", flush=True)
        return

    if sync_voice_memos(source, destination):
        print("✅ Kopiowanie nagran Voice Memos zakonczone pomyslnie!", flush=True)
    else:
        print("⚠️ Kopiowanie nagran Voice Memos zakonczone z bledami (sprawdz logi powyzej)", flush=True)


if __name__ == "__main__":
    main()
