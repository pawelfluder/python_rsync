"""Wspolny mechanizm 'main.py to tylko opakowanie, ktore uruchamia najnowsza wersje'.

Uzywane przez rsync_files/main.py, rsync_voice-memo/main.py i clean_docker/main.py:
kazdy z tych folderow trzyma cala historie wersji jako osobne pliki
<prefix>_v1.py, <prefix>_v2.py, ... (tak jak retry_network_drive_v1.py...v6.py) -
main.py sam nie zawiera logiki, tylko znajduje plik z najwyzszym numerem wersji
i wywoluje jego main().

Wczytywanie przez importlib.util (nie zwykly "import") dziala nawet dla plikow,
ktorych nazwa zawiera myslnik (np. rsync_voice-memo_v1.py) - "import" z myslnikiem
w nazwie modulu jest bledem skladni, a importlib nie ma tego ograniczenia.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType


def find_latest_version_file(script_dir: Path, prefix: str) -> Path:
    """Znajduje plik '<prefix>_vN.py' z najwyzszym N w podanym katalogu."""
    pattern = re.compile(rf"^{re.escape(prefix)}_v(\d+)\.py$")
    candidates: list[tuple[int, Path]] = []
    for entry in script_dir.iterdir():
        match = pattern.match(entry.name)
        if match:
            candidates.append((int(match.group(1)), entry))

    if not candidates:
        raise FileNotFoundError(f"Nie znaleziono zadnego pliku '{prefix}_vN.py' w {script_dir}")

    _, latest_path = max(candidates, key=lambda item: item[0])
    return latest_path


def load_module_from_path(module_name: str, path: Path) -> ModuleType:
    """Wczytuje modul z konkretnej sciezki, niezaleznie od tego, czy nazwa pliku jest poprawnym identyfikatorem."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Nie mozna wczytac modulu z {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_latest_version(script_dir: Path, prefix: str) -> None:
    """Znajduje najnowszy '<prefix>_vN.py' w script_dir i wywoluje jego main()."""
    latest_path = find_latest_version_file(script_dir, prefix)
    module_name = latest_path.stem.replace("-", "_")
    print(f"▶ Uruchamiam najnowsza wersje: {latest_path.name}", flush=True)
    module = load_module_from_path(module_name, latest_path)
    module.main()
