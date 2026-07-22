"""
rsync_voice-memo/main.py - opakowanie: nie zawiera logiki, tylko uruchamia najnowsza
wersje rsync_voice-memo_vN.py z tego katalogu (aktualnie: rsync_voice-memo_v1.py).

Kolejne wersje dodaje sie jako rsync_voice-memo_v2.py, rsync_voice-memo_v3.py, itd. -
main.py nie wymaga wtedy zadnej zmiany, sam wykryje najwyzszy numer.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.append(str(SRC_ROOT))

from rsync_core.versioning import run_latest_version

if __name__ == "__main__":
    run_latest_version(SCRIPT_DIR, prefix="rsync_voice-memo")
